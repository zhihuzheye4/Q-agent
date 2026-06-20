"""主窗口：QMainWindow 主框架。

结构（v0.0.14 贴纸式重构）：
    +---------------------------+
    | menu_bar                   |
    +---------------------------+
    | toolbar                    |
    +---+-----------------------+
    | L |   QStackedWidget      |
    | e |   (ChatPage /          |
    | f |    SkillsPage /        |
    | t |    MemoryPage /         |
    | P |    SettingsPage)       |
    | a |                        |
    | n |                        |
    | e |                        |
    | l |                        |
    +---+-----------------------+
    | status_bar                 |
    +---------------------------+

Left Panel（v0.0.14 新增，贴纸式挂载点）：
    +---------------+
    | Sidebar       |  ← 4 tab（对话/技能/记忆/设置）stretch=1
    | (QListWidget) |
    +---------------+
    | HardwareMonitor|  ← 硬件监控曲线 4 折线 60s 历史，固定 160px
    +---------------+
    整体 fixed 200px 宽，放进水平布局左侧

v0.0.14 贴纸式原则（CLAUDE.md 第二十一节）：
    - Sidebar 保持 v0.0.9 QListWidget 子类原貌，零改动
    - HardwareMonitor 独立 widget，由 MainWindow left panel 一行 addWidget 挂载
    - 删除/新增硬件监控只动 HardwareMonitor 文件 + MainWindow 一行挂载，Sidebar 零影响
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from q_agent.ui.hardware_monitor import HardwareMonitor
from q_agent.ui.menu_bar import MenuBar
from q_agent.ui.pages.chat_page import ChatPage
from q_agent.ui.pages.memory_page import MemoryPage
from q_agent.ui.pages.settings_page import SettingsPage
from q_agent.ui.pages.skills_page import SkillsPage
from q_agent.ui.sidebar import SIDEBAR_WIDTH, Sidebar
from q_agent.ui.theme import apply_theme
from q_agent.ui.toolbar import Toolbar

# left panel 固定宽度（含 sidebar + 底部硬件监控，等于 sidebar 宽度）
LEFT_PANEL_WIDTH = SIDEBAR_WIDTH


class MainWindow(QMainWindow):
    """Q-agent 主窗口（v0.0.14：left panel 贴纸式挂载 sidebar + hardware_monitor）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Q-agent")
        self.resize(1200, 800)
        self._build_layout()

    def _build_layout(self) -> None:
        # 中央容器：水平布局 [left_panel | 主内容区]
        central = QWidget(self)
        from PySide6.QtWidgets import QHBoxLayout

        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # left panel（贴纸式挂载点：sidebar stretch=1 + hardware_monitor 底部固定 160px）
        left_panel = QWidget(central)
        left_panel.setFixedWidth(LEFT_PANEL_WIDTH)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.sidebar = Sidebar(left_panel)
        left_layout.addWidget(self.sidebar, stretch=1)

        self.hardware_monitor = HardwareMonitor(left_panel)
        left_layout.addWidget(self.hardware_monitor)

        left_panel.setLayout(left_layout)
        h_layout.addWidget(left_panel)

        # 主内容区（QStackedWidget）
        self.stack = QStackedWidget(central)
        self.chat_page = ChatPage()
        self.skills_page = SkillsPage()
        self.memory_page = MemoryPage()
        self.settings_page = SettingsPage()
        self.stack.addWidget(self.chat_page)
        self.stack.addWidget(self.skills_page)
        self.stack.addWidget(self.memory_page)
        self.stack.addWidget(self.settings_page)
        h_layout.addWidget(self.stack, stretch=1)

        central.setLayout(h_layout)
        self.setCentralWidget(central)

        # 侧边栏切换 → 主内容区切换
        self.sidebar.tab_changed.connect(self.stack.setCurrentIndex)

        # 工具栏
        self.toolbar = Toolbar(self, status_callback=self._show_status)
        self.addToolBar(self.toolbar)

        # ChatPage 注入模型名 + 分组提供器 + host
        self.chat_page.set_model_provider(self.toolbar.current_model)
        self.chat_page.set_group_provider(self.toolbar.current_model_group)
        self.chat_page.set_host("http://localhost:11434")

        # toolbar 模型分组变化 → chat_page 更新发送按钮可用状态
        self.toolbar.model_group_changed.connect(self.chat_page.update_send_enabled)

        # toolbar 用户切换模型 → chat_page 清空当前对话 + 系统提示（v0.0.9 新增）
        self.toolbar.model_selected.connect(self.chat_page._on_model_changed)

        # 菜单栏
        self.menu = MenuBar(self)

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 启动后自动检测一次本地 Ollama 模型（延迟 100ms 让 UI 先绘制）
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self.toolbar.refresh_models)
        # 检测完成后会触发 model_group_changed，但启动时下拉框初始占位 disabled，
        # 主动调一次让 chat_page 初始禁用发送按钮（与 toolbar 初始状态对齐）
        QTimer.singleShot(150, self._sync_send_enabled)
        # 启动硬件监控 worker（延迟 200ms 让 UI 先绘制，避免首帧空白）
        QTimer.singleShot(200, self.hardware_monitor.start)

    def closeEvent(self, event: QCloseEvent) -> None:
        """窗口关闭时优雅停止 hardware_monitor worker，避免线程悬挂。"""
        self.hardware_monitor.stop()
        super().closeEvent(event)

    def _sync_send_enabled(self) -> None:
        """启动后主动同步一次发送按钮状态（与 toolbar 当前选中项对齐）。"""
        self.chat_page.update_send_enabled(self.toolbar.current_model_group())

    def _show_status(self, text: str) -> None:
        self.statusBar().showMessage(text, 5000)


def run_app() -> int:
    """启动 Q-agent UI 主循环。

    延迟 import 让 cmd_ui() 调用时才装载 PySide6。
    返回 app.exec() 的退出码。
    """
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()
