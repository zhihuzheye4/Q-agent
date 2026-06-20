"""加载指示器：流动彩虹色三点跳动（pending AI 气泡内显示）。

设计：
- 三个圆点依次上下跳动（类似 iMessage 打字气泡）
- 颜色：HSV 色相随时间流动 + 每点偏移 60 度 → 流动彩虹渐变
- 透明度：alpha=180 (~70%)，与背景融合不刺眼
- QTimer 80ms tick，phase 0~1 循环，约 1.6s 一个完整跳动周期
- 父 widget 销毁时 QTimer 自动停止（Qt parent 机制）

UX 决策（v0.0.10 用户已确认）：
- 形式：三点跳动
- 位置：pending AI 气泡内
- 彩色：流动彩虹渐变（HSV 色相循环，独立于模型色）
- 透明度：加载指示元素本身半透明（alpha ~70%）
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

# 三个点的整体宽度/高度（固定尺寸，不随容器缩放）
DOT_SIZE = 8
DOT_GAP = 8
# 上下跳动幅度（px）
DOT_BOUNCE = 5
# 透明度（0-255，180 ≈ 70%）
DOT_ALPHA = 180
# 跳动周期：80ms × 20 tick = 1.6s 一个完整循环
TICK_MS = 80
PHASE_STEP = 0.05


class LoadingDots(QWidget):
    """流动彩虹色三点跳动加载指示器。

    用于 pending AI 气泡内，提示用户"AI 正在生成"。第一个 chunk 到达后
    由 ChatPage 移除（hide + deleteLater）。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        total_w = 3 * DOT_SIZE + 2 * DOT_GAP
        self.setFixedSize(total_w, DOT_SIZE + 2 * DOT_BOUNCE)
        self._phase: float = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(TICK_MS)

    def _tick(self) -> None:
        """推进动画相位并触发重绘。"""
        self._phase = (self._phase + PHASE_STEP) % 1.0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ANN001, ARG002
        """绘制三个跳动的彩虹色圆点。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        total = 3 * DOT_SIZE + 2 * DOT_GAP
        start_x = (w - total) // 2
        baseline_y = h // 2 - DOT_SIZE // 2
        for i in range(3):
            # 每个点相位错开 1/3 周期 → 依次跳动
            phase_offset = i * 0.33
            t = (self._phase + phase_offset) % 1.0
            # sin 曲线 → 平滑上下跳动（取绝对值让点只往上跳）
            y_offset = -abs(math.sin(t * math.pi * 2)) * DOT_BOUNCE
            # 流动彩虹：HSV 色相随时间循环 + 每点偏移 60 度
            hue = (self._phase * 360 + i * 60) % 360
            color = QColor.fromHsv(int(hue), 220, 230, DOT_ALPHA)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            x = start_x + i * (DOT_SIZE + DOT_GAP)
            y = int(baseline_y + y_offset)
            painter.drawEllipse(x, y, DOT_SIZE, DOT_SIZE)
