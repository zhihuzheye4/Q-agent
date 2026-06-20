"""主窗口：QMainWindow 主框架。

结构：
    +---------------------------+
    | menu_bar                   |
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

行为：
    - 侧边栏点击 tab → QStackedWidget 切换 index
    - 工具栏按钮 → 状态栏提示
    - 菜单栏文件 → 退出；帮助 → 关于弹窗
    - 全部前端响应，无后端逻辑
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from q_agent.ui.menu_bar import MenuBar
from q_agent.ui.pages.chat_page import ChatPage
from q_agent.ui.pages.memory_page import MemoryPage
from q_agent.ui.pages.settings_page import SettingsPage
from q_agent.ui.pages.skills_page import SkillsPage
from q_agent.ui.sidebar import Sidebar
from q_agent.ui.theme import apply_theme
from q_agent.ui.toolbar import Toolbar


class MainWindow(QMainWindow):
    """Q-agent 主窗口。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Q-agent")
        self.resize(1200, 800)
        self._build_layout()

    def _build_layout(self) -> None:
        # 中央容器：水平布局 [侧边栏 | 主内容区]
        central = QWidget(self)
        from PySide6.QtWidgets import QHBoxLayout

        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # 侧边栏
        self.sidebar = Sidebar(central)
        h_layout.addWidget(self.sidebar)

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

        # ChatPage 注入模型名提供器（绑定到 toolbar.current_model）
        self.chat_page.set_model_provider(self.toolbar.current_model)

        # 菜单栏
        self.menu = MenuBar(self)

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 启动后自动检测一次本地 Ollama 模型（延迟 100ms 让 UI 先绘制）
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self.toolbar.refresh_models)

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
