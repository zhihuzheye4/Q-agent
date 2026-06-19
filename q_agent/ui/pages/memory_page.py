"""记忆 tab：占位列表。

行为（活 UI 空壳）：
    - 列出几个占位记忆条目（不调 MemoryStore）
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


class MemoryPage(QWidget):
    """记忆 tab 主页。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("运行期记忆条目", self)
        title.setObjectName("SettingsGroupTitle")
        layout.addWidget(title)

        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("MemoryList")
        for entry in (
            "[对话] 你好，我是 Q-agent（占位）",
            "[对话] [echo 回声] ...",
            "[技能] echo 调用",
            "[记忆] 占位条目 1",
            "[记忆] 占位条目 2",
        ):
            item = QListWidgetItem(entry)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        hint = QLabel("提示：记忆 tab 为占位骨架，不调 MemoryStore。", self)
        hint.setStyleSheet("color: #272F42; font-size: 12px;")
        layout.addWidget(hint)
