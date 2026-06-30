"""Claude Code 风格折叠展开工具气泡 widget。

4 状态：
- pending（执行中）：蓝色齿轮 #4A9FFA
- success（成功）：绿色圆勾 #3FB950
- failed（失败）：红色圆叉 #F85149
- cancelled（取消）：灰色圆圈横线 #8B949E

默认折叠 28px，展开最大 240px，QPropertyAnimation 200ms OutCubic。

模块化：独立 widget，ChatPage 一行 addWidget 挂载。
v0.0.19 仅建好 widget，信号挂载注释掉；v0.0.20 编排层接通后触发。
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Signal,
)
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from q_agent.ui.icons import load_icon

# 4 状态图标名（icon_path 会自动加 -active.svg 后缀）
_STATE_ICON_NAMES: dict[str, str] = {
    "pending": "tool-pending",
    "success": "tool-success",
    "failed": "tool-failed",
    "cancelled": "tool-cancelled",
}

_COLLAPSED_HEIGHT = 28
_EXPANDED_HEIGHT = 240
_ANIM_DURATION_MS = 200


class ToolBubble(QFrame):
    """工具调用气泡：折叠展开 + 4 状态切换 + 输入输出展示。"""

    # 信号（v0.0.20 编排层接通后由 ChatPage 连接）
    tool_call_started = Signal(str)  # tool_name
    tool_call_finished = Signal(str, str, str)  # tool_name, status, output_path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToolBubble")
        self._collapsed = True
        self._state = "pending"
        self._anim: QPropertyAnimation | None = None

        v = QVBoxLayout(self)
        v.setContentsMargins(8, 4, 8, 4)
        v.setSpacing(2)

        # 折叠态单行：图标 + 标题 + 展开按钮
        top = QHBoxLayout()
        top.setSpacing(6)
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(QSize(16, 16))
        self.title_lbl = QLabel("工具调用")
        self.title_lbl.setFont(QFont("", 9))
        self.expand_btn = QPushButton("展开")
        self.expand_btn.setFlat(True)
        self.expand_btn.setFixedWidth(48)
        top.addWidget(self.icon_lbl)
        top.addWidget(self.title_lbl, 1)
        top.addWidget(self.expand_btn)
        v.addLayout(top)

        # 展开态：输入 + 输出
        self.input_lbl = QLabel("输入：")
        self.input_lbl.setWordWrap(True)
        self.input_lbl.setStyleSheet("color: #6B7280; font-size: 11px;")
        self.output_lbl = QLabel("输出：")
        self.output_lbl.setWordWrap(True)
        self.output_lbl.setStyleSheet("color: #6B7280; font-size: 11px;")
        v.addWidget(self.input_lbl)
        v.addWidget(self.output_lbl)

        # 落盘后两按钮（v0.0.20 接通编排层后才会显示路径）
        btn_row = QHBoxLayout()
        self.view_btn = QPushButton("点击查看")
        self.view_btn.setFixedWidth(80)
        self.open_fm_btn = QPushButton("在文件管理器打开")
        self.open_fm_btn.setFixedWidth(140)
        btn_row.addWidget(self.view_btn)
        btn_row.addWidget(self.open_fm_btn)
        btn_row.addStretch(1)
        v.addLayout(btn_row)

        self.expand_btn.clicked.connect(self._toggle)
        self._apply_state("pending")
        self.setFixedHeight(_COLLAPSED_HEIGHT)
        self.setMaximumHeight(_COLLAPSED_HEIGHT)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        target = _COLLAPSED_HEIGHT if self._collapsed else _EXPANDED_HEIGHT
        self._anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._anim.setDuration(_ANIM_DURATION_MS)
        self._anim.setStartValue(self.height())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)  # type: ignore[attr-defined]
        self._anim.start()
        self.expand_btn.setText("展开" if self._collapsed else "折叠")

    def _apply_state(self, state: str) -> None:
        self._state = state
        icon_name = _STATE_ICON_NAMES.get(state, "tool-pending")
        icon: QIcon = load_icon(icon_name)
        if icon.isNull():
            # 图标缺失时不崩，显示空 pixmap
            self.icon_lbl.setPixmap(QPixmap(16, 16))
        else:
            self.icon_lbl.setPixmap(icon.pixmap(QSize(16, 16)))

    # ---- 外部触发槽 ----

    def on_started(self, tool_name: str) -> None:
        """工具开始执行时调（v0.0.20 由 chat_worker.tool_call_started 信号触发）。"""
        self.title_lbl.setText(f"执行中：{tool_name}")
        self._apply_state("pending")

    def on_finished(
        self,
        tool_name: str,
        status: str,
        output_path: str,
    ) -> None:
        """工具完成时调（v0.0.20 由 chat_worker.tool_call_finished 信号触发）。

        status: success / failed / cancelled
        """
        self.title_lbl.setText(f"{tool_name} - {status}")
        self._apply_state(status)
        if output_path:
            self.output_lbl.setText(f"输出落盘：{output_path}")
        else:
            self.output_lbl.setText("输出：（内联，未落盘）")
