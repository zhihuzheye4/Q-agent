"""主窗口：QMainWindow 主框架。

结构（v0.0.15 硬件监控独立窗口）：
    +---------------------------+
    | menu_bar（文件/监控/帮助）   |
    +---------------------------+
    | toolbar                    |
    +---+-----------------------+
    | S |   QStackedWidget      |
    | i |   (ChatPage /          |
    | d |    SkillsPage /        |
    | e |    MemoryPage /         |
    | b |    SettingsPage)       |
    | a |                        |
    | r |                        |
    +---+-----------------------+
    | status_bar                 |
    +---------------------------+

Left Panel（v0.0.15 简化）：
    +---------------+
    | Sidebar       |  ← 4 tab（对话/技能/记忆/设置）stretch=1
    | (QListWidget) |
    +---------------+
    整体 fixed 200px 宽，放进水平布局左侧

v0.0.15 变更（模块化迁移，CLAUDE.md 第二十一节）：
    - 硬件监控从 left panel 底部常驻 → 独立窗口（menu_bar "监控"菜单 triggered 弹出）
    - left panel 只剩 sidebar（恢复 v0.0.9 前的极简结构）
    - MainWindow 新增 _open_hardware_monitor() + 持有 _hw_window 引用，closeEvent 关闭
    - hardware_monitor.py 只保留 Worker + 常量，HardwareMonitorWindow 独立 widget 文件
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from q_agent.ui.tool_history_window import ToolHistoryWindow

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from q_agent.ui.hardware_monitor_window import HardwareMonitorWindow
from q_agent.ui.menu_bar import MenuBar
from q_agent.ui.pages.chat_page import ChatPage
from q_agent.ui.pages.memory_page import MemoryPage
from q_agent.ui.pages.settings_page import SettingsPage
from q_agent.ui.pages.skills_page import SkillsPage
from q_agent.ui.sidebar import SIDEBAR_WIDTH, Sidebar
from q_agent.ui.theme import apply_theme
from q_agent.ui.toolbar import Toolbar

# left panel 固定宽度（仅 sidebar，等于 sidebar 宽度）
LEFT_PANEL_WIDTH = SIDEBAR_WIDTH


class MainWindow(QMainWindow):
    """Q-agent 主窗口（v0.0.15：硬件监控迁移为独立窗口，left panel 仅 sidebar）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Q-agent")
        self.resize(1200, 800)
        self._hw_window: HardwareMonitorWindow | None = None
        self._tool_history_window: ToolHistoryWindow | None = None
        self._build_layout()

    def _build_layout(self) -> None:
        # 中央容器：水平布局 [left_panel | 主内容区]
        central = QWidget(self)
        from PySide6.QtWidgets import QHBoxLayout

        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # left panel（仅 sidebar，模块化挂载点保留供未来扩展）
        left_panel = QWidget(central)
        left_panel.setFixedWidth(LEFT_PANEL_WIDTH)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.sidebar = Sidebar(left_panel)
        left_layout.addWidget(self.sidebar, stretch=1)

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

        # toolbar 新建对话 / 清空按钮 → chat_page._clear_messages（v0.0.16 接通实际行为）
        self.toolbar.new_chat_requested.connect(self.chat_page._clear_messages)
        self.toolbar.clear_requested.connect(self.chat_page._clear_messages)

        # toolbar 取消生成按钮 → chat_page._cancel_chat（v0.0.17 接通 ChatWorker.stop）
        self.toolbar.cancel_requested.connect(self.chat_page._cancel_chat)

        # 菜单栏（注入 monitor_callback / close_callback，"监控"菜单 triggered）
        self.menu = MenuBar(
            self,
            monitor_callback=self._open_hardware_monitor,
            close_callback=self._close_hardware_monitor,
        )

        # v0.0.19 追加"工具"菜单：工具历史窗口（不动 MenuBar 既有结构）
        from PySide6.QtGui import QAction

        tools_menu = self.menuBar().addMenu("工具")
        history_action = QAction("工具历史", self)
        history_action.setShortcut("Ctrl+H")
        history_action.triggered.connect(self._open_tool_history)
        tools_menu.addAction(history_action)

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 启动后自动检测一次本地 Ollama 模型（延迟 100ms 让 UI 先绘制）
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self.toolbar.refresh_models)
        # 检测完成后会触发 model_group_changed，但启动时下拉框初始占位 disabled，
        # 主动调一次让 chat_page 初始禁用发送按钮（与 toolbar 初始状态对齐）
        QTimer.singleShot(150, self._sync_send_enabled)

    def _open_hardware_monitor(self) -> None:
        """v0.0.15 新增：菜单"打开监控"triggered → 实例化 + show HardwareMonitorWindow。

        独立顶级窗口（parent=None + Qt.Window flag），不依附 MainWindow。
        若已打开则再次 show + raise 激活，避免重复实例化。
        用户关闭监控窗口后 closed 信号触发 → 清空 _hw_window 引用，下次点"打开监控"重新实例化。
        """
        if self._hw_window is None:
            self._hw_window = HardwareMonitorWindow()
            self._hw_window.closed.connect(self._on_hw_window_closed)
        self._hw_window.start()
        self._hw_window.show()
        self._hw_window.raise_()

    def _on_hw_window_closed(self) -> None:
        """监控窗口关闭后清空引用，下次"打开监控"重新实例化。"""
        self._hw_window = None

    def _close_hardware_monitor(self) -> None:
        """v0.0.15 修订新增：菜单"关闭监控"triggered → 关闭独立窗口（如有）。"""
        if self._hw_window is not None:
            self._hw_window.close()

    def _open_tool_history(self) -> None:
        """v0.0.19 新增：菜单"工具 → 工具历史"triggered → 实例化 + show ToolHistoryWindow。"""
        if self._tool_history_window is None:
            from q_agent.ui.tool_history_window import ToolHistoryWindow

            self._tool_history_window = ToolHistoryWindow()
        self._tool_history_window.show()
        self._tool_history_window.raise_()

    def closeEvent(self, event: QCloseEvent) -> None:
        """主窗口关闭时优雅关闭硬件监控独立窗口（如有），避免 worker 线程悬挂。

        独立顶级窗口不会随主窗口自动关闭，需主动 close() 触发其 closeEvent 停 worker。
        """
        if self._hw_window is not None:
            self._hw_window.close()
        if self._tool_history_window is not None:
            self._tool_history_window.close()
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
