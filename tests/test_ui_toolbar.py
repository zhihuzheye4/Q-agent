"""工具栏 + 模型下拉框单测。

覆盖：
    - Toolbar 可构造，含 model_combo + refresh_btn
    - _on_models_found 有模型：填下拉、启用、状态栏回调
    - _on_models_found 无模型：占位项、disabled、状态栏提示
    - _on_refresh_failed：占位项、disabled、状态栏提示
    - _on_combo_changed：占位项不 emit model_selected；真模型项 emit
    - current_model：占位返回 None；真模型返回模型名
    - ModelRefreshWorker：models_found / refresh_failed 信号触发
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
    """Toolbar 含模型下拉框 + 刷新按钮，初始占位为"检测中..."。"""
    from q_agent.ui.toolbar import PLACEHOLDER_DETECTING, Toolbar

    tb = Toolbar()
    assert tb.model_combo is not None
    assert tb.refresh_btn is not None
    assert tb.model_combo.count() == 1
    assert tb.model_combo.itemText(0) == PLACEHOLDER_DETECTING
    assert not tb.model_combo.isEnabled(), "初始检测中状态应 disabled"


def test_on_models_found_with_models(qapp) -> None:  # noqa: ANN001
    """收到模型列表 → 填下拉、启用、回调状态。"""
    from q_agent.ui.toolbar import Toolbar

    received: list[str] = []
    tb = Toolbar(status_callback=received.append)
    tb._on_models_found(["qwen2.5:7b", "llama3:8b"])
    assert tb.model_combo.count() == 2
    assert tb.model_combo.itemText(0) == "qwen2.5:7b"
    assert tb.model_combo.itemText(1) == "llama3:8b"
    assert tb.model_combo.isEnabled()
    assert any("已发现" in msg for msg in received)


def test_on_models_found_empty(qapp) -> None:  # noqa: ANN001
    """收到空列表 → 占位项、disabled、回调提示。"""
    from q_agent.ui.toolbar import PLACEHOLDER_EMPTY, Toolbar

    received: list[str] = []
    tb = Toolbar(status_callback=received.append)
    tb._on_models_found([])
    assert tb.model_combo.count() == 1
    assert tb.model_combo.itemText(0) == PLACEHOLDER_EMPTY
    assert not tb.model_combo.isEnabled()
    assert any("未发现" in msg for msg in received)


def test_on_refresh_failed(qapp) -> None:  # noqa: ANN001
    """worker 失败 → 占位项、disabled、回调含失败消息。"""
    from q_agent.ui.toolbar import PLACEHOLDER_EMPTY, Toolbar

    received: list[str] = []
    tb = Toolbar(status_callback=received.append)
    tb._on_refresh_failed("连接被拒绝")
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
    tb.model_combo.setCurrentIndex(1)
    assert selected == ["llama3:8b"]


def test_combo_changed_placeholder_does_not_emit(qapp) -> None:  # noqa: ANN001
    """占位项切换不 emit。"""
    from q_agent.ui.toolbar import PLACEHOLDER_EMPTY, Toolbar

    tb = Toolbar()
    tb._on_models_found([])
    selected: list[str] = []
    tb.model_selected.connect(selected.append)
    tb.model_combo.setCurrentIndex(0)
    assert selected == []


def test_current_model_returns_none_for_placeholder(qapp) -> None:  # noqa: ANN001
    """占位状态 current_model 返回 None。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found([])
    assert tb.current_model() is None


def test_current_model_returns_name_for_real(qapp) -> None:  # noqa: ANN001
    """真模型选中后 current_model 返回模型名。"""
    from q_agent.ui.toolbar import Toolbar

    tb = Toolbar()
    tb._on_models_found(["qwen2.5:7b"])
    tb.model_combo.setCurrentIndex(0)
    assert tb.current_model() == "qwen2.5:7b"


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
    QTest.qWait(50)  # 让 queued 信号在主线程事件循环里派发
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
    """MainWindow 构造后异步触发一次模型检测（worker 启动）。

    用 monkeypatch 让 list_models 立即返回空，避免真实网络访问。
    """
    from q_agent.ui import toolbar as tb_mod
    from q_agent.ui.main_window import MainWindow

    called: list[int] = []

    def fake_list_models(host: str = "", timeout: float = 0.0) -> list[str]:
        called.append(1)
        return []

    monkeypatch.setattr(tb_mod, "list_models", fake_list_models)

    w = MainWindow()
    # 触发 QTimer.singleShot(100) 内的 refresh_models —— 等待 worker 跑完
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec()
    assert called, "MainWindow 启动应自动触发一次 list_models 调用"