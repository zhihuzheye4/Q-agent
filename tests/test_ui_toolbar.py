"""工具栏 + 模型下拉框单测（v0.0.7：本地 / Ollama Cloud 转发 / 云端预置三组）。

覆盖：
    - Toolbar 可构造，初始占位"检测中..."且 disabled
    - _on_models_found 仅本地模型：本地 header + 本地项 + 云端预置 header + 预置项
    - _on_models_found 含 Ollama Cloud 转发：本地 + Ollama Cloud 组 + 云端预置组
    - _on_models_found 无本地模型：本地占位 + Ollama Cloud 组 + 云端预置组
    - _on_models_found 全空：本地占位 + 云端预置组（无 Ollama Cloud 组）
    - _on_refresh_failed：仅"未发现本地 LLM"占位，不加任何后续组
    - _on_combo_changed：header / placeholder 不 emit，真模型项 emit
    - current_model：占位 / header / 未选 返回 None；真模型返回模型名
    - ModelRefreshWorker：models_found / refresh_failed 信号触发
    - MainWindow 启动自动触发一次检测
"""

from __future__ import annotations

import os

import pytest

from q_agent.llm.ollama import ModelEntry

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _entry(name: str, is_remote: bool = False, remote_host: str = "") -> ModelEntry:
    """构造 ModelEntry 测试替身。"""
    return ModelEntry(name=name, is_remote=is_remote, remote_host=remote_host)


def test_toolbar_constructs_with_model_group(qapp) -> None:  # noqa: ANN001
    """Toolbar 含模型下拉框 + 刷新按钮，初始占位为"检测中..."且 disabled。"""
    from q_agent.ui.toolbar import PLACEHOLDER_DETECTING, Toolbar

    tb = Toolbar()
    assert tb.model_combo is not None
    assert tb.refresh_btn is not None
    assert tb.model_combo.count() == 1
    assert tb.model_combo.itemText(0) == PLACEHOLDER_DETECTING
    assert not tb.model_combo.isEnabled(), "初始检测中状态应 disabled"


def test_on_models_found_local_only(qapp) -> None:  # noqa: ANN001
    """仅本地模型 → 本地 header + 本地项 + 云端预置 header + 预置项。"""
    from q_agent.ui.toolbar import CLOUD_PRESET, HEADER_CLOUD, HEADER_LOCAL, Toolbar

    received: list[str] = []
    tb = Toolbar(status_callback=received.append)
    tb._on_models_found([_entry("qwen2.5:7b"), _entry("llama3:8b")])

    # 总项数 = 1 本地 header + 2 本地模型 + 1 云端预置 header + 3 预置 = 7
    # 无 Ollama Cloud 组（无 is_remote=True）
    assert tb.model_combo.count() == 1 + 2 + 1 + len(CLOUD_PRESET)
    assert tb.model_combo.itemText(0) == HEADER_LOCAL
    assert tb.model_combo.itemText(1) == "qwen2.5:7b"
    assert tb.model_combo.itemText(2) == "llama3:8b"
    assert tb.model_combo.itemText(3) == HEADER_CLOUD
    assert tb.model_combo.itemText(4) == "gpt-4o (OpenAI)"
    assert tb.model_combo.itemText(5) == "claude-opus-4-7 (Anthropic)"
    assert tb.model_combo.itemText(6) == "gemini-2.5-pro (Google)"
    assert tb.model_combo.isEnabled()
    # header / placeholder 项应 disabled
    assert not tb.model_combo.model().item(0).isEnabled()  # 本地 header
    assert tb.model_combo.model().item(1).isEnabled()  # qwen2.5:7b 可选
    assert not tb.model_combo.model().item(3).isEnabled()  # 云端 header
    assert any("已发现" in msg for msg in received)


def test_on_models_found_with_ollama_cloud(qapp) -> None:  # noqa: ANN001
    """含 Ollama Cloud 转发 → 本地 + Ollama Cloud 组 + 云端预置组三组。"""
    from q_agent.ui.toolbar import (
        CLOUD_PRESET,
        HEADER_CLOUD,
        HEADER_LOCAL,
        HEADER_OLLAMA_CLOUD,
        Toolbar,
    )

    received: list[str] = []
    tb = Toolbar(status_callback=received.append)
    tb._on_models_found(
        [
            _entry("qwen2.5:7b", is_remote=False),
            _entry("minimax-m3:latest", is_remote=True, remote_host="https://ollama.com"),
            _entry("deepseek-v4-pro", is_remote=True, remote_host="https://ollama.com"),
        ]
    )

    # 1 本地 header + 1 本地 + 1 Ollama Cloud header + 2 cloud + 1 预置 header + 3 预置 = 9
    assert tb.model_combo.count() == 1 + 1 + 1 + 2 + 1 + len(CLOUD_PRESET)
    assert tb.model_combo.itemText(0) == HEADER_LOCAL
    assert tb.model_combo.itemText(1) == "qwen2.5:7b"
    assert tb.model_combo.itemText(2) == HEADER_OLLAMA_CLOUD
    assert tb.model_combo.itemText(3) == "minimax-m3:latest"
    assert tb.model_combo.itemText(4) == "deepseek-v4-pro"
    assert tb.model_combo.itemText(5) == HEADER_CLOUD
    assert tb.model_combo.itemText(6) == "gpt-4o (OpenAI)"
    # Ollama Cloud header disabled，转发模型项可选
    assert not tb.model_combo.model().item(2).isEnabled()  # Ollama Cloud header
    assert tb.model_combo.model().item(3).isEnabled()  # minimax 可选
    assert tb.model_combo.model().item(4).isEnabled()  # deepseek 可选
    # 默认选中本地首个
    assert tb.current_model() == "qwen2.5:7b"
    # 状态栏应包含 "Ollama Cloud" 字样
    assert any("Ollama Cloud" in msg for msg in received)


def test_on_models_found_only_ollama_cloud_no_local(qapp) -> None:  # noqa: ANN001
    """仅 cloud 转发无本地 → 本地占位 + Ollama Cloud 组 + 云端预置组。"""
    from q_agent.ui.toolbar import (
        CLOUD_PRESET,
        HEADER_CLOUD,
        HEADER_LOCAL,
        HEADER_OLLAMA_CLOUD,
        PLACEHOLDER_NO_LOCAL_MODEL,
        Toolbar,
    )

    tb = Toolbar()
    tb._on_models_found(
        [_entry("minimax-m3:latest", is_remote=True, remote_host="https://ollama.com")]
    )

    # 1 本地 header + 1 占位 + 1 Ollama Cloud header + 1 cloud + 1 预置 header + 3 预置 = 8
    assert tb.model_combo.count() == 1 + 1 + 1 + 1 + 1 + len(CLOUD_PRESET)
    assert tb.model_combo.itemText(0) == HEADER_LOCAL
    assert tb.model_combo.itemText(1) == PLACEHOLDER_NO_LOCAL_MODEL
    assert tb.model_combo.itemText(2) == HEADER_OLLAMA_CLOUD
    assert tb.model_combo.itemText(3) == "minimax-m3:latest"
    assert tb.model_combo.itemText(4) == HEADER_CLOUD
    # 默认选中首个可选（Ollama Cloud 转发的 minimax）
    assert tb.current_model() == "minimax-m3:latest"


def test_on_models_found_empty_all(qapp) -> None:  # noqa: ANN001
    """全空（无本地无 cloud 转发）→ 本地占位 + 云端预置组（无 Ollama Cloud 组）。"""
    from q_agent.ui.toolbar import (
        CLOUD_PRESET,
        HEADER_CLOUD,
        HEADER_LOCAL,
        PLACEHOLDER_NO_LOCAL_MODEL,
        Toolbar,
    )

    received: list[str] = []
    tb = Toolbar(status_callback=received.append)
    tb._on_models_found([])

    # 1 本地 header + 1 占位 + 1 云端预置 header + 3 预置 = 6（无 Ollama Cloud 组）
    assert tb.model_combo.count() == 1 + 1 + 1 + len(CLOUD_PRESET)
    assert tb.model_combo.itemText(0) == HEADER_LOCAL
    assert tb.model_combo.itemText(1) == PLACEHOLDER_NO_LOCAL_MODEL
    assert tb.model_combo.itemText(2) == HEADER_CLOUD
    assert tb.model_combo.itemText(3) == "gpt-4o (OpenAI)"
    assert tb.model_combo.isEnabled()
    # 默认应选中云端首个可选项
    assert tb.current_model() == "gpt-4o (OpenAI)"
    assert any("0 个本地" in msg for msg in received)


def test_on_refresh_failed(qapp) -> None:  # noqa: ANN001
    """worker 失败 → 仅"未发现本地 LLM"占位项，不加任何后续组。"""
    from q_agent.ui.toolbar import PLACEHOLDER_EMPTY, Toolbar

    received: list[str] = []
    tb = Toolbar(status_callback=received.append)
    tb._on_refresh_failed("连接被拒绝")
    assert tb.model_combo.count() == 1
    assert tb.model_combo.itemText(0) == PLACEHOLDER_EMPTY
    assert not tb.model_combo.isEnabled()
    assert any("连接被拒绝" in msg for msg in received)


def test_combo_changed_emits_model_selected(qapp) -> None:  # noqa: ANN001
    """切换到真模型项 → emit model_selected。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found([_entry("qwen2.5:7b"), _entry("llama3:8b")])
    selected: list[str] = []
    tb.model_selected.connect(selected.append)
    # index 2 是 llama3:8b
    tb.model_combo.setCurrentIndex(2)
    assert selected == ["llama3:8b"]


def test_combo_changed_header_does_not_emit(qapp) -> None:  # noqa: ANN001
    """切换到 header（disabled）项不 emit。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found([_entry("qwen2.5:7b")])
    selected: list[str] = []
    tb.model_selected.connect(selected.append)
    # 尝试切到本地 header（index 0）
    tb.model_combo.setCurrentIndex(0)
    assert selected == []


def test_combo_changed_cloud_emits(qapp) -> None:  # noqa: ANN001
    """切换到云端预置模型项 → emit model_selected（带云端名）。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found([_entry("qwen2.5:7b")])
    selected: list[str] = []
    tb.model_selected.connect(selected.append)
    # 索引：0 本地header / 1 qwen / 2 云端预置header / 3 gpt-4o / 4 claude / 5 gemini
    tb.model_combo.setCurrentIndex(4)
    assert selected == ["claude-opus-4-7 (Anthropic)"]


def test_combo_changed_ollama_cloud_emits(qapp) -> None:  # noqa: ANN001
    """切换到 Ollama Cloud 转发模型项 → emit model_selected。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found(
        [
            _entry("qwen2.5:7b"),
            _entry("minimax-m3:latest", is_remote=True, remote_host="https://ollama.com"),
        ]
    )
    selected: list[str] = []
    tb.model_selected.connect(selected.append)
    # 索引：0 本地header / 1 qwen / 2 Ollama Cloud header / 3 minimax / 4 预置header / 5 gpt-4o...
    tb.model_combo.setCurrentIndex(3)
    assert selected == ["minimax-m3:latest"]


def test_current_model_returns_none_for_placeholder(qapp) -> None:  # noqa: ANN001
    """检测失败状态 current_model 返回 None。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_refresh_failed("boom")
    assert tb.current_model() is None


def test_current_model_returns_none_for_header(qapp) -> None:  # noqa: ANN001
    """选中 header 项 current_model 返回 None（不应被选中，但防御）。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found([_entry("qwen2.5:7b")])
    # 强行设 currentIndex 到 header（实际 UI 阻止，但代码层验证）
    tb.model_combo.setCurrentIndex(0)
    # current_model 内部检查 isEnabled，header disabled 返回 None
    assert tb.current_model() is None


def test_current_model_returns_local(qapp) -> None:  # noqa: ANN001
    """真本地模型选中后 current_model 返回模型名。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found([_entry("qwen2.5:7b")])
    tb.model_combo.setCurrentIndex(1)
    assert tb.current_model() == "qwen2.5:7b"


def test_current_model_returns_cloud(qapp) -> None:  # noqa: ANN001
    """云端预置模型选中后 current_model 返回云端名。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found([_entry("qwen2.5:7b")])
    tb.model_combo.setCurrentIndex(3)  # gpt-4o (OpenAI)
    assert tb.current_model() == "gpt-4o (OpenAI)"


def test_current_model_returns_ollama_cloud(qapp) -> None:  # noqa: ANN001
    """Ollama Cloud 转发模型选中后 current_model 返回模型名。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found(
        [
            _entry("qwen2.5:7b"),
            _entry("minimax-m3:latest", is_remote=True, remote_host="https://ollama.com"),
        ]
    )
    # 索引 3 是 minimax-m3:latest
    tb.model_combo.setCurrentIndex(3)
    assert tb.current_model() == "minimax-m3:latest"


def test_worker_emits_models_found(qapp, monkeypatch) -> None:  # noqa: ANN001
    """ModelRefreshWorker 成功 → models_found 信号带 ModelEntry 列表。"""
    from PySide6.QtTest import QTest

    from q_agent.llm.ollama import ModelEntry
    from q_agent.ui import toolbar as tb_mod
    from q_agent.ui.toolbar import ModelRefreshWorker

    expected = [ModelEntry(name="qwen2.5:7b", is_remote=False, remote_host="")]
    monkeypatch.setattr(
        tb_mod,
        "list_models",
        lambda host="http://localhost:11434", timeout=2.0: expected,
    )

    worker = ModelRefreshWorker()
    received: list[list] = []
    worker.models_found.connect(received.append)
    worker.start()
    worker.wait(3000)
    QTest.qWait(50)
    assert received == [expected]


def test_worker_emits_refresh_failed(qapp, monkeypatch) -> None:  # noqa: ANN001
    """ModelRefreshWorker 失败 → refresh_failed 信号带错误消息。"""
    from PySide6.QtTest import QTest

    from q_agent.llm.ollama import OllamaError
    from q_agent.ui import toolbar as tb_mod
    from q_agent.ui.toolbar import ModelRefreshWorker

    def boom(host: str = "", timeout: float = 0.0) -> list:  # noqa: ANN202
        raise OllamaError("无法连接 Ollama")

    monkeypatch.setattr(tb_mod, "list_models", boom)

    worker = ModelRefreshWorker()
    received: list[str] = []
    worker.refresh_failed.connect(received.append)
    worker.start()
    worker.wait(3000)
    QTest.qWait(50)
    assert received == ["无法连接 Ollama"]


def test_main_window_auto_refreshes_on_startup(qapp, monkeypatch) -> None:  # noqa: ANN001
    """MainWindow 构造后异步触发一次模型检测。"""
    from q_agent.ui import toolbar as tb_mod
    from q_agent.ui.main_window import MainWindow

    called: list[int] = []

    def fake_list_models(host: str = "", timeout: float = 0.0) -> list:  # noqa: ANN202
        called.append(1)
        return []

    monkeypatch.setattr(tb_mod, "list_models", fake_list_models)

    MainWindow()
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec()
    assert called, "MainWindow 启动应自动触发一次 list_models 调用"
