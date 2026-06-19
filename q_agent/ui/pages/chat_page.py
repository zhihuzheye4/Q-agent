"""对话 tab：消息流 + 输入框 + 发送按钮。

行为（活 UI 空壳）：
    - 发送按钮按下时，输入框文本追加到消息流（纯前端 echo，无 LLM 调用）
    - 用户消息用 MessageUser 样式气泡，AI 用 MessageAI（这里"AI"是固定占位回声）
    - 回车键也能触发发送
    - 输入框为空时发送按钮 disabled
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ChatPage(QWidget):
    """对话 tab 主页。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._messages: list[tuple[str, str]] = []  # (role, text)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 上方：消息流（可滚动）
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(24, 24, 24, 24)
        self.messages_layout.setSpacing(12)
        self.messages_layout.addStretch()  # 占位拉伸

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, stretch=1)

        # 下方：输入框 + 发送按钮
        input_bar = QWidget(self)
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(12)

        self.input = QLineEdit(input_bar)
        self.input.setObjectName("ChatInput")
        self.input.setPlaceholderText("输入消息，按 Enter 发送...")
        self.input.textChanged.connect(self._on_input_changed)
        self.input.returnPressed.connect(self._on_send_clicked)

        self.send_btn = QPushButton("发送", input_bar)
        self.send_btn.setObjectName("SendButton")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._on_send_clicked)

        input_layout.addWidget(self.input, stretch=1)
        input_layout.addWidget(self.send_btn)
        layout.addWidget(input_bar)

        # 初始占位消息
        self._add_message("ai", "你好，我是 Q-agent（活 UI 空壳）。输入消息后按发送，会原样回显。")

    def _on_input_changed(self, text: str) -> None:
        self.send_btn.setEnabled(bool(text.strip()))

    def _on_send_clicked(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self._add_message("user", text)
        # 活 UI 空壳：AI 固定回声占位（不调 LLM）
        self._add_message("ai", f"[echo 回声] {text}")
        self.input.clear()
        self._scroll_to_bottom()

    def _add_message(self, role: str, text: str) -> None:
        """追加消息气泡。role: 'user' / 'ai'。"""
        from PySide6.QtWidgets import QLabel

        label = QLabel(text, self.messages_container)
        label.setWordWrap(True)
        label.setObjectName("MessageUser" if role == "user" else "MessageAI")
        label.setMaximumWidth(560)
        if role == "user":
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # 插入到 stretch 之前
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, label)
        self._messages.append((role, text))
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        from PySide6.QtCore import QTimer

        bar = self.scroll_area.verticalScrollBar()

        def _scroll() -> None:
            bar.setValue(bar.maximum())

        QTimer.singleShot(0, _scroll)
