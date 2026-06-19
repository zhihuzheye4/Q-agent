"""对话 tab：消息流 + 输入框 + 发送按钮。

行为（活 UI 空壳）：
    - 发送按钮按下时，输入框文本追加到消息流（纯前端 echo，无 LLM 调用）
    - 用户消息气泡贴右边（由右至左排），AI 消息气泡贴左边（由左至右排）
    - 气泡最大宽度跟随容器宽度（容器 70%），窗口拉宽时气泡跟着变宽，但仍贴对应边
    - 回车键也能触发发送
    - 输入框为空时发送按钮 disabled
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# 气泡最大宽度占容器可用宽度的比例（动态跟随窗口大小）
BUBBLE_WIDTH_RATIO = 0.7
# 气泡最小宽度（避免窗口极窄时气泡太窄不可读）
BUBBLE_MIN_WIDTH = 200


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
        self.send_btn.setToolTip("发送当前输入框内容（也可按 Enter）")
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

    def _bubble_max_width(self) -> int:
        """根据容器当前宽度计算气泡最大宽度（容器 70%，最小 200）。"""
        avail = max(self.messages_container.width() - 48, BUBBLE_MIN_WIDTH)
        return max(int(avail * BUBBLE_WIDTH_RATIO), BUBBLE_MIN_WIDTH)

    def _add_message(self, role: str, text: str) -> None:
        """追加消息气泡。role: 'user'（贴右）/ 'ai'（贴左）。

        布局：每条消息用一行 QHBoxLayout 包装，
        AI 行：[气泡][stretch]  → 气泡贴左
        用户行：[stretch][气泡]  → 气泡贴右
        气泡最大宽度 = 容器宽度 × 70%，跟随窗口大小变化。
        """
        label = QLabel(text, self.messages_container)
        label.setWordWrap(True)
        label.setObjectName("MessageUser" if role == "user" else "MessageAI")
        label.setMaximumWidth(self._bubble_max_width())

        row = QWidget(self.messages_container)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        if role == "user":
            # 用户：[stretch][气泡] → 贴右
            row_layout.addStretch(1)
            row_layout.addWidget(label)
        else:
            # AI：[气泡][stretch] → 贴左
            row_layout.addWidget(label)
            row_layout.addStretch(1)
        # 插入到 stretch 之前
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self._messages.append((role, text))
        self._scroll_to_bottom()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: ANN001
        """窗口大小变化时，重设已有气泡最大宽度。"""
        super().resizeEvent(event)
        max_w = self._bubble_max_width()
        # 遍历已有消息行，更新气泡 QLabel 最大宽度
        for i in range(self.messages_layout.count() - 1):  # 最后一个是 stretch
            row_item = self.messages_layout.itemAt(i)
            if row_item is None:
                continue
            row = row_item.widget()
            if row is None:
                continue
            row_layout = row.layout()
            if row_layout is None:
                continue
            for j in range(row_layout.count()):
                child = row_layout.itemAt(j)
                if child is None:
                    continue
                w = child.widget()
                if isinstance(w, QLabel):
                    w.setMaximumWidth(max_w)

    def _scroll_to_bottom(self) -> None:
        from PySide6.QtCore import QTimer

        bar = self.scroll_area.verticalScrollBar()

        def _scroll() -> None:
            bar.setValue(bar.maximum())

        QTimer.singleShot(0, _scroll)
