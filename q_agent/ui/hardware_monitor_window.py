"""硬件监控独立窗口（v0.0.15 新增，模块化）。

由 menu_bar "监控"菜单 triggered 触发，MainWindow._open_hardware_monitor 实例化 + show()。

结构：
    +----------------------------------+
    | 硬件监控 - 6 指标 60s 历史        |  ← 顶部标题 30px
    +----------------------------------+
    | CPU%  45%  | GPU%  30%           |  ← MonitorCell 2 列 × 3 行
    | [折线图]   | [折线图]            |
    +-----------+----------------------+
    | VRAM% 60%  | RAM%  70%           |
    | [折线图]   | [折线图]            |
    +-----------+----------------------+
    | CPU°C N/A  | GPU°C 65°C          |
    | [N/A 横线] | [折线图]            |
    +-----------+----------------------+

模块化原则（CLAUDE.md 第二十一节）：
- 独立 widget 文件，自己管渲染 + worker 生命周期
- MainWindow 一行实例化 + show() 挂载，关闭时 closeEvent 优雅停止 worker
- 不侵入任何既有模块内部

指标（v0.0.15 6 个，0-100 数值范围，温度单位 °C）：
- CPU%（蓝）/ GPU%（绿）/ VRAM%（紫）/ RAM%（橙）/ CPU°C（灰蓝 N/A）/ GPU°C（红）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent, QPaintEvent

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from q_agent.ui.hardware_monitor import (
    COLOR_CELL_BG,
    COLOR_GRID,
    COLOR_NA,
    COLOR_PLOT_BG,
    COLOR_TEXT,
    HISTORY_SECONDS,
    METRICS,
    HardwareMonitorWorker,
)

# 窗口固定大小（2 列 × 3 行 cell + 标题 + 边距）
WINDOW_WIDTH = 620
WINDOW_HEIGHT = 520
# 每个 cell 高度（含图例 20px + 折线 ~100px）
CELL_HEIGHT = 150
CELL_MIN_WIDTH = 280


class MonitorCell(QWidget):
    """单个指标的小折线图 cell（自绘）。

    显示：顶部指标名 + 当前数值 + 单位（20px）+ 下方 60s 折线历史。
    无数据时画灰色 N/A 占位横线。
    """

    def __init__(
        self,
        key: str,
        label: str,
        color: str,
        unit: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._label = label
        self._color = color
        self._unit = unit
        self._history: list[float | None] = []
        self.setFixedHeight(CELL_HEIGHT)
        self.setMinimumWidth(CELL_MIN_WIDTH)

    def set_sample(self, value: float | None) -> None:
        """接收新样本，append 历史 + 截断到 HISTORY_SECONDS + 触发重绘。"""
        self._history.append(value)
        if len(self._history) > HISTORY_SECONDS:
            del self._history[0]
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ANN001, ARG002
        """自绘：顶部 20px 图例（色块 + 名称 + 当前数值）+ 下方折线图（含 y 轴）。

        v0.0.15 修订：
        - plot 坐标系背景用 COLOR_PLOT_BG（与 cell 整体背景区分）
        - 加 y 轴：左侧 28px 留给刻度标签（0/25/50/75/100 + 单位）+ 竖线
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # cell 整体背景
        painter.fillRect(0, 0, w, h, QColor(COLOR_CELL_BG))

        # 顶部图例（20px）
        legend_h = 20
        legend_y = 4
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)

        # 色块
        painter.setBrush(QColor(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(8, legend_y, 10, 10)

        # 名称 + 当前数值
        painter.setPen(QColor(COLOR_TEXT))
        last = self._history[-1] if self._history else None
        if last is None:
            last_str = "N/A"
        elif self._unit == "°C":
            last_str = f"{last:.0f}°C"
        else:
            last_str = f"{last:.0f}%"
        text = f"{self._label}  {last_str}"
        painter.drawText(22, legend_y + 10, text)

        # 折线图区域：左侧 28px 留给 y 轴刻度标签
        plot_y = legend_h + 4
        plot_h = h - plot_y - 4
        axis_w = 28
        plot_x = 8 + axis_w
        plot_w = w - 16 - axis_w

        # plot 坐标系背景（与 cell 整体背景区分）
        painter.fillRect(plot_x, plot_y, plot_w, plot_h, QColor(COLOR_PLOT_BG))

        # y 轴刻度标签 + 网格线（0/25/50/75/100）
        painter.setPen(QColor(COLOR_TEXT))
        painter.setFont(font)
        for pct in (0, 25, 50, 75, 100):
            y = plot_y + int(plot_h * (1 - pct / 100))
            # 刻度标签（左侧）
            label = f"{pct}°" if self._unit == "°C" else f"{pct}"
            painter.drawText(8, y + 3, label)
            # 网格线
            painter.setPen(QColor(COLOR_GRID))
            painter.drawLine(plot_x, y, plot_x + plot_w, y)
            painter.setPen(QColor(COLOR_TEXT))

        # y 轴线（左侧竖线）
        painter.setPen(QColor(COLOR_GRID))
        painter.drawLine(plot_x, plot_y, plot_x, plot_y + plot_h)

        # 折线（None 段断开）
        self._draw_line(painter, self._history, self._color, plot_x, plot_y, plot_w, plot_h)

    def _draw_line(
        self,
        painter: QPainter,
        history: list[float | None],
        color: str,
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> None:
        """画一条折线，None 段断开（无数据时不连线）。"""
        if not history:
            painter.setPen(QColor(COLOR_NA))
            painter.drawLine(x, y + h // 2, x + w, y + h // 2)
            return
        painter.setPen(QColor(color))
        step_x = w / max(HISTORY_SECONDS - 1, 1)
        prev_x: int | None = None
        prev_y: int | None = None
        for i, val in enumerate(history):
            cur_x = x + int(i * step_x)
            if val is None:
                prev_x = None
                prev_y = None
                continue
            cur_y = y + int(h * (1 - val / 100))
            if prev_x is not None and prev_y is not None:
                painter.drawLine(prev_x, prev_y, cur_x, cur_y)
            prev_x = cur_x
            prev_y = cur_y
        if all(v is None for v in history):
            painter.setPen(QColor(COLOR_NA))
            painter.drawLine(x, y + h // 2, x + w, y + h // 2)


class HardwareMonitorWindow(QWidget):
    """硬件监控独立顶级窗口（v0.0.15 修订）：6 个 MonitorCell（2 列 × 3 行）+ 后台 worker。

    v0.0.15 修订（用户反馈"不是弹出式面板要独立 UI 窗口"）：
    - parent=None + Qt.WindowType.Window flag → 独立顶级窗口，不依附 MainWindow
    - Windows 任务栏显示独立条目，自带标题栏 + X 关闭按钮
    - 关闭时 emit closed 信号 → MainWindow 清空 _hw_window 引用（下次"打开监控"重新实例化）
    - closeEvent 优雅停止 worker

    启动 worker 后开始采集；关闭窗口时 worker.stop() + wait 优雅退出。
    无 NVIDIA 显卡时 GPU/VRAM/GPU°C 折线画灰色 N/A 占位；CPU°C 永远 N/A（Windows psutil 限制）。
    """

    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # 独立顶级窗口：Qt.Window flag 明确不依附父窗口
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle("硬件监控 - Q-agent")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setObjectName("HardwareMonitorWindow")

        # 6 个 MonitorCell（按 METRICS 顺序）
        self._cells: dict[str, MonitorCell] = {}
        for key, label, color, unit in METRICS:
            self._cells[key] = MonitorCell(key, label, color, unit, self)

        # 布局：顶部标题 + 下方 2×3 网格
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("硬件监控 - 6 指标 60s 历史", self)
        title.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px; padding: 4px;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (key, _label, _color, _unit) in enumerate(METRICS):
            row, col = divmod(i, 2)
            grid.addWidget(self._cells[key], row, col)
        layout.addLayout(grid)

        self.setLayout(layout)

        # 后台 worker
        self._worker = HardwareMonitorWorker(parent=self)
        self._worker.sample_collected.connect(self._on_sample)

    def start(self) -> None:
        """启动后台采集 worker（show 后调用）。"""
        if not self._worker.isRunning():
            self._worker.start()

    def stop(self) -> None:
        """关闭 worker（关闭窗口时调用）。"""
        self._worker.stop()
        self._worker.wait(2000)

    def _on_sample(self, sample: dict[str, float | None]) -> None:
        """新样本到达 → 分发给 6 个 cell。"""
        for key in self._cells:
            self._cells[key].set_sample(sample.get(key))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: ANN001
        """窗口关闭时：停止 worker + emit closed 通知 MainWindow 清引用。"""
        self.stop()
        self.closed.emit()
        super().closeEvent(event)
