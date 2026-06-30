"""侧边栏：4 tab 切换（v0.0.1 既有模块，v0.0.14 恢复 QListWidget 子类原貌）。

v0.0.14 回退说明：
    v0.0.12 曾把 Sidebar 从 QListWidget 改为 QFrame 容器内嵌 HardwareMonitor，
    违反模块化开发原则（CLAUDE.md 第二十一节）——新功能侵入既有模块导致
    QSS 选择器失配、tooltip 异常、连锁破坏。v0.0.14 回退到 v0.0.9 QListWidget
    子类原貌，HardwareMonitor 改由 MainWindow left panel 独立挂载（模块化）。

4 个 tab：
    对话 / 技能 / 记忆 / 设置

行为：
    - QListWidget 4 项，点击切换主内容区（QStackedWidget index）
    - 每个 tab 项含图标 + 文字 + tooltip
    - 键盘 Tab 键可聚焦，Enter 可切换（UX 规范 keyboard nav 友好）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from q_agent.ui.icons import load_icon

# tab 元数据：(name, label, icon_name, tooltip)
TABS: list[tuple[str, str, str, str]] = [
    ("chat", "对话", "chat", "对话 tab：与 AI 交互的消息流"),
    ("skills", "技能", "skills", "技能 tab：已注册技能列表（当前为占位）"),
    ("memory", "记忆", "memory", "记忆 tab：运行期记忆条目（当前为占位）"),
    ("settings", "设置", "settings", "设置 tab：通用 / LLM 后端 / 工具调用层配置"),
]

# sidebar 固定宽度（v0.0.14 起由 MainWindow left panel 控制整体宽度，
# sidebar 自身仍保留 200px 兼容历史）
SIDEBAR_WIDTH = 200


class Sidebar(QListWidget):
    """侧边栏 tab 切换组件（v0.0.14 模块化回退：纯 QListWidget，不含硬件监控）。

    硬件监控由 MainWindow 在 left panel 中独立挂载，不侵入本组件。
    """

    tab_changed = Signal(int)  # 切换时发信号，参数为 tab 索引

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setIconSize(QSize(20, 20))
        self.setCurrentRow(0)
        self.currentRowChanged.connect(self.tab_changed.emit)
        self._build_items()

    def _build_items(self) -> None:
        for _name, label, icon_name, tooltip in TABS:
            icon: QIcon = load_icon(icon_name)
            item = QListWidgetItem(icon, label)
            item.setToolTip(tooltip)
            self.addItem(item)
