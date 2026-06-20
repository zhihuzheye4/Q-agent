"""对话 tab：消息流 + 输入框 + 发送按钮。

行为（v0.0.8 起接 Ollama 真实调用）：
    - 发送按钮按下时，调当前选中模型对应的 OllamaClient.chat_stream 流式生成
    - ChatWorker 后台跑流式，buffer 攒满 500 字 OR 满 500ms 任一触发就 emit 一段
    - 主线程收到 chunk 追加到 pending AI 气泡，done 时整段入历史 _messages
    - 失败时显示红色错误气泡（区别于正常 AI 气泡）
    - 选中云端预置占位（gpt-4o/claude/gemini，未接 API）时发送按钮禁用
    - 用户消息气泡贴右边，AI 消息气泡贴左边
    - AI 气泡上方显示当前回答的模型名小标签（取自 toolbar.current_model）
    - 气泡最大宽度跟随容器宽度（容器 92%），长发言可占满大部分宽度
    - 回车键触发发送，Shift+Enter 换行（多行输入支持长发言）
    - 输入框为多行 QTextEdit，高度可随内容增长
    - 输入框为空时发送按钮 disabled
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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

from q_agent.ui.chat_worker import ChatWorker
from q_agent.ui.loading_dots import LoadingDots

# 气泡最大宽度占容器可用宽度的比例（长发言友好，短发言按内容自适应）
BUBBLE_WIDTH_RATIO = 0.92
# 气泡最小宽度（避免窗口极窄时气泡太窄不可读）
BUBBLE_MIN_WIDTH = 200
# 输入框最小/最大高度（多行输入支持长发言）
INPUT_MIN_HEIGHT = 44
INPUT_MAX_HEIGHT = 200
# 未选模型时 AI 气泡上方显示的占位文本
NO_MODEL_TEXT = "(未选模型)"
# 允许发送的分组：本地 + Ollama Cloud 转发（云端预置走 OpenAI/Anthropic/Google API 未接，禁用）
SENDABLE_GROUPS = ("local", "ollama-cloud")
# 默认 Ollama host（v0.0.8 hardcoded，下版本接 QSettings 后改）
DEFAULT_HOST = "http://localhost:11434"
# 模型名标签调色板（按模型名 hash 取一个，8 个高对比色，同一模型每次显示同色）
MODEL_NAME_PALETTE = (
    "#22C55E",  # 绿
    "#3B82F6",  # 蓝
    "#A855F7",  # 紫
    "#EC4899",  # 粉
    "#F97316",  # 橙
    "#14B8A6",  # 青
    "#EAB308",  # 黄
    "#6366F1",  # 靛
)
# 切换模型时系统提示气泡文案
SYSTEM_MSG_SWITCHED = "模型已切换为 {model}，上下文已清空"


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
        self._messages: list[tuple[str, str, str | None]] = []  # (role, text, model_name)
        self._model_provider: Callable[[], str | None] | None = None
        self._group_provider: Callable[[], str | None] | None = None
        self._host: str = DEFAULT_HOST
        self._worker: ChatWorker | None = None
        self._pending_bubble: QLabel | None = None
        self._pending_text: str = ""
        self._pending_model_name: str | None = None
        self._pending_loading: LoadingDots | None = None
        self._bubble_labels: list[QLabel] = []  # 用于 resize 时批量更新最大宽度
        self._build_ui()

    def set_model_provider(self, provider: Callable[[], str | None]) -> None:
        """注入模型名提供器（MainWindow 调用，绑定到 toolbar.current_model）。"""
        self._model_provider = provider

    def set_group_provider(self, provider: Callable[[], str | None]) -> None:
        """注入分组提供器（MainWindow 调用，绑定到 toolbar.current_model_group）。"""
        self._group_provider = provider

    def set_host(self, host: str) -> None:
        """注入 Ollama host（v0.0.8 默认 DEFAULT_HOST，下版本接 QSettings 后改）。"""
        self._host = host

    def update_send_enabled(self, group: str | None) -> None:
        """根据当前选中模型的分组 + 输入框内容决定发送按钮是否可用。

        云端预置（cloud，未接 API）→ 禁用 + tooltip 提示
        本地 / Ollama Cloud 转发 → 启用 iff 输入框非空
        其他（None）→ 禁用
        """
        if group == "cloud":
            self.send_btn.setEnabled(False)
            self.send_btn.setToolTip("云端 API 未接，请选本地或 Ollama Cloud 模型")
        elif group in SENDABLE_GROUPS:
            has_text = bool(self.input.toPlainText().strip())
            self.send_btn.setEnabled(has_text)
            self.send_btn.setToolTip("发送当前输入框内容（也可按 Enter）")
        else:
            self.send_btn.setEnabled(False)
            self.send_btn.setToolTip("未选模型，请先在右上角下拉框选择")

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
        """输入框内容变化 → 重新判定发送按钮启用（基于当前分组 + 输入非空）。"""
        group = self._group_provider() if self._group_provider else None
        self.update_send_enabled(group)

    def _on_send_clicked(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        # 防御性：当前分组不可发送时不调（正常情况 send_btn 已禁用）
        group = self._group_provider() if self._group_provider else None
        if group not in SENDABLE_GROUPS:
            return
        model_name = self._current_model_name()

        # 用户消息入历史
        self._add_message("user", text)

        # 给 LLM 的 messages：含到当前 user 为止的全部历史
        messages_for_llm: list[dict[str, Any]] = [
            {"role": r, "content": t} for r, t, _ in self._messages
        ]

        # 创建 pending AI 气泡（不污染 _messages，等生成完毕再 append）+ LoadingDots 加载指示器
        pending_bubble = self._add_message(
            "ai", "", model_name=model_name, append_to_history=False, loading=True
        )
        self._pending_bubble = pending_bubble
        self._pending_text = ""
        self._pending_model_name = model_name

        # 进入 loading 状态：禁用输入框 + 按钮，按钮文字变"生成中"
        self.send_btn.setEnabled(False)
        self.input.setEnabled(False)
        self.send_btn.setText("生成中")

        self.input.clear()
        self._scroll_to_bottom()

        # 启动 ChatWorker 后台流式调用
        self._worker = ChatWorker(model_name, self._host, messages_for_llm, parent=self)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.chat_failed.connect(self._on_chat_failed)
        self._worker.chat_done.connect(self._on_chat_done)
        self._worker.start()

    def _remove_pending_loading(self) -> None:
        """移除 pending AI 气泡内的 LoadingDots（首个 chunk / 失败 / 完成时调用）。"""
        if self._pending_loading is not None:
            self._pending_loading.hide()
            self._pending_loading.deleteLater()
            self._pending_loading = None

    def _on_chunk(self, text: str) -> None:
        """ChatWorker 流式 flush 一段 → 追加到 pending AI 气泡。"""
        if self._pending_bubble is None:
            return
        # 首个 chunk 到达 → 移除 LoadingDots（回复开始流入）
        if self._pending_loading is not None:
            self._remove_pending_loading()
        self._pending_text += text
        self._pending_bubble.setText(self._pending_text)
        self._scroll_to_bottom()

    def _on_chat_failed(self, msg: str) -> None:
        """ChatWorker 失败 → 把 pending 气泡变红显示错误。"""
        self._remove_pending_loading()
        if self._pending_bubble is not None:
            self._pending_bubble.setText(f"❌ {msg}")
            self._pending_bubble.setObjectName("MessageError")
            # 强制重应用样式（objectName 变了，需要 polish 刷新）
            self._pending_bubble.style().unpolish(self._pending_bubble)
            self._pending_bubble.style().polish(self._pending_bubble)
            self._bubble_labels.append(self._pending_bubble)  # 错误气泡也参与 resize
        self._reset_send_state()

    def _on_chat_done(self) -> None:
        """ChatWorker 完成 → 完整回复入历史 + 恢复输入状态。"""
        self._remove_pending_loading()
        if self._pending_bubble is not None and self._pending_text:
            self._messages.append(("ai", self._pending_text, self._pending_model_name))
        self._pending_bubble = None
        self._pending_text = ""
        self._pending_model_name = None
        self._reset_send_state()

    def _reset_send_state(self) -> None:
        """恢复输入框 + 发送按钮可用状态，按钮文字还原。"""
        self.input.setEnabled(True)
        self.send_btn.setText("发送")
        # 重新按当前分组 + 输入框内容判定启用状态
        self.update_send_enabled(self._group_provider() if self._group_provider else None)
        self.input.setFocus()

    def _current_model_name(self) -> str:
        """从 model_provider 取当前模型名；未注入或返回 None 时给占位。"""
        if self._model_provider is None:
            return NO_MODEL_TEXT
        name = self._model_provider()
        return name if name else NO_MODEL_TEXT

    def _bubble_max_width(self) -> int:
        """根据容器当前宽度计算气泡最大宽度（容器 92%，最小 200）。"""
        avail = max(self.messages_container.width() - 48, BUBBLE_MIN_WIDTH)
        return max(int(avail * BUBBLE_WIDTH_RATIO), BUBBLE_MIN_WIDTH)

    def _add_message(
        self,
        role: str,
        text: str,
        model_name: str | None = None,
        append_to_history: bool = True,
        loading: bool = False,
    ) -> QLabel:
        """追加消息气泡。role: 'user'（贴右）/ 'ai'（贴左）。

        AI 消息时 model_name 非空 → 气泡上方加模型名小标签（颜色按 hash 取调色板）。
        loading=True 时在气泡上方插入 LoadingDots 跳动指示器（pending AI 气泡专用，
        第一个 chunk 到达后由 _on_chunk 移除）。
        布局：
            AI 行：[stretch][垂直列：模型名label + (LoadingDots?) + 气泡label]  → 贴左
            用户行：[垂直列：气泡label][stretch]  → 贴右
        气泡最大宽度 = 容器宽度 × 92%，长发言可占满大部分宽度。

        Args:
            append_to_history: 是否加入 _messages 历史。pending AI 气泡用 False
                不污染历史，等 chat_done 时再单独 append。
            loading: 是否在气泡上方插入 LoadingDots 加载指示器（pending AI 专用）。

        Returns:
            bubble_label 引用，供外部追加 text（流式 chunk 用）
        """
        max_w = self._bubble_max_width()

        bubble_label = QLabel(text, self.messages_container)
        bubble_label.setWordWrap(True)
        bubble_label.setObjectName("MessageUser" if role == "user" else "MessageAI")
        bubble_label.setMaximumWidth(max_w)
        self._bubble_labels.append(bubble_label)

        bubble_col = QWidget(self.messages_container)
        col_layout = QVBoxLayout(bubble_col)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(4)

        # AI 消息且提供模型名 → 上方加模型名小标签（颜色按模型名 hash 取调色板）
        if role == "ai" and model_name:
            model_label = QLabel(model_name, bubble_col)
            model_label.setObjectName("ModelLabel")
            model_label.setMaximumWidth(max_w)
            color = self._model_color(model_name)
            model_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 0 4px;")
            col_layout.addWidget(model_label)
            self._bubble_labels.append(model_label)

        # pending AI 气泡：模型名下方、气泡上方插入 LoadingDots 跳动指示器
        if loading:
            loading_dots = LoadingDots(bubble_col)
            col_layout.addWidget(loading_dots)
            self._pending_loading = loading_dots

        col_layout.addWidget(bubble_label)

        row = QWidget(self.messages_container)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        if role == "user":
            # 用户：[stretch][列] → 贴右
            row_layout.addStretch(1)
            row_layout.addWidget(bubble_col)
        else:
            # AI：[列][stretch] → 贴左
            row_layout.addWidget(bubble_col)
            row_layout.addStretch(1)
        # 插入到 stretch 之前
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        if append_to_history:
            self._messages.append((role, text, model_name))
        self._scroll_to_bottom()
        return bubble_label

    def _add_system_message(self, text: str) -> None:
        """追加居中灰色斜体系统提示气泡（区别于 user/ai 对话气泡）。

        不入 _messages 历史（不是对话内容，仅做 UI 提示）。
        用于切换模型时显示"模型已切换为 XXX，上下文已清空"。
        """
        max_w = self._bubble_max_width()
        label = QLabel(text, self.messages_container)
        label.setObjectName("MessageSystem")
        label.setMaximumWidth(max_w)
        self._bubble_labels.append(label)
        row = QWidget(self.messages_container)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addStretch(1)
        row_layout.addWidget(label)
        row_layout.addStretch(1)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self._scroll_to_bottom()

    def _clear_messages(self) -> None:
        """清空消息流（移除所有 row widget，保留末尾 stretch）+ 清空 _messages 历史。

        用于切换模型时清空当前对话上下文。也清空 pending AI 气泡状态。
        """
        # stretch 在末尾，count > 1 时仍有 row widget 待移除
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        self._messages.clear()
        self._bubble_labels.clear()
        self._pending_bubble = None
        self._pending_text = ""
        self._pending_model_name = None
        # LoadingDots 随 row widget deleteLater 一并销毁，仅清引用
        self._pending_loading = None

    def _on_model_changed(self, model_name: str) -> None:
        """toolbar.model_selected 信号触发：清空对话 + 插入系统提示气泡。

        切换模型后历史消息对当前模型无意义（context 不同），统一清空 +
        插入"模型已切换为 XXX，上下文已清空"系统提示。
        """
        self._clear_messages()
        self._add_system_message(SYSTEM_MSG_SWITCHED.format(model=model_name))

    def _model_color(self, name: str) -> str:
        """根据模型名稳定 hash（zlib.crc32）取调色板中的一个颜色。

        同一模型每次启动显示同色（zlib 跨进程稳定，不同于内置 hash 随机化）。
        占位文本 NO_MODEL_TEXT 返回默认灰色。
        """
        import zlib

        if name == NO_MODEL_TEXT:
            return "#94A3B8"
        return MODEL_NAME_PALETTE[zlib.crc32(name.encode("utf-8")) % len(MODEL_NAME_PALETTE)]

    def _find_first_label_by_object_name(self, name: str) -> QLabel | None:
        """遍历消息流查找首个指定 objectName 的 QLabel（测试用）。"""
        for i in range(self.messages_layout.count()):
            item = self.messages_layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            # row widget 内嵌套 layout，需递归查找 QLabel
            found = self._find_label_recursive(widget, name)
            if found is not None:
                return found
        return None

    @staticmethod
    def _find_label_recursive(widget: QWidget, name: str) -> QLabel | None:
        """递归查找 widget 子树中首个 objectName=name 的 QLabel。"""
        if isinstance(widget, QLabel) and widget.objectName() == name:
            return widget
        for child in widget.findChildren(QLabel):
            if child.objectName() == name:
                return child
        return None

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: ANN001
        """窗口大小变化时，重设所有气泡 + 模型名 label 的最大宽度。"""
        super().resizeEvent(event)
        max_w = self._bubble_max_width()
        for label in self._bubble_labels:
            label.setMaximumWidth(max_w)

    def _scroll_to_bottom(self) -> None:
        import contextlib

        from PySide6.QtCore import QTimer
        from shiboken6 import isValid

        bar = self.scroll_area.verticalScrollBar()

        def _scroll() -> None:
            # 防御：scroll_area 可能已被销毁（测试场景跨用例残留的 deferred 调用）
            if not isValid(bar):
                return
            with contextlib.suppress(RuntimeError):
                bar.setValue(bar.maximum())

        QTimer.singleShot(0, _scroll)
