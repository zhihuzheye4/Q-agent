"""顶部菜单栏：文件 / 监控 / 帮助。

行为：
    - 文件菜单：退出
    - 监控菜单（v0.0.15 新增）：打开监控 + 关闭监控（triggered → callback）
    - 帮助菜单：关于（QMessageBox 弹窗）

v0.0.15 贴纸式扩展（CLAUDE.md 第二十一节）：
    - monitor_callback / close_callback 作为构造参数注入，菜单只负责触发回调
    - 不侵入既有 _build_file_menu / _build_help_menu，新增 _build_monitor_menu 独立方法

v0.0.15 修订：菜单加"关闭监控"项，用户反馈"打开后无法关闭"。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox


class MenuBar:
    """菜单栏控制器（不继承 QMenuBar，直接调 window.menuBar()）。

    monitor_callback：v0.0.15 新增，"打开监控"菜单项触发时调用
        （MainWindow 注入 _open_hardware_monitor）。
    close_callback：v0.0.15 修订新增，"关闭监控"菜单项触发时调用
        （MainWindow 注入 _close_hardware_monitor）。
    """

    def __init__(
        self,
        window: QMainWindow,
        monitor_callback: Callable[[], None] | None = None,
        close_callback: Callable[[], None] | None = None,
    ) -> None:
        self.window = window
        self._monitor_callback = monitor_callback
        self._close_callback = close_callback
        self._build_file_menu()
        self._build_monitor_menu()
        self._build_help_menu()

    def _build_file_menu(self) -> None:
        menu = self.window.menuBar().addMenu("文件")

        exit_action = QAction("退出", self.window)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.window.close)
        menu.addAction(exit_action)

    def _build_monitor_menu(self) -> None:
        """v0.0.15 新增：监控菜单，"打开监控"+"关闭监控"两项。"""
        menu = self.window.menuBar().addMenu("监控")

        open_action = QAction("打开监控", self.window)
        open_action.setShortcut("Ctrl+M")
        if self._monitor_callback is not None:
            open_action.triggered.connect(self._monitor_callback)
        else:
            open_action.setEnabled(False)
        menu.addAction(open_action)

        menu.addSeparator()

        close_action = QAction("关闭监控", self.window)
        close_action.setShortcut("Ctrl+W")
        if self._close_callback is not None:
            close_action.triggered.connect(self._close_callback)
        else:
            close_action.setEnabled(False)
        menu.addAction(close_action)

    def _build_help_menu(self) -> None:
        menu = self.window.menuBar().addMenu("帮助")

        about_action = QAction("关于 Q-agent", self.window)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

    def _show_about(self) -> None:
        QMessageBox.information(
            self.window,
            "关于 Q-agent",
            "Q-agent v0.0.16\n\n"
            "类似 Claude Code 的桌面端 AI 工具\n"
            "对接本地 LLM\n\n"
            "当前：活 UI 空壳 + 硬件监控独立窗口 + 新建/清空按钮接通\n"
            "界面可跳转、按钮可按，核心功能逐步填充中。",
        )
