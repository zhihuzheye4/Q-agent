"""硬件监控：sidebar 底部常驻 4 条折线图，60s 历史实时显示。

指标（v0.0.12 用户已确认）：
    - CPU 占用%（蓝）
    - GPU 利用率%（绿）
    - VRAM 占用%（紫）
    - RAM%（橙）

数据源（v0.0.12 用户已确认引入运行时依赖，PyInstaller 打包进 .exe，符合 ADR-015）：
    - psutil：CPU + RAM 跨平台
    - pynvml（nvidia-ml-py）：NVIDIA GPU 利用率 + 显存，无 NVIDIA 显卡时 N/A

线程模型：
    - HardwareMonitorWorker(QThread)：1s 采集一次样本，emit sample_collected(dict)
    - HardwareMonitor(QWidget)：主线程接收样本，append 到历史列表，触发重绘
    - 关闭时 worker.stop() 设 _stop flag，run 循环早退

容错：
    - pynvml 初始化失败（无 NVIDIA 显卡 / 驱动问题）→ GPU/VRAM 永远 None，折线画灰色 N/A 占位
    - 采集时单指标异常 → 该指标 None，不影响其他指标
"""

from __future__ import annotations

import contextlib

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

# 折线历史长度（秒）= 样本数（1s 一个样本）
HISTORY_SECONDS = 60
# 采样间隔（毫秒）
SAMPLE_INTERVAL_MS = 1000
# 固定高度（sidebar 底部常驻，留出 4 条折线 + 图例 + 边距）
MONITOR_HEIGHT = 160

# 4 指标颜色（与设计规范色板对齐，4 色高对比可区分）
COLOR_CPU = "#3B82F6"  # 蓝
COLOR_GPU = "#22C55E"  # 绿
COLOR_VRAM = "#A855F7"  # 紫
COLOR_RAM = "#F97316"  # 橙
COLOR_NA = "#475569"  # 灰（无数据占位线）
COLOR_GRID = "#1E293B"  # 网格线
COLOR_TEXT = "#94A3B8"  # 图例文本

# 指标元数据：(key, label, color)
METRICS: list[tuple[str, str, str]] = [
    ("cpu", "CPU", COLOR_CPU),
    ("gpu", "GPU", COLOR_GPU),
    ("vram", "VRAM", COLOR_VRAM),
    ("ram", "RAM", COLOR_RAM),
]


class HardwareMonitorWorker(QThread):
    """后台采集硬件指标样本，1s 一个样本 emit 给主线程。

    pynvml 初始化失败（无 NVIDIA 显卡 / 驱动问题）时 gpu/vram 永远 None。
    psutil.cpu_percent 第一次调用返回 0，启动时阻塞 100ms 预热一个基线。
    """

    sample_collected = Signal(object)  # dict[str, float | None]

    def __init__(
        self, interval_ms: int = SAMPLE_INTERVAL_MS, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._stop = False
        self._nvml_ok = False
        try:
            import pynvml  # type: ignore[import-untyped]

            pynvml.nvmlInit()
            self._nvml_ok = True
            self._pynvml = pynvml  # 保留引用供 run 内调用
        except Exception:
            self._nvml_ok = False
            self._pynvml = None

    def run(self) -> None:
        # psutil.cpu_percent 第一次调用返回 0，预热一个基线
        try:
            import psutil  # type: ignore[import-untyped]

            psutil.cpu_percent(interval=0.1)
            self._psutil = psutil
        except Exception:
            self._psutil = None

        while not self._stop:
            sample = self._collect()
            if not self._stop:
                self.sample_collected.emit(sample)
            self.msleep(self._interval_ms)

    def _collect(self) -> dict[str, float | None]:
        sample: dict[str, float | None] = {"cpu": None, "gpu": None, "vram": None, "ram": None}
        # CPU + RAM
        if self._psutil is not None:
            try:
                sample["cpu"] = float(self._psutil.cpu_percent(interval=None))
            except Exception:
                sample["cpu"] = None
            try:
                sample["ram"] = float(self._psutil.virtual_memory().percent)
            except Exception:
                sample["ram"] = None
        # GPU + VRAM
        if self._nvml_ok and self._pynvml is not None:
            try:
                handle = self._pynvml.nvmlDeviceGetHandleByIndex(0)
                util = self._pynvml.nvmlDeviceGetUtilizationRates(handle)
                sample["gpu"] = float(util.gpu)
                mem = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
                sample["vram"] = float(mem.used / mem.total * 100.0) if mem.total else 0.0
            except Exception:
                sample["gpu"] = None
                sample["vram"] = None
        return sample

    def stop(self) -> None:
        """请求线程退出循环。主线程关闭窗口时调用。"""
        self._stop = True
        if self._nvml_ok and self._pynvml is not None:
            with contextlib.suppress(Exception):
                self._pynvml.nvmlShutdown()


class HardwareMonitor(QWidget):
    """sidebar 底部常驻硬件监控曲线图，4 条折线 60s 历史。

    启动 worker 后开始采集；关闭窗口时 worker.stop() 优雅退出。
    无 NVIDIA 显卡时 GPU/VRAM 折线画灰色 N/A 占位。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HardwareMonitor")
        self.setFixedHeight(MONITOR_HEIGHT)
        # 4 条折线历史（60s × 1s/样本 = 60 个点）
        self._history: dict[str, list[float | None]] = {
            "cpu": [],
            "gpu": [],
            "vram": [],
            "ram": [],
        }
        self._worker = HardwareMonitorWorker(SAMPLE_INTERVAL_MS, parent=self)
        self._worker.sample_collected.connect(self._on_sample)

    def start(self) -> None:
        """启动后台采集 worker（MainWindow show 后调用）。"""
        if not self._worker.isRunning():
            self._worker.start()

    def stop(self) -> None:
        """关闭 worker（MainWindow close 时调用）。"""
        self._worker.stop()
        self._worker.wait(2000)

    def _on_sample(self, sample: dict[str, float | None]) -> None:
        """新样本到达 → append 到各指标历史 + 截断到 HISTORY_SECONDS + 触发重绘。"""
        for key, _label, _color in METRICS:
            self._history[key].append(sample.get(key))
            if len(self._history[key]) > HISTORY_SECONDS:
                del self._history[key][0]
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ANN001, ARG002
        """自绘 4 条折线 + 图例 + 当前数值。

        布局（MONITOR_HEIGHT=160px）：
            - 顶部 20px：4 个图例小色块 + 名称 + 当前数值
            - 下方 140px：折线图区域，4 条折线叠加，0-100% y 轴
        """
        from PySide6.QtGui import QFont

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 背景（与 sidebar 同色，避免突兀）
        painter.fillRect(0, 0, w, h, QColor("#0F172A"))

        # 顶部图例区（20px）
        legend_h = 20
        legend_y = 4
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        x = 8
        for key, label, color in METRICS:
            # 色块
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(x, legend_y, 8, 8)
            # 名称 + 当前数值
            painter.setPen(QColor(COLOR_TEXT))
            history = self._history[key]
            last = history[-1] if history else None
            last_str = f"{last:.0f}%" if last is not None else "N/A"
            text = f"{label} {last_str}"
            painter.drawText(x + 12, legend_y + 9, text)
            x += 12 + painter.fontMetrics().horizontalAdvance(text) + 12

        # 折线图区域
        plot_y = legend_h + 4
        plot_h = h - plot_y - 4
        plot_w = w - 16
        plot_x = 8

        # 网格线（25%/50%/75%）
        painter.setPen(QColor(COLOR_GRID))
        for pct in (25, 50, 75):
            y = plot_y + int(plot_h * (1 - pct / 100))
            painter.drawLine(plot_x, y, plot_x + plot_w, y)

        # 4 条折线（每条独立画，None 段断开）
        for key, _label, color in METRICS:
            self._draw_line(painter, self._history[key], color, plot_x, plot_y, plot_w, plot_h)

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
            # 无数据画灰色 N/A 占位横线
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
                # None 段断开
                prev_x = None
                prev_y = None
                continue
            cur_y = y + int(h * (1 - val / 100))
            if prev_x is not None and prev_y is not None:
                painter.drawLine(prev_x, prev_y, cur_x, cur_y)
            prev_x = cur_x
            prev_y = cur_y
        # 如果整段都是 None，画灰色 N/A 占位（history 非空但所有值 None）
        if all(v is None for v in history):
            painter.setPen(QColor(COLOR_NA))
            painter.drawLine(x, y + h // 2, x + w, y + h // 2)


# 测试辅助：不依赖 QThread 的同步采集器，便于单测
def collect_sample_sync() -> dict[str, float | None]:
    """同步采集一个硬件样本（测试用，不依赖 worker 线程）。

    异常容错：psutil / pynvml 不可用时对应字段 None，不抛错。
    """
    sample: dict[str, float | None] = {"cpu": None, "gpu": None, "vram": None, "ram": None}
    with contextlib.suppress(Exception):
        import psutil

        sample["cpu"] = float(psutil.cpu_percent(interval=None))
        sample["ram"] = float(psutil.virtual_memory().percent)
    with contextlib.suppress(Exception):
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        sample["gpu"] = float(util.gpu)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        sample["vram"] = float(mem.used / mem.total * 100.0) if mem.total else 0.0
        pynvml.nvmlShutdown()
    return sample
