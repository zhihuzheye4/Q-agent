"""对话 tab：消息流 + 输入框 + 发送按钮。

行为（活 UI 空壳）：
    - 发送按钮按下时，输入框文本追加到消息流（纯前端 echo，无 LLM 调用）
    - 用户消息气泡贴右边，AI 消息气泡贴左边
    - 气泡最大宽度跟随容器宽度（容器 92%），长发言可占满大部分宽度
    - 回车键触发发送，Shift+Enter 换行（多行输入支持长发言）
    - 输入框为多行 QTextEdit，高度可随内容增长
    - 输入框为空时发送按钮 disabled
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# 气泡最大宽度占容器可用宽度的比例（长发言友好，短发言按内容自适应）
BUBBLE_WIDTH_RATIO = 0.92
# 气泡最小宽度（避免窗口极窄时气泡太窄不可读）
BUBBLE_MIN_WIDTH = 200
# 输入框最小/最大高度（多行输入支持长发言）
INPUT_MIN_HEIGHT = 44
INPUT_MAX_HEIGHT = 200


class ChatInput(QTextEdit):
    """多行输入框：高度随内容动态变化（min~max 之间），Enter 发送，Shift+Enter 换行。"""

    send_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatInput")
        self.setAcceptRichText(False)
        self.setPlaceholderText("输入消息，按 Enter 发送，Shift+Enter 换行...")
        # 固定初始高度为最小高度，后续随内容增长
        self.setFixedHeight(INPUT_MIN_HEIGHT)
        self.setMaximumHeight(INPUT_MAX_HEIGHT)
        # 超过最大高度时才显示滚动条
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 监听文档尺寸变化（内容增减 → 触发重算高度）
        self.document().documentLayout().documentSizeChanged.connect(self._adjust_height)

    def _adjust_height(self) -> None:
        """根据文档内容高度动态调整输入框高度（在 min~max 之间）。"""
        doc_h = self.document().documentLayout().documentSize().toSize().height()
        # 加上边框 + padding 上下余量（QTextEdit 默认约 9px）
        margins = self.contentsMargins()
        needed = int(doc_h + margins.top() + margins.bottom() + 2)
        # 钳制到 [min, max]
        clamped = max(INPUT_MIN_HEIGHT, min(needed, INPUT_MAX_HEIGHT))
        if self.height() != clamped:
            self.setFixedHeight(clamped)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: ANN001
        """Enter 发送，Shift+Enter / Ctrl+Enter 换行。"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            mods = event.modifiers()
            shift = mods & Qt.KeyboardModifier.ShiftModifier
            ctrl = mods & Qt.KeyboardModifier.ControlModifier
            if shift or ctrl:
                # 换行：走默认行为插入换行符
                super().keyPressEvent(event)
                return
            # 发送：发出信号，交由 ChatPage 处理
            self.send_requested.emit()
            return
        super().keyPressEvent(event)


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

        # 下方：输入框 + 发送按钮（多行 QTextEdit 支持长发言）
        input_bar = QWidget(self)
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(12)

        self.input = ChatInput(input_bar)
        self.input.textChanged.connect(self._on_input_changed)
        self.input.send_requested.connect(self._on_send_clicked)

        self.send_btn = QPushButton("发送", input_bar)
        self.send_btn.setObjectName("SendButton")
        self.send_btn.setEnabled(False)
        self.send_btn.setToolTip("发送当前输入框内容（也可按 Enter）")
        self.send_btn.clicked.connect(self._on_send_clicked)

        input_layout.addWidget(self.input, stretch=1)
        input_layout.addWidget(self.send_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(input_bar)

        # 初始占位消息
        self._add_message("ai", "你好，我是 Q-agent（活 UI 空壳）。输入消息后按发送，会原样回显。")

    def _on_input_changed(self) -> None:
        text = self.input.toPlainText().strip()
        self.send_btn.setEnabled(bool(text))

    def _on_send_clicked(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        self._add_message("user", text)
        # 活 UI 空壳：AI 固定回声占位（不调 LLM）
        self._add_message("ai", f"[echo 回声] {text}")
        self.input.clear()
        self._scroll_to_bottom()

    def _bubble_max_width(self) -> int:
        """根据容器当前宽度计算气泡最大宽度（容器 92%，最小 200）。"""
        avail = max(self.messages_container.width() - 48, BUBBLE_MIN_WIDTH)
        return max(int(avail * BUBBLE_WIDTH_RATIO), BUBBLE_MIN_WIDTH)

    def _add_message(self, role: str, text: str) -> None:
        """追加消息气泡。role: 'user'（贴右）/ 'ai'（贴左）。

        布局：每条消息用一行 QHBoxLayout 包装，
        AI 行：[气泡][stretch]  → 气泡贴左
        用户行：[stretch][气泡]  → 气泡贴右
        气泡最大宽度 = 容器宽度 × 92%，长发言可占满大部分宽度。
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
