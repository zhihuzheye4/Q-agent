"""顶部菜单栏：文件 / 帮助。

行为（活 UI 空壳）：
    - 文件菜单：退出
    - 帮助菜单：关于（QMessageBox 弹窗）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox


class MenuBar:
    """菜单栏控制器（不继承 QMenuBar，直接调 window.menuBar()）。"""

    def __init__(self, window: QMainWindow) -> None:
        self.window = window
        self._build_file_menu()
        self._build_help_menu()

    def _build_file_menu(self) -> None:
        menu = self.window.menuBar().addMenu("文件")

        exit_action = QAction("退出", self.window)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.window.close)
        menu.addAction(exit_action)

    def _build_help_menu(self) -> None:
        menu = self.window.menuBar().addMenu("帮助")

        about_action = QAction("关于 Q-agent", self.window)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

    def _show_about(self) -> None:
        QMessageBox.information(
            self.window,
            "关于 Q-agent",
            "Q-agent v0.0.1\n\n"
            "类似 Claude Code 的桌面端 AI 工具\n"
            "对接本地 LLM\n\n"
            "当前：活 UI 空壳\n"
            "界面可跳转、按钮可按，无实际功能。",
        )
