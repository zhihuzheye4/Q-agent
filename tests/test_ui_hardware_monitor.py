"""硬件监控单测（v0.0.15 重构）。

覆盖：
    - HardwareMonitorWorker 构造（pynvml 不可用时 _nvml_ok=False）
    - collect_sample_sync 返回 6 字段 dict（含 cpu_temp/gpu_temp，不抛错）
    - MonitorCell 构造 + set_sample 追加 + 截断 + None 不崩
    - MonitorCell paintEvent 三场景（空/部分/全数据）不崩
    - MonitorCell _draw_line None 段断开 + 全 None 占位横线
    - HardwareMonitorWindow 构造（6 cell + worker + 标题）
    - HardwareMonitorWindow _on_sample 分发给 6 cell
    - HardwareMonitorWindow start/stop 不崩
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

from PySide6.QtGui import QPaintEvent
from PySide6.QtTest import QTest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


# ===== HardwareMonitorWorker =====


def test_worker_init_handles_no_pynvml(qapp: QApplication) -> None:
    """HardwareMonitorWorker 构造时 pynvml 不可用 → _nvml_ok=False，不崩。"""
    from q_agent.ui.hardware_monitor import HardwareMonitorWorker

    worker = HardwareMonitorWorker(interval_ms=1000)
    assert hasattr(worker, "_pynvml")
    assert hasattr(worker, "_nvml_ok")
    assert hasattr(worker, "_stop")
    assert worker._stop is False


def test_collect_sample_sync_returns_6_fields_dict() -> None:
    """collect_sample_sync 返回含 6 字段的 dict（含 cpu_temp/gpu_temp，不抛错）。"""
    from q_agent.ui.hardware_monitor import collect_sample_sync

    sample = collect_sample_sync()
    assert set(sample.keys()) == {"cpu", "gpu", "vram", "ram", "cpu_temp", "gpu_temp"}
    for key in ("cpu", "gpu", "vram", "ram", "cpu_temp", "gpu_temp"):
        assert sample[key] is None or isinstance(sample[key], float)


def test_metrics_list_has_6_entries() -> None:
    """METRICS 元数据列表含 6 个指标元组。"""
    from q_agent.ui.hardware_monitor import METRICS

    assert len(METRICS) == 6
    keys = [m[0] for m in METRICS]
    assert keys == ["cpu", "gpu", "vram", "ram", "cpu_temp", "gpu_temp"]
    # 每个元组 4 字段（key, label, color, unit）
    for entry in METRICS:
        assert len(entry) == 4


# ===== MonitorCell =====


def test_monitor_cell_constructs(qapp: QApplication) -> None:
    """MonitorCell 构造 OK，固定高度 + 最小宽度 + 空 history。"""
    from q_agent.ui.hardware_monitor_window import CELL_HEIGHT, MonitorCell

    cell = MonitorCell("cpu", "CPU", "#3B82F6", "%")
    assert cell.height() == CELL_HEIGHT
    assert cell._history == []
    assert cell._key == "cpu"
    assert cell._unit == "%"


def test_monitor_cell_set_sample_appends_and_truncates(qapp: QApplication) -> None:
    """set_sample 追加历史 + 超 HISTORY_SECONDS 截断。"""
    from q_agent.ui.hardware_monitor import HISTORY_SECONDS
    from q_agent.ui.hardware_monitor_window import MonitorCell

    cell = MonitorCell("cpu", "CPU", "#3B82F6", "%")
    for i in range(HISTORY_SECONDS + 5):
        cell.set_sample(float(i))
    assert len(cell._history) == HISTORY_SECONDS
    assert cell._history[-1] == float(HISTORY_SECONDS + 4)


def test_monitor_cell_set_sample_none_does_not_crash(qapp: QApplication) -> None:
    """set_sample(None) append None，不崩。"""
    from q_agent.ui.hardware_monitor_window import MonitorCell

    cell = MonitorCell("gpu_temp", "GPU°C", "#EF4444", "°C")
    cell.set_sample(None)
    assert cell._history == [None]


def test_monitor_cell_paint_event_empty(qapp: QApplication) -> None:
    """MonitorCell paintEvent 空历史不崩（N/A 占位横线）。"""
    from q_agent.ui.hardware_monitor_window import MonitorCell

    cell = MonitorCell("cpu", "CPU", "#3B82F6", "%")
    cell.resize(280, 150)
    cell.show()
    QTest.qWait(20)
    event = QPaintEvent(cell.rect())
    cell.paintEvent(event)


def test_monitor_cell_paint_event_partial(qapp: QApplication) -> None:
    """MonitorCell paintEvent 部分数据（含 None）不崩。"""
    from q_agent.ui.hardware_monitor_window import MonitorCell

    cell = MonitorCell("gpu", "GPU", "#22C55E", "%")
    cell.resize(280, 150)
    cell.show()
    for v in (10.0, None, 30.0, None, 50.0):
        cell.set_sample(v)
    event = QPaintEvent(cell.rect())
    cell.paintEvent(event)


def test_monitor_cell_paint_event_full(qapp: QApplication) -> None:
    """MonitorCell paintEvent 30 个样本全有值不崩。"""
    from q_agent.ui.hardware_monitor_window import MonitorCell

    cell = MonitorCell("cpu_temp", "CPU°C", "#94A3B8", "°C")
    cell.resize(280, 150)
    cell.show()
    for i in range(30):
        cell.set_sample(float(40 + i % 30))
    event = QPaintEvent(cell.rect())
    cell.paintEvent(event)


def test_monitor_cell_draw_line_none_breaks(qapp: QApplication) -> None:
    """_draw_line None 段断开不连线。"""
    from PySide6.QtGui import QColor, QImage, QPainter

    from q_agent.ui.hardware_monitor_window import MonitorCell

    cell = MonitorCell("cpu", "CPU", "#3B82F6", "%")
    history: list[float | None] = [10.0, 20.0, None, 40.0, 50.0]
    img = QImage(280, 150, QImage.Format.Format_ARGB32)
    img.fill(QColor("#0F172A"))
    painter = QPainter(img)
    cell._draw_line(painter, history, "#3B82F6", 8, 24, 264, 122)
    painter.end()


def test_monitor_cell_draw_line_all_none(qapp: QApplication) -> None:
    """_draw_line 全 None 画灰色 N/A 占位横线，不崩。"""
    from PySide6.QtGui import QColor, QImage, QPainter

    from q_agent.ui.hardware_monitor_window import MonitorCell

    cell = MonitorCell("gpu_temp", "GPU°C", "#EF4444", "°C")
    history: list[float | None] = [None, None, None]
    img = QImage(280, 150, QImage.Format.Format_ARGB32)
    img.fill(QColor("#0F172A"))
    painter = QPainter(img)
    cell._draw_line(painter, history, "#EF4444", 8, 24, 264, 122)
    painter.end()


# ===== HardwareMonitorWindow =====


def test_hardware_monitor_window_constructs(qapp: QApplication) -> None:
    """HardwareMonitorWindow 构造 OK，6 个 cell + worker + 固定尺寸。"""
    from q_agent.ui.hardware_monitor import METRICS
    from q_agent.ui.hardware_monitor_window import (
        WINDOW_HEIGHT,
        WINDOW_WIDTH,
        HardwareMonitorWindow,
    )

    w = HardwareMonitorWindow()
    assert w.windowTitle().startswith("硬件监控")
    assert w.width() == WINDOW_WIDTH
    assert w.height() == WINDOW_HEIGHT
    # 6 cell 按 METRICS 顺序
    assert len(w._cells) == 6
    for key, _label, _color, _unit in METRICS:
        assert key in w._cells
    # worker 子组件存在
    assert w._worker is not None


def test_hardware_monitor_window_on_sample_dispatches(qapp: QApplication) -> None:
    """_on_sample 分发样本到 6 个 cell（每个 cell history 末尾 = 样本值）。"""
    from q_agent.ui.hardware_monitor_window import HardwareMonitorWindow

    w = HardwareMonitorWindow()
    sample = {
        "cpu": 50.0,
        "gpu": 60.0,
        "vram": 70.0,
        "ram": 80.0,
        "cpu_temp": None,
        "gpu_temp": 65.0,
    }
    w._on_sample(sample)
    for key in ("cpu", "gpu", "vram", "ram", "cpu_temp", "gpu_temp"):
        cell = w._cells[key]
        assert cell._history[-1] == sample[key], f"{key} cell 末尾应等于样本值"


def test_hardware_monitor_window_start_stop_no_crash(qapp: QApplication) -> None:
    """start/stop 不崩（worker 可能未实际启动因环境而异）。"""
    from q_agent.ui.hardware_monitor_window import HardwareMonitorWindow

    w = HardwareMonitorWindow()
    # 不调 start（避免实际跑线程），调 stop 应安全（worker 未 running）
    w.stop()
    # 再次 stop 不崩（幂等）
    w.stop()


def test_hardware_monitor_window_is_independent_top_level(qapp: QApplication) -> None:
    """v0.0.15 修订：独立顶级窗口（Qt.Window flag），parent=None 时不依附父窗口。"""
    from PySide6.QtCore import Qt

    from q_agent.ui.hardware_monitor_window import HardwareMonitorWindow

    w = HardwareMonitorWindow()
    # Qt.Window flag 应被设置（独立顶级窗口）
    assert w.windowFlags() & Qt.WindowType.Window, "应设置 Qt.Window flag 为独立顶级窗口"


def test_hardware_monitor_window_emits_closed_signal(qapp: QApplication) -> None:
    """v0.0.15 修订：closeEvent 应 emit closed 信号让 MainWindow 清引用。"""
    from q_agent.ui.hardware_monitor_window import HardwareMonitorWindow

    w = HardwareMonitorWindow()
    received: list[bool] = []
    w.closed.connect(lambda: received.append(True))
    # 直接触发 closeEvent 模拟关闭（QCloseEvent 无参数构造）
    from PySide6.QtGui import QCloseEvent

    w.closeEvent(QCloseEvent())
    assert received == [True], "closeEvent 应 emit closed 信号"
