"""UI 模块 import 与加载测试。

约束：
    - PySide6 不可用时整文件 skip（pytest.importorskip）
    - 用 QT_QPA_PLATFORM=minimal 避免 CI 弹窗
    - 仅测模块加载与基础组件创建，不测交互逻辑
"""

from __future__ import annotations

import os

import pytest

# 整文件级 skip：无 PySide6 时
pytest.importorskip("PySide6")

# 强制离屏渲染（CI 环境无显示）
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")


@pytest.fixture(scope="module")
def qapp():
    """共享 QApplication 实例（pytest-qt 风格）。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_icons_module_loads() -> None:
    """icons 模块可 import 且 manifest 可加载。"""
    from q_agent.ui.icons import ICONS_DIR, load_manifest

    assert ICONS_DIR.exists(), f"图标目录不存在：{ICONS_DIR}"
    manifest = load_manifest()
    assert manifest["version"], "manifest 缺 version"
    assert len(manifest["icons"]) > 0, "manifest 无图标"


def test_load_icon_returns_qicon() -> None:
    """方案 D：load_icon 返回非空 QIcon（SVG 文件存在时）。"""
    from PySide6.QtGui import QIcon

    from q_agent.ui.icons import load_icon

    icon = load_icon("chat")
    assert isinstance(icon, QIcon)
    assert not icon.isNull(), "chat 图标加载失败（SVG 文件缺失？）"


def test_load_icon_missing_returns_empty() -> None:
    """不存在的图标返回空 QIcon（不崩）。"""
    from PySide6.QtGui import QIcon

    from q_agent.ui.icons import load_icon

    icon = load_icon("nonexistent-icon-xyz")
    assert isinstance(icon, QIcon)
    assert icon.isNull(), "不存在的图标应返回空 QIcon"


def test_theme_qss_nonempty() -> None:
    """DARK_QSS 是非空字符串。"""
    from q_agent.ui.theme import DARK_QSS

    assert isinstance(DARK_QSS, str)
    assert len(DARK_QSS) > 100, "DARK_QSS 太短，可能未生成"
    assert "#0F172A" in DARK_QSS, "DARK_QSS 缺 Background 色值"


def test_theme_color_constants() -> None:
    """设计 token 常量齐全。"""
    from q_agent.ui.theme import (
        COLOR_ACCENT,
        COLOR_BACKGROUND,
        COLOR_BORDER,
        COLOR_DESTRUCTIVE,
        COLOR_FOREGROUND,
        COLOR_MUTED,
        COLOR_PRIMARY,
        COLOR_RING,
        COLOR_SECONDARY,
    )

    assert all(
        c.startswith("#") and len(c) == 7
        for c in [
            COLOR_PRIMARY,
            COLOR_SECONDARY,
            COLOR_ACCENT,
            COLOR_BACKGROUND,
            COLOR_FOREGROUND,
            COLOR_MUTED,
            COLOR_BORDER,
            COLOR_DESTRUCTIVE,
            COLOR_RING,
        ]
    ), "设计 token 颜色格式错误"


def test_main_window_constructs(qapp) -> None:  # noqa: ANN001
    """MainWindow 可构造，4 tab + 4 stack 页 + 菜单栏注入 monitor_callback。"""
    from q_agent.ui.main_window import MainWindow

    w = MainWindow()
    assert w.windowTitle() == "Q-agent"
    # v0.0.14：sidebar 恢复 QListWidget 子类，count() 直接可用
    assert w.sidebar.count() == 4, "侧边栏应有 4 个 tab"
    assert w.stack.count() == 4, "主内容区应有 4 个页面"
    # v0.0.15：hardware_monitor 从 left panel 移除，独立窗口由 menu 触发
    assert not hasattr(w, "hardware_monitor"), "v0.0.15 应移除 w.hardware_monitor 属性"
    # v0.0.15：menu 注入 monitor_callback / close_callback，_hw_window 初始为 None
    assert w._hw_window is None, "_hw_window 应初始为 None"
    assert w.menu._monitor_callback is not None, "menu 应注入 monitor_callback"
    assert w.menu._close_callback is not None, "menu 应注入 close_callback"


def test_sidebar_tab_switches_stack(qapp) -> None:  # noqa: ANN001
    """点击侧边栏 tab 切换主内容区。"""
    from q_agent.ui.main_window import MainWindow

    w = MainWindow()
    for i in range(4):
        # v0.0.14：sidebar 恢复 QListWidget 子类，setCurrentRow 直接可用
        w.sidebar.setCurrentRow(i)
        assert w.stack.currentIndex() == i, f"侧边栏 {i} 未正确切换 stack"


def test_chat_page_send_appends_user_and_pending_ai(qapp, monkeypatch) -> None:  # noqa: ANN001
    """对话 tab：发送按钮触发 ChatWorker，追加 user 消息 + pending AI 气泡（不污染历史）。"""
    from q_agent.ui.main_window import MainWindow

    class _SignalStub:
        def __init__(self) -> None:
            self._slots: list = []

        def connect(self, slot: object) -> None:
            self._slots.append(slot)

        def emit(self, *args: object) -> None:
            for s in self._slots:
                s(*args)

    class FakeWorker:
        chunk_received = _SignalStub()
        chat_failed = _SignalStub()
        chat_done = _SignalStub()
        chat_aborted = _SignalStub()

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr("q_agent.ui.pages.chat_page.ChatWorker", FakeWorker)

    w = MainWindow()
    chat = w.chat_page
    chat.set_group_provider(lambda: "local")
    initial = len(chat._messages)
    chat.input.setPlainText("测试消息")
    chat._on_send_clicked()
    # 仅 user 消息入历史（pending AI 气泡 append_to_history=False）
    assert len(chat._messages) == initial + 1, "应仅追加 user 一条（AI 等 chat_done）"
    assert chat._messages[-1] == ("user", "测试消息", None)
    assert chat.input.toPlainText() == "", "发送后输入框应清空"


def test_chat_page_send_disabled_on_empty(qapp) -> None:  # noqa: ANN001
    """输入框为空时发送按钮 disabled；有内容 + local 分组时启用。"""
    from q_agent.ui.main_window import MainWindow

    w = MainWindow()
    # 默认未选模型 → group=None → disabled
    assert not w.chat_page.send_btn.isEnabled(), "未选模型应 disabled 发送按钮"
    w.chat_page.set_group_provider(lambda: "local")
    w.chat_page.input.setPlainText("有内容")
    w.chat_page.update_send_enabled("local")
    assert w.chat_page.send_btn.isEnabled(), "local 分组 + 有内容应启用发送按钮"
    w.chat_page.input.clear()
    w.chat_page.update_send_enabled("local")
    assert not w.chat_page.send_btn.isEnabled(), "清空后应再次 disabled"


def test_chat_page_ai_bubble_includes_model_name(qapp, monkeypatch) -> None:  # noqa: ANN001
    """AI 气泡 _messages 元组含模型名，model_provider 返回真模型名时记录到元组。"""
    from q_agent.ui.pages.chat_page import ChatPage

    class _SignalStub:
        def __init__(self) -> None:
            self._slots: list = []

        def connect(self, slot: object) -> None:
            self._slots.append(slot)

        def emit(self, *args: object) -> None:
            for s in self._slots:
                s(*args)

    class FakeWorker:
        chunk_received = _SignalStub()
        chat_failed = _SignalStub()
        chat_done = _SignalStub()
        chat_aborted = _SignalStub()

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr("q_agent.ui.pages.chat_page.ChatWorker", FakeWorker)

    chat = ChatPage()
    chat.set_model_provider(lambda: "qwen2.5:7b")
    chat.set_group_provider(lambda: "local")
    chat.input.setPlainText("测试")
    chat._on_send_clicked()
    # 模拟 ChatWorker 完成：完整回复入历史
    chat._pending_text = "完整回复"
    chat._pending_model_name = "qwen2.5:7b"
    chat._on_chat_done()
    last = chat._messages[-1]
    assert last[0] == "ai"
    assert last[2] == "qwen2.5:7b", f"AI 消息元组应含模型名，实际：{last}"


def test_chat_page_ai_bubble_uses_placeholder_when_no_model(qapp, monkeypatch) -> None:  # noqa: ANN001
    """model_provider 返回 None 时 AI 气泡记录占位文本。"""
    from q_agent.ui.pages.chat_page import NO_MODEL_TEXT, ChatPage

    class _SignalStub:
        def __init__(self) -> None:
            self._slots: list = []

        def connect(self, slot: object) -> None:
            self._slots.append(slot)

        def emit(self, *args: object) -> None:
            for s in self._slots:
                s(*args)

    class FakeWorker:
        chunk_received = _SignalStub()
        chat_failed = _SignalStub()
        chat_done = _SignalStub()
        chat_aborted = _SignalStub()

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr("q_agent.ui.pages.chat_page.ChatWorker", FakeWorker)

    chat = ChatPage()
    # 不注入 model_provider → _current_model_name 返回 NO_MODEL_TEXT
    chat.set_group_provider(lambda: "local")
    chat.input.setPlainText("测试")
    chat._on_send_clicked()
    chat._pending_text = "回复"
    chat._pending_model_name = NO_MODEL_TEXT
    chat._on_chat_done()
    last = chat._messages[-1]
    assert last[0] == "ai"
    assert last[2] == NO_MODEL_TEXT


def test_chat_page_user_bubble_has_no_model_name(qapp, monkeypatch) -> None:  # noqa: ANN001
    """用户气泡元组 model_name 字段为 None。"""
    from q_agent.ui.pages.chat_page import ChatPage

    class _SignalStub:
        def __init__(self) -> None:
            self._slots: list = []

        def connect(self, slot: object) -> None:
            self._slots.append(slot)

        def emit(self, *args: object) -> None:
            for s in self._slots:
                s(*args)

    class FakeWorker:
        chunk_received = _SignalStub()
        chat_failed = _SignalStub()
        chat_done = _SignalStub()
        chat_aborted = _SignalStub()

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr("q_agent.ui.pages.chat_page.ChatWorker", FakeWorker)

    chat = ChatPage()
    chat.set_model_provider(lambda: "qwen2.5:7b")
    chat.set_group_provider(lambda: "local")
    chat.input.setPlainText("测试")
    chat._on_send_clicked()
    # 最后一条是 user 消息（pending AI 不入历史）
    user_msg = chat._messages[-1]
    assert user_msg[0] == "user"
    assert user_msg[2] is None, "用户气泡不应带模型名"


def test_settings_page_widgets_exist(qapp) -> None:  # noqa: ANN001
    """设置 tab 含全部预期控件。"""
    from q_agent.ui.main_window import MainWindow

    w = MainWindow()
    s = w.settings_page
    assert s.dark_mode_check.isChecked(), "暗色模式默认开"
    assert s.lang_combo.count() > 0, "语言下拉有项"
    assert s.llm_backend_combo.count() > 0, "LLM 后端下拉有项"
    assert s.font_size_spin.value() == 14, "字号默认 14"
    assert s.safety_check.isChecked(), "危险命令黑名单默认开"
    assert s.root_protect_check.isChecked(), "根目录保护默认开"


def test_cli_ui_subcommand_registered() -> None:
    """CLI ui 子命令注册到 argparse。"""
    from q_agent.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["ui"])
    assert args.cmd == "ui"
