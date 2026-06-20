"""工具栏 + 模型下拉框单测（v0.0.5：本地/云端分组）。

覆盖：
    - Toolbar 可构造，初始占位"检测中..."且 disabled
    - _on_models_found 有本地模型：本地 header + 本地项 + 云端 header + 云端预置项
    - _on_models_found 无本地模型：本地 header + "未发现本地模型"占位 + 云端 header + 云端项
    - _on_refresh_failed：仅"未发现本地 LLM"占位，不加云端组
    - _on_combo_changed：header / placeholder 不 emit，真模型项 emit
    - current_model：占位 / header / 未选 返回 None；真模型返回模型名
    - ModelRefreshWorker：models_found / refresh_failed 信号触发
    - MainWindow 启动自动触发一次检测
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_toolbar_constructs_with_model_group(qapp) -> None:  # noqa: ANN001
    """Toolbar 含模型下拉框 + 刷新按钮，初始占位为"检测中..."且 disabled。"""
    from q_agent.ui.toolbar import PLACEHOLDER_DETECTING, Toolbar

    tb = Toolbar()
    assert tb.model_combo is not None
    assert tb.refresh_btn is not None
    assert tb.model_combo.count() == 1
    assert tb.model_combo.itemText(0) == PLACEHOLDER_DETECTING
    assert not tb.model_combo.isEnabled(), "初始检测中状态应 disabled"


def test_on_models_found_with_local_models(qapp) -> None:  # noqa: ANN001
    """收到本地模型列表 → 本地 header + 本地项 + 云端 header + 云端预置项。"""
    from q_agent.ui.toolbar import CLOUD_PRESET, HEADER_CLOUD, HEADER_LOCAL, Toolbar

    received: list[str] = []
    tb = Toolbar(status_callback=received.append)
    tb._on_models_found(["qwen2.5:7b", "llama3:8b"])

    # 总项数 = 1 本地 header + 2 本地模型 + 1 云端 header + 3 云端预置 = 7
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


def test_on_models_found_empty_local(qapp) -> None:  # noqa: ANN001
    """本地无模型 → 本地 header + "未发现本地模型"占位 + 云端组照常。"""
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

    # 1 本地 header + 1 占位 + 1 云端 header + 3 云端 = 6
    assert tb.model_combo.count() == 1 + 1 + 1 + len(CLOUD_PRESET)
    assert tb.model_combo.itemText(0) == HEADER_LOCAL
    assert tb.model_combo.itemText(1) == PLACEHOLDER_NO_LOCAL_MODEL
    assert tb.model_combo.itemText(2) == HEADER_CLOUD
    assert tb.model_combo.itemText(3) == "gpt-4o (OpenAI)"
    assert tb.model_combo.isEnabled()
    # 默认应选中云端首个可选项
    assert tb.current_model() == "gpt-4o (OpenAI)"
    assert any("云端" in msg or "无模型" in msg for msg in received)


def test_on_refresh_failed(qapp) -> None:  # noqa: ANN001
    """worker 失败 → 仅"未发现本地 LLM"占位项，不加云端组。"""
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
    tb._on_models_found(["qwen2.5:7b", "llama3:8b"])
    selected: list[str] = []
    tb.model_selected.connect(selected.append)
    # index 2 是 llama3:8b
    tb.model_combo.setCurrentIndex(2)
    assert selected == ["llama3:8b"]


def test_combo_changed_header_does_not_emit(qapp) -> None:  # noqa: ANN001
    """切换到 header（disabled）项不 emit。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found(["qwen2.5:7b"])
    selected: list[str] = []
    tb.model_selected.connect(selected.append)
    # 尝试切到本地 header（index 0）
    tb.model_combo.setCurrentIndex(0)
    assert selected == []


def test_combo_changed_cloud_emits(qapp) -> None:  # noqa: ANN001
    """切换到云端模型项 → emit model_selected（带云端名）。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found(["qwen2.5:7b"])
    selected: list[str] = []
    tb.model_selected.connect(selected.append)
    # 索引：0 本地header / 1 qwen / 2 云端header / 3 gpt-4o / 4 claude / 5 gemini
    tb.model_combo.setCurrentIndex(4)
    assert selected == ["claude-opus-4-7 (Anthropic)"]


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
    tb._on_models_found(["qwen2.5:7b"])
    # 强行设 currentIndex 到 header（实际 UI 阻止，但代码层验证）
    tb.model_combo.setCurrentIndex(0)
    # current_model 内部检查 isEnabled，header disabled 返回 None
    assert tb.current_model() is None


def test_current_model_returns_local(qapp) -> None:  # noqa: ANN001
    """真模型选中后 current_model 返回模型名。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found(["qwen2.5:7b"])
    tb.model_combo.setCurrentIndex(1)
    assert tb.current_model() == "qwen2.5:7b"


def test_current_model_returns_cloud(qapp) -> None:  # noqa: ANN001
    """云端模型选中后 current_model 返回云端名。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found(["qwen2.5:7b"])
    tb.model_combo.setCurrentIndex(3)  # gpt-4o (OpenAI)
    assert tb.current_model() == "gpt-4o (OpenAI)"


def test_worker_emits_models_found(qapp, monkeypatch) -> None:  # noqa: ANN001
    """ModelRefreshWorker 成功 → models_found 信号带列表。"""
    from PySide6.QtTest import QTest

    from q_agent.ui import toolbar as tb_mod
    from q_agent.ui.toolbar import ModelRefreshWorker

    monkeypatch.setattr(
        tb_mod,
        "list_models",
        lambda host="http://localhost:11434", timeout=2.0: ["qwen2.5:7b"],
    )

    worker = ModelRefreshWorker()
    received: list[list] = []
    worker.models_found.connect(received.append)
    worker.start()
    worker.wait(3000)
    QTest.qWait(50)
    assert received == [["qwen2.5:7b"]]


def test_worker_emits_refresh_failed(qapp, monkeypatch) -> None:  # noqa: ANN001
    """ModelRefreshWorker 失败 → refresh_failed 信号带错误消息。"""
    from PySide6.QtTest import QTest

    from q_agent.llm.ollama import OllamaError
    from q_agent.ui import toolbar as tb_mod
    from q_agent.ui.toolbar import ModelRefreshWorker

    def boom(host: str = "", timeout: float = 0.0) -> list[str]:
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

    def fake_list_models(host: str = "", timeout: float = 0.0) -> list[str]:
        called.append(1)
        return []

    monkeypatch.setattr(tb_mod, "list_models", fake_list_models)

    MainWindow()
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec()
    assert called, "MainWindow 启动应自动触发一次 list_models 调用"
