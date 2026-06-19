"""侧边栏：4 tab 切换。

4 个 tab：
    对话 / 技能 / 记忆 / 设置

行为：
    - QListWidget 4 项，点击切换主内容区（QStackedWidget index）
    - 每个 tab 项含图标 + 文字
    - 键盘 Tab 键可聚焦，Enter 可切换（UX 规范 keyboard nav 友好）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from q_agent.ui.icons import load_icon

# tab 元数据：(name, label, icon_name)
TABS: list[tuple[str, str, str]] = [
    ("chat", "对话", "chat"),
    ("skills", "技能", "skills"),
    ("memory", "记忆", "memory"),
    ("settings", "设置", "settings"),
]


class Sidebar(QListWidget):
    """侧边栏 tab 切换组件。"""

    tab_changed = Signal(int)  # 切换时发信号，参数为 tab 索引

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(200)
        self.setCurrentRow(0)
        self.currentRowChanged.connect(self.tab_changed.emit)
        self._build_items()

    def _build_items(self) -> None:
        for _name, label, icon_name in TABS:
            icon: QIcon = load_icon(icon_name)
            item = QListWidgetItem(icon, label)
            self.addItem(item)
