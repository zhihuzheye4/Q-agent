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
    """MainWindow 可构造，4 tab + 4 stack 页。"""
    from q_agent.ui.main_window import MainWindow

    w = MainWindow()
    assert w.windowTitle() == "Q-agent"
    assert w.sidebar.count() == 4, "侧边栏应有 4 个 tab"
    assert w.stack.count() == 4, "主内容区应有 4 个页面"


def test_sidebar_tab_switches_stack(qapp) -> None:  # noqa: ANN001
    """点击侧边栏 tab 切换主内容区。"""
    from q_agent.ui.main_window import MainWindow

    w = MainWindow()
    for i in range(4):
        w.sidebar.setCurrentRow(i)
        assert w.stack.currentIndex() == i, f"侧边栏 {i} 未正确切换 stack"


def test_chat_page_send_echos(qapp) -> None:  # noqa: ANN001
    """对话 tab：发送按钮把输入文本 echo 到消息流。"""
    from q_agent.ui.main_window import MainWindow

    w = MainWindow()
    chat = w.chat_page
    initial = len(chat._messages)
    chat.input.setText("测试消息")
    chat._on_send_clicked()
    assert len(chat._messages) == initial + 2, "应追加 user + ai 各一条"
    assert chat._messages[-2][0] == "user"
    assert chat._messages[-2][1] == "测试消息"
    assert chat._messages[-1][0] == "ai"
    assert "测试消息" in chat._messages[-1][1]
    assert chat.input.text() == "", "发送后输入框应清空"


def test_chat_page_send_disabled_on_empty(qapp) -> None:  # noqa: ANN001
    """输入框为空时发送按钮 disabled。"""
    from q_agent.ui.main_window import MainWindow

    w = MainWindow()
    assert not w.chat_page.send_btn.isEnabled(), "空输入框应 disabled 发送按钮"
    w.chat_page.input.setText("有内容")
    assert w.chat_page.send_btn.isEnabled(), "有内容应启用发送按钮"
    w.chat_page.input.clear()
    assert not w.chat_page.send_btn.isEnabled(), "清空后应再次 disabled"


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
