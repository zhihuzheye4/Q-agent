"""技能 tab：占位列表。

行为（活 UI 空壳）：
    - 列出几个占位技能项（不调 SkillRegistry）
    - 点击项可选中，但不触发任何行为
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SkillsPage(QWidget):
    """技能 tab 主页。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("已注册技能", self)
        title.setObjectName("SettingsGroupTitle")
        layout.addWidget(title)

        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("SkillList")
        for name in (
            "echo（已实现）",
            "search（待实现）",
            "summarize（待实现）",
            "translate（待实现）",
        ):
            item = QListWidgetItem(name)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        hint = QLabel("提示：技能 tab 为占位骨架，不调 SkillRegistry。", self)
        hint.setStyleSheet("color: #272F42; font-size: 12px;")
        layout.addWidget(hint)
