"""SummaryWorker 测试（v0.0.18 骨架）。

骨架版 _summarize_block / _merge_summaries 是占位实现，不调真 Ollama。
测试信号触发 + stop 标志 + 骨架占位输出格式。
"""

from __future__ import annotations

import os
from typing import Any

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")


@pytest.fixture(scope="module")
def qapp() -> Any:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_summary_worker_constructs(qapp) -> None:  # noqa: ANN001
    """SummaryWorker 可构造。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker(summary_model="qwen2.5:3b", host="http://localhost:11434")
    assert worker.summary_model == "qwen2.5:3b"
    assert worker.host == "http://localhost:11434"


def test_summary_worker_set_chunks(qapp) -> None:  # noqa: ANN001
    """set_chunks 注入块。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    worker.set_chunks(["chunk1", "chunk2"])
    # 内部 _chunks 应是副本
    assert worker._chunks == ["chunk1", "chunk2"]


def test_summary_worker_stop_flag(qapp) -> None:  # noqa: ANN001
    """stop 设标志。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    assert worker._stop is False
    worker.stop()
    assert worker._stop is True


def test_summary_worker_summarize_block_skeleton(qapp) -> None:  # noqa: ANN001
    """骨架版 _summarize_block 返回占位 + 前 200 字符。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    chunk = "x" * 500
    result = worker._summarize_block(chunk)
    assert "[骨架占位摘要" in result
    assert "x" * 200 in result  # 前 200 字符


def test_summary_worker_merge_summaries_skeleton(qapp) -> None:  # noqa: ANN001
    """骨架版 _merge_summaries 拼接 + 标记。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    result = worker._merge_summaries(["a", "b"])
    assert "[骨架合并摘要" in result
    assert "a" in result
    assert "b" in result


def test_summary_worker_stop_returns_empty_block(qapp) -> None:  # noqa: ANN001
    """stop 标志下 _summarize_block 返回空。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    worker.stop()
    assert worker._summarize_block("chunk") == ""


def test_summary_worker_stop_returns_empty_merge(qapp) -> None:  # noqa: ANN001
    """stop 标志下 _merge_summaries 返回空。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    worker.stop()
    assert worker._merge_summaries(["a", "b"]) == ""


def test_summary_worker_run_single_chunk_emits_completed(qapp) -> None:  # noqa: ANN001
    """run() 单块摘要 → summary_completed 信号触发。

    直接调 run()（不调 start()）同步执行 QThread 入口。
    """
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    worker.set_chunks(["single chunk text"])

    received: list[str] = []
    worker.summary_completed.connect(received.append)
    worker.run()  # 同步执行，不启动线程

    assert len(received) == 1
    assert "[骨架占位摘要" in received[0]


def test_summary_worker_run_multiple_chunks_emits_merged(qapp) -> None:  # noqa: ANN001
    """run() 多块摘要 → 合并后 summary_completed 信号触发。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    worker.set_chunks(["chunk1", "chunk2", "chunk3"])

    received: list[str] = []
    worker.summary_completed.connect(received.append)
    worker.run()

    assert len(received) == 1
    # 多块合并应含合并标记
    assert "[骨架合并摘要" in received[0]


def test_summary_worker_run_empty_chunks_emits_empty(qapp) -> None:  # noqa: ANN001
    """run() 无块 → summary_completed 触发空字符串。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    worker.set_chunks([])

    received: list[str] = []
    worker.summary_completed.connect(received.append)
    worker.run()

    assert received == [""]


def test_summary_worker_run_stop_before_complete(qapp) -> None:  # noqa: ANN001
    """run() 在 stop 标志下早退，不发信号。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    worker.set_chunks(["chunk1", "chunk2"])
    worker.stop()  # 启动前就 stop

    received: list[str] = []
    worker.summary_completed.connect(received.append)
    worker.run()

    # stop 后 run() 应早退，不 emit
    assert received == []


def test_summary_worker_run_failure_emits_failed(qapp) -> None:  # noqa: ANN001
    """run() 抛异常 → summary_failed 信号触发。"""
    from q_agent.orchestrator.summary_worker import SummaryWorker

    worker = SummaryWorker()
    worker.set_chunks(["chunk"])

    # 让 _summarize_block 抛异常
    def boom(_chunk: str) -> str:
        raise RuntimeError("摘要模型爆炸")

    worker._summarize_block = boom  # type: ignore[method-assign]

    failures: list[str] = []
    worker.summary_failed.connect(failures.append)
    worker.run()

    assert len(failures) == 1
    assert "RuntimeError" in failures[0]
    assert "摘要模型爆炸" in failures[0]
