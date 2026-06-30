"""硬件监控：后台采集 6 指标 + 1s 采样（v0.0.15 重构）。

v0.0.15 改造（模块化）：
- 删除 v0.0.12 旧 HardwareMonitor widget（sidebar 底部常驻折线，已被 left panel 移除挂载）
- HardwareMonitorWorker 扩展采集温度：CPU 温度（Windows psutil 不支持，永远 None）
  + GPU 温度（pynvml NVML_TEMPERATURE_GPU）
- HardwareMonitorWindow 独立窗口由 menu_bar "监控"菜单触发弹出（新文件 hardware_monitor_window.py）

指标（v0.0.15 6 个）：
    - CPU 占用%（psutil.cpu_percent）
    - GPU 利用率%（pynvml nvmlDeviceGetUtilizationRates）
    - VRAM 占用%（pynvml nvmlDeviceGetMemoryInfo）
    - RAM%（psutil.virtual_memory）
    - CPU 温度°C（Windows psutil 不支持 sensors_temperatures，永远 None）
    - GPU 温度°C（pynvml nvmlDeviceGetTemperature NVML_TEMPERATURE_GPU）

数据源：
    - psutil：CPU + RAM 跨平台（温度 Windows 不支持）
    - pynvml（nvidia-ml-py）：NVIDIA GPU 利用率 + 显存 + 温度，无 NVIDIA 显卡时 N/A

线程模型：
    - HardwareMonitorWorker(QThread)：1s 采集一次样本，emit sample_collected(dict)
    - HardwareMonitorWindow(QWidget)：主线程接收样本，append 到各指标历史，触发重绘
    - 关闭时 worker.stop() 设 _stop flag，run 循环早退

容错：
    - pynvml 初始化失败（无 NVIDIA 显卡 / 驱动问题）→ GPU/VRAM/GPU 温度永远 None
    - CPU 温度 Windows 永远 None（psutil 限制）
    - 采集时单指标异常 → 该指标 None，不影响其他指标
"""

from __future__ import annotations

import contextlib

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

# 折线历史长度（秒）= 样本数（1s 一个样本）
HISTORY_SECONDS = 60
# 采样间隔（毫秒）
SAMPLE_INTERVAL_MS = 1000

# 6 指标颜色（CPU/GPU/VRAM/RAM 沿用 v0.0.12，温度加 2 色）
COLOR_CPU = "#3B82F6"  # 蓝
COLOR_GPU = "#22C55E"  # 绿
COLOR_VRAM = "#A855F7"  # 紫
COLOR_RAM = "#F97316"  # 橙
COLOR_CPU_TEMP = "#94A3B8"  # 灰蓝（CPU 温度，Windows N/A）
COLOR_GPU_TEMP = "#EF4444"  # 红（GPU 温度）
COLOR_NA = "#475569"  # 灰（无数据占位线）
COLOR_GRID = "#334155"  # 网格线（v0.0.15 修订加深，配合 plot 背景区分）
COLOR_TEXT = "#94A3B8"  # 图例文本 / y 轴刻度
COLOR_CELL_BG = "#0F172A"  # cell 整体背景（与主窗口同色）
COLOR_PLOT_BG = "#1E293B"  # plot 坐标系背景（v0.0.15 修订新增，与 cell 背景区分）

# 指标元数据：(key, label, color, unit)
# unit: "%" 百分比 0-100 / "°C" 温度 0-100°C（数值范围巧合一致，可共用 y 轴）
# label v0.0.15 修订中文化
METRICS: list[tuple[str, str, str, str]] = [
    ("cpu", "CPU 占用率", COLOR_CPU, "%"),
    ("gpu", "GPU 利用率", COLOR_GPU, "%"),
    ("vram", "显存占用率", COLOR_VRAM, "%"),
    ("ram", "内存占用率", COLOR_RAM, "%"),
    ("cpu_temp", "CPU 温度", COLOR_CPU_TEMP, "°C"),
    ("gpu_temp", "GPU 温度", COLOR_GPU_TEMP, "°C"),
]


class HardwareMonitorWorker(QThread):
    """后台采集硬件指标样本，1s 一个样本 emit 给主线程。

    pynvml 初始化失败（无 NVIDIA 显卡 / 驱动问题）时 gpu/vram/gpu_temp 永远 None。
    psutil.cpu_percent 第一次调用返回 0，启动时阻塞 100ms 预热一个基线。
    Windows psutil 不支持 sensors_temperatures，cpu_temp 永远 None。
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
        sample: dict[str, float | None] = {
            "cpu": None,
            "gpu": None,
            "vram": None,
            "ram": None,
            "cpu_temp": None,  # Windows psutil 不支持，永远 None
            "gpu_temp": None,
        }
        # CPU + RAM（psutil 跨平台）
        if self._psutil is not None:
            try:
                sample["cpu"] = float(self._psutil.cpu_percent(interval=None))
            except Exception:
                sample["cpu"] = None
            try:
                sample["ram"] = float(self._psutil.virtual_memory().percent)
            except Exception:
                sample["ram"] = None
        # GPU + VRAM + GPU 温度（pynvml NVIDIA）
        if self._nvml_ok and self._pynvml is not None:
            try:
                handle = self._pynvml.nvmlDeviceGetHandleByIndex(0)
                util = self._pynvml.nvmlDeviceGetUtilizationRates(handle)
                sample["gpu"] = float(util.gpu)
                mem = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
                sample["vram"] = float(mem.used / mem.total * 100.0) if mem.total else 0.0
                # GPU 温度（NVML_TEMPERATURE_GPU = 0）
                sample["gpu_temp"] = float(self._pynvml.nvmlDeviceGetTemperature(handle, 0))
            except Exception:
                sample["gpu"] = None
                sample["vram"] = None
                sample["gpu_temp"] = None
        return sample

    def stop(self) -> None:
        """请求线程退出循环。主线程关闭窗口时调用。"""
        self._stop = True
        if self._nvml_ok and self._pynvml is not None:
            with contextlib.suppress(Exception):
                self._pynvml.nvmlShutdown()


# 测试辅助：不依赖 QThread 的同步采集器，便于单测
def collect_sample_sync() -> dict[str, float | None]:
    """同步采集一个硬件样本（测试用，不依赖 worker 线程）。

    异常容错：psutil / pynvml 不可用时对应字段 None，不抛错。
    """
    sample: dict[str, float | None] = {
        "cpu": None,
        "gpu": None,
        "vram": None,
        "ram": None,
        "cpu_temp": None,  # Windows psutil 不支持
        "gpu_temp": None,
    }
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
        sample["gpu_temp"] = float(pynvml.nvmlDeviceGetTemperature(handle, 0))
        pynvml.nvmlShutdown()
    return sample
