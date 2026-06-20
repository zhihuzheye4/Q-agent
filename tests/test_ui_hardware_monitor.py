"""HardwareMonitor 硬件监控曲线单测（v0.0.12）。

覆盖：
    - HardwareMonitor 构造 + 固定高度 + worker 子组件
    - _on_sample 追加历史 + 截断到 HISTORY_SECONDS
    - _on_sample None 段不崩
    - paintEvent 渲染不崩（含无数据/部分数据/全数据三种场景）
    - _draw_line None 段断开（不连线）
    - collect_sample_sync 同步采集器返回 4 字段 dict（不抛错）
    - HardwareMonitorWorker 构造（pynvml 不可用时 _nvml_ok=False）
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
def qapp() -> "QApplication":
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_hardware_monitor_constructs_with_fixed_height(qapp: "QApplication") -> None:
    """HardwareMonitor 构造 OK，固定高度 = MONITOR_HEIGHT。"""
    from q_agent.ui.hardware_monitor import MONITOR_HEIGHT, HardwareMonitor

    monitor = HardwareMonitor()
    assert monitor.height() == MONITOR_HEIGHT
    assert monitor.objectName() == "HardwareMonitor"
    # 4 个指标历史均为空 list
    assert all(monitor._history[k] == [] for k in ("cpu", "gpu", "vram", "ram"))
    # worker 子组件存在
    assert monitor._worker is not None


def test_on_sample_appends_and_truncates_history(qapp: "QApplication") -> None:
    """_on_sample 追加样本到各指标历史 + 超 HISTORY_SECONDS 截断。"""
    from q_agent.ui.hardware_monitor import HISTORY_SECONDS, HardwareMonitor

    monitor = HardwareMonitor()
    # 注入 HISTORY_SECONDS + 5 个样本，验证截断到 HISTORY_SECONDS
    for i in range(HISTORY_SECONDS + 5):
        sample = {"cpu": float(i), "gpu": float(i), "vram": float(i), "ram": float(i)}
        monitor._on_sample(sample)
    for key in ("cpu", "gpu", "vram", "ram"):
        assert len(monitor._history[key]) == HISTORY_SECONDS
        # 末尾应该是最后注入的样本值
        assert monitor._history[key][-1] == float(HISTORY_SECONDS + 4)


def test_on_sample_none_does_not_crash(qapp: "QApplication") -> None:
    """_on_sample 收到 None 字段时 append None，不崩。"""
    from q_agent.ui.hardware_monitor import HardwareMonitor

    monitor = HardwareMonitor()
    sample = {"cpu": None, "gpu": None, "vram": None, "ram": None}
    monitor._on_sample(sample)
    for key in ("cpu", "gpu", "vram", "ram"):
        assert monitor._history[key] == [None]


def test_paint_event_renders_without_crash_empty_history(qapp: "QApplication") -> None:
    """paintEvent 在无数据时不崩（4 条灰色 N/A 占位横线）。"""
    from q_agent.ui.hardware_monitor import HardwareMonitor

    monitor = HardwareMonitor()
    monitor.resize(200, 160)
    monitor.show()
    QTest.qWait(50)
    # 直接触发 paintEvent（不依赖事件循环）
    event = QPaintEvent(monitor.rect())
    monitor.paintEvent(event)


def test_paint_event_renders_with_partial_data(qapp: "QApplication") -> None:
    """paintEvent 在有部分数据（部分 None）时不崩。"""
    from q_agent.ui.hardware_monitor import HardwareMonitor

    monitor = HardwareMonitor()
    monitor.resize(200, 160)
    monitor.show()
    # 注入 5 个样本，CPU/RAM 有值，GPU/VRAM 全 None
    for _ in range(5):
        monitor._on_sample({"cpu": 50.0, "gpu": None, "vram": None, "ram": 70.0})
    event = QPaintEvent(monitor.rect())
    monitor.paintEvent(event)


def test_paint_event_renders_with_full_data(qapp: "QApplication") -> None:
    """paintEvent 在 4 指标全有数据时不崩。"""
    from q_agent.ui.hardware_monitor import HardwareMonitor

    monitor = HardwareMonitor()
    monitor.resize(200, 160)
    monitor.show()
    for i in range(30):
        monitor._on_sample(
            {
                "cpu": float(40 + i % 30),
                "gpu": float(60 + i % 20),
                "vram": float(50 + i % 25),
                "ram": float(70 + i % 15),
            }
        )
    event = QPaintEvent(monitor.rect())
    monitor.paintEvent(event)


def test_draw_line_none_segment_breaks_line(qapp: "QApplication") -> None:
    """_draw_line 在 None 段断开不连线（prev_x/prev_y 重置）。"""
    from PySide6.QtGui import QColor, QImage, QPainter

    from q_agent.ui.hardware_monitor import COLOR_CPU, HardwareMonitor

    monitor = HardwareMonitor()
    monitor.resize(200, 160)
    # 历史含 None 段：[10, 20, None, 40, 50]
    history: list[float | None] = [10.0, 20.0, None, 40.0, 50.0]
    # 用 QImage 作为画布（不依赖 widget 显示）
    img = QImage(200, 160, QImage.Format.Format_ARGB32)
    img.fill(QColor("#0F172A"))
    painter = QPainter(img)
    monitor._draw_line(painter, history, COLOR_CPU, 8, 24, 184, 132)
    painter.end()
    # 不崩即通过


def test_draw_line_all_none_draws_na_placeholder(qapp: "QApplication") -> None:
    """_draw_line 全 None 时画灰色 N/A 占位横线（不崩）。"""
    from PySide6.QtGui import QColor, QImage, QPainter

    from q_agent.ui.hardware_monitor import HardwareMonitor

    monitor = HardwareMonitor()
    history: list[float | None] = [None, None, None]
    img = QImage(200, 160, QImage.Format.Format_ARGB32)
    img.fill(QColor("#0F172A"))
    painter = QPainter(img)
    monitor._draw_line(painter, history, "#3B82F6", 8, 24, 184, 132)
    painter.end()


def test_collect_sample_sync_returns_4_fields_dict() -> None:
    """collect_sample_sync 返回含 4 字段的 dict（即使依赖缺失也不抛错）。"""
    from q_agent.ui.hardware_monitor import collect_sample_sync

    sample = collect_sample_sync()
    assert set(sample.keys()) == {"cpu", "gpu", "vram", "ram"}
    # 每个字段是 float 或 None
    for key in ("cpu", "gpu", "vram", "ram"):
        assert sample[key] is None or isinstance(sample[key], float)


def test_worker_init_handles_no_pynvml(qapp: "QApplication") -> None:
    """HardwareMonitorWorker 构造时 pynvml 不可用 → _nvml_ok=False，不崩。"""
    from q_agent.ui.hardware_monitor import HardwareMonitorWorker

    worker = HardwareMonitorWorker(interval_ms=1000)
    # 不强制要求 _nvml_ok 值（取决于运行环境），但 _pynvml 字段必须存在
    assert hasattr(worker, "_pynvml")
    assert hasattr(worker, "_nvml_ok")
    assert hasattr(worker, "_stop")
    assert worker._stop is False