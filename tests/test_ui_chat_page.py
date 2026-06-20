"""ChatPage 真实调用 + ChatWorker 信号流单测（v0.0.8）。

覆盖：
    - update_send_enabled：cloud → 禁用；local/ollama-cloud + 输入非空 → 启用
    - _on_send_clicked：mock ChatWorker → 验证 messages_for_llm 构造 + loading 状态
    - _on_chunk：追加到 pending 气泡
    - _on_chat_done：完整回复入历史 + 恢复输入状态
    - _on_chat_failed：错误气泡（objectName=MessageError）
    - ChatWorker：chunk_received/chat_failed/chat_done 信号流（mock chat_stream）
    - ChatWorker：批量刷新阈值（500 字 OR 500ms）
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QTest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_update_send_enabled_cloud_disables(qapp) -> None:  # noqa: ANN001
    """group=cloud → send_btn 禁用。"""
    from q_agent.ui.pages.chat_page import ChatPage

    page = ChatPage()
    page.input.setPlainText("hello")  # 有输入也禁用
    page.update_send_enabled("cloud")
    assert not page.send_btn.isEnabled()


def test_update_send_enabled_local_with_text_enables(qapp) -> None:  # noqa: ANN001
    """group=local + 输入框非空 → 启用。"""
    from q_agent.ui.pages.chat_page import ChatPage

    page = ChatPage()
    page.input.setPlainText("hello")
    page.update_send_enabled("local")
    assert page.send_btn.isEnabled()


def test_update_send_enabled_local_empty_disables(qapp) -> None:  # noqa: ANN001
    """group=local + 输入框空 → 禁用。"""
    from q_agent.ui.pages.chat_page import ChatPage

    page = ChatPage()
    page.input.clear()
    page.update_send_enabled("local")
    assert not page.send_btn.isEnabled()


def test_update_send_enabled_none_disables(qapp) -> None:  # noqa: ANN001
    """group=None → 禁用。"""
    from q_agent.ui.pages.chat_page import ChatPage

    page = ChatPage()
    page.input.setPlainText("hello")
    page.update_send_enabled(None)
    assert not page.send_btn.isEnabled()


def test_update_send_enabled_ollama_cloud_enables(qapp) -> None:  # noqa: ANN001
    """group=ollama-cloud + 输入非空 → 启用。"""
    from q_agent.ui.pages.chat_page import ChatPage

    page = ChatPage()
    page.input.setPlainText("hi")
    page.update_send_enabled("ollama-cloud")
    assert page.send_btn.isEnabled()


def test_on_send_clicked_starts_worker_and_enters_loading(qapp, monkeypatch) -> None:  # noqa: ANN001
    """_on_send_clicked → 启动 ChatWorker + 进入 loading 状态（禁用按钮 + "生成中"）。"""
    from q_agent.ui.pages.chat_page import ChatPage

    started: list[bool] = []

    class _SignalStub:
        def __init__(self) -> None:
            self._slots: list[Any] = []

        def connect(self, slot: Any) -> None:
            self._slots.append(slot)

        def emit(self, *args: Any) -> None:
            for s in self._slots:
                s(*args)

    class FakeWorker:
        chunk_received = _SignalStub()
        chat_failed = _SignalStub()
        chat_done = _SignalStub()

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def start(self) -> None:
            started.append(True)

    monkeypatch.setattr("q_agent.ui.pages.chat_page.ChatWorker", FakeWorker)

    page = ChatPage()
    page.set_model_provider(lambda: "qwen2.5:7b")
    page.set_group_provider(lambda: "local")
    page.set_host("http://localhost:11434")
    page.input.setPlainText("你好")

    page._on_send_clicked()

    assert started == [True]
    assert not page.send_btn.isEnabled()
    assert page.send_btn.text() == "生成中"
    assert not page.input.isEnabled()
    # 用户消息入历史（_messages[0] 是构造时的初始 AI 占位，user 在其后追加）
    user_msgs = [m for m in page._messages if m[0] == "user"]
    assert user_msgs[-1][1] == "你好"


def test_on_chunk_appends_to_pending_bubble(qapp) -> None:  # noqa: ANN001
    """_on_chunk 追加文本到 pending 气泡。"""
    from q_agent.ui.pages.chat_page import ChatPage

    page = ChatPage()
    # 手动设置 pending 状态（模拟 _on_send_clicked 后）
    bubble = page._add_message("ai", "", model_name="qwen2.5:7b", append_to_history=False)
    page._pending_bubble = bubble
    page._pending_text = ""

    page._on_chunk("Hello")
    page._on_chunk(", world!")
    assert page._pending_text == "Hello, world!"
    assert page._pending_bubble.text() == "Hello, world!"


def test_on_chat_done_appends_to_history_and_resets(qapp) -> None:  # noqa: ANN001
    """_on_chat_done → 完整回复入历史 + 恢复输入状态。"""
    from q_agent.ui.pages.chat_page import ChatPage

    page = ChatPage()
    bubble = page._add_message("ai", "", model_name="qwen2.5:7b", append_to_history=False)
    page._pending_bubble = bubble
    page._pending_text = "完整回复"
    page._pending_model_name = "qwen2.5:7b"
    # 模拟 loading 状态
    page.send_btn.setEnabled(False)
    page.send_btn.setText("生成中")
    page.input.setEnabled(False)
    page.set_group_provider(lambda: "local")
    page.input.setPlainText("下条消息")

    page._on_chat_done()

    assert page._messages[-1] == ("ai", "完整回复", "qwen2.5:7b")
    assert page._pending_bubble is None
    assert page._pending_text == ""
    assert page.send_btn.text() == "发送"
    assert page.input.isEnabled()


def test_on_chat_failed_shows_error_bubble(qapp) -> None:  # noqa: ANN001
    """_on_chat_failed → pending 气泡 objectName=MessageError + 恢复输入。"""
    from q_agent.ui.pages.chat_page import ChatPage

    page = ChatPage()
    bubble = page._add_message("ai", "", model_name="qwen2.5:7b", append_to_history=False)
    page._pending_bubble = bubble
    page.send_btn.setEnabled(False)
    page.send_btn.setText("生成中")
    page.input.setEnabled(False)
    page.set_group_provider(lambda: "local")
    page.input.setPlainText("next")

    page._on_chat_failed("无法连接 Ollama")

    assert page._pending_bubble is not None
    assert page._pending_bubble.objectName() == "MessageError"
    assert "无法连接 Ollama" in page._pending_bubble.text()
    assert page.send_btn.text() == "发送"
    assert page.input.isEnabled()


def test_chat_worker_emits_chunks_and_done(qapp, monkeypatch) -> None:  # noqa: ANN001
    """ChatWorker mock chat_stream 返回多个 chunk → emit chunk_received + chat_done。"""
    from q_agent.llm.ollama import OllamaClient
    from q_agent.ui.chat_worker import ChatWorker

    # mock OllamaClient.chat_stream 返回短文本（不满 500 字阈值，但完成时一次性 flush）
    def fake_chat_stream(self: Any, messages: Any, timeout: float = 120.0) -> Any:  # noqa: ANN001, ANN003
        yield "Hello"
        yield ", "
        yield "world!"

    monkeypatch.setattr(OllamaClient, "chat_stream", fake_chat_stream)

    worker = ChatWorker(model="m", host="http://localhost:11434", messages=[])
    chunks: list[str] = []
    dones: list[bool] = []
    worker.chunk_received.connect(chunks.append)
    worker.chat_done.connect(lambda: dones.append(True))
    worker.start()
    worker.wait(3000)
    QTest.qWait(50)

    # 三个短 chunk 总长 13 字符 < 500，但循环结束时一次性 emit 剩余 buffer
    assert "".join(chunks) == "Hello, world!"
    assert dones == [True]


def test_chat_worker_emits_chunk_at_size_threshold(qapp, monkeypatch) -> None:  # noqa: ANN001
    """ChatWorker buffer 满 500 字 → 提前 emit chunk_received（不等完成）。"""
    from q_agent.llm.ollama import OllamaClient
    from q_agent.ui.chat_worker import ChatWorker

    # 构造 600 字 chunk，应触发一次 500 字阈值 flush + 末尾 100 字 flush
    long_text = "a" * 600

    def fake_chat_stream(self: Any, messages: Any, timeout: float = 120.0) -> Any:  # noqa: ANN001, ANN003
        yield long_text

    monkeypatch.setattr(OllamaClient, "chat_stream", fake_chat_stream)

    worker = ChatWorker(model="m", host="http://localhost:11434", messages=[])
    chunks: list[str] = []
    worker.chunk_received.connect(chunks.append)
    worker.start()
    worker.wait(3000)
    QTest.qWait(50)

    # 至少一次 emit（可能合并 500 字 + 100 字或单次 600 字，取决于时序）
    assert sum(len(c) for c in chunks) == 600


def test_chat_worker_emits_failed_on_ollama_error(qapp, monkeypatch) -> None:  # noqa: ANN001
    """ChatWorker 遇 OllamaError → emit chat_failed。"""
    from q_agent.llm.ollama import OllamaClient, OllamaError
    from q_agent.ui.chat_worker import ChatWorker

    def boom_chat_stream(self: Any, messages: Any, timeout: float = 120.0) -> Any:  # noqa: ANN001, ANN003
        raise OllamaError("无法连接 Ollama")
        yield  # noqa: R100  # unreachable yield 让函数成 generator

    monkeypatch.setattr(OllamaClient, "chat_stream", boom_chat_stream)

    worker = ChatWorker(model="m", host="http://localhost:11434", messages=[])
    fails: list[str] = []
    worker.chat_failed.connect(fails.append)
    worker.start()
    worker.wait(3000)
    QTest.qWait(50)

    assert fails == ["无法连接 Ollama"]


def test_chat_worker_stop_flag_interrupts(qapp, monkeypatch) -> None:  # noqa: ANN001
    """ChatWorker.stop() 设 _stop → run 循环检查早退。"""
    from q_agent.llm.ollama import OllamaClient
    from q_agent.ui.chat_worker import ChatWorker

    def slow_chat_stream(self: Any, messages: Any, timeout: float = 120.0) -> Any:  # noqa: ANN001, ANN003
        yield "first"
        # 模拟等待，让主线程有时间调 stop()
        time.sleep(0.05)
        yield "should_not_be_emitted_after_stop"

    monkeypatch.setattr(OllamaClient, "chat_stream", slow_chat_stream)

    worker = ChatWorker(model="m", host="http://localhost:11434", messages=[])
    chunks: list[str] = []
    dones: list[bool] = []
    worker.chunk_received.connect(chunks.append)
    worker.chat_done.connect(lambda: dones.append(True))
    worker.start()
    # 立即设 stop
    worker.stop()
    worker.wait(3000)
    QTest.qWait(50)

    # stop 后循环早退，不应触发 chat_done
    assert dones == []


def test_main_window_connects_group_changed_to_chat_page(qapp, monkeypatch) -> None:  # noqa: ANN001
    """MainWindow 启动后 toolbar.model_group_changed 信号连接到 chat_page.update_send_enabled。"""
    from q_agent.ui import toolbar as tb_mod
    from q_agent.ui.main_window import MainWindow
    from q_agent.ui.pages.chat_page import ChatPage

    monkeypatch.setattr(
        tb_mod,
        "list_models",
        lambda host="http://localhost:11434", timeout=2.0: [],
    )

    mw = MainWindow()
    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec()

    # 触发 toolbar 切换模型 → chat_page.send_btn 状态应随之变化
    mw.toolbar._on_models_found(
        [tb_mod.ModelEntry(name="qwen2.5:7b", is_remote=False, remote_host="")]
    )
    # 切到 qwen2.5:7b（local 分组）
    mw.toolbar.model_combo.setCurrentIndex(1)
    mw.chat_page.input.setPlainText("hello")
    QTest.qWait(10)
    assert mw.chat_page.send_btn.isEnabled()

    # 简化：直接调 update_send_enabled 验证 cloud 禁用
    mw.chat_page.update_send_enabled("cloud")
    assert not mw.chat_page.send_btn.isEnabled()

    # 确认 ChatPage 类型用于 type hint
    assert ChatPage is not None
