"""Orchestrator 主循环测试（v0.0.18）。

mock LLM + mock executor + mock SummaryWorker + 临时 sqlite3。
覆盖 10 步主循环各路径：自然停止 / 工具循环 / LLM 失败 / doom_loop / max_steps / 压缩触发。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from q_agent.orchestrator.context import ContextConfig, ContextManager
from q_agent.orchestrator.loop import Orchestrator
from q_agent.orchestrator.persistence import SessionStore
from q_agent.orchestrator.types import Role, TerminationReason

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")


@pytest.fixture(scope="module")
def qapp() -> Any:
    """QApplication fixture（SummaryWorker 是 QThread 需 QApp）。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    """临时 SessionStore。"""
    s = SessionStore(tmp_path / "test.db")
    s.create_session("s1")
    return s


@pytest.fixture
def context(store: SessionStore, tmp_path: Path) -> ContextManager:
    """临时 ContextManager。"""
    return ContextManager(
        session_id="s1",
        session_store=store,
        tool_results_dir=tmp_path / "tool_results",
    )


class MockLLM:
    """mock LLM 客户端，按预设序列返回输出。"""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: int = 0

    def chat(self, messages: list[dict[str, object]]) -> str:
        self.calls += 1
        if self.calls > len(self.responses):
            return ""
        return self.responses[self.calls - 1]


class MockExecutor:
    """mock executor。"""

    def __init__(self, return_value: str = "tool_result") -> None:
        self.return_value = return_value
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute_tool(self, name: str, **kwargs: object) -> str:
        self.calls.append((name, dict(kwargs)))
        return self.return_value


class FailingLLM:
    """永远抛异常的 LLM。"""

    def chat(self, messages: list[dict[str, object]]) -> str:
        raise RuntimeError("Ollama 离线")


# ---- 测试用例 ----


def test_run_turn_llm_stopped_no_tools(qapp, store, context) -> None:  # noqa: ANN001
    """LLM 自然停止（无 tool_calls）→ LLM_STOPPED。"""
    llm = MockLLM(["你好，我是 AI"])
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=MockExecutor(),
    )
    result = orch.run_turn("hi")
    assert result.termination_reason == TerminationReason.LLM_STOPPED
    assert result.final_assistant_text == "你好，我是 AI"
    assert result.tool_calls_made == []


def test_run_turn_with_tool_call_then_stop(qapp, store, context) -> None:  # noqa: ANN001
    """LLM 调工具 → 工具结果回喂 → LLM 自然停止。"""
    llm = MockLLM(
        [
            (
                "正在读取\n```json\n"
                '{"id": "c1", "name": "read_file", "arguments": {"path": "x.py"}}\n```'
            ),
            "读取完成",
        ]
    )
    executor = MockExecutor(return_value="file content")
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=executor,
    )
    result = orch.run_turn("读 x.py")
    assert result.termination_reason == TerminationReason.LLM_STOPPED
    assert len(result.tool_calls_made) == 1
    assert result.tool_calls_made[0].name == "read_file"
    assert executor.calls == [("read_file", {"path": "x.py"})]


def test_run_turn_llm_failure_marks_consecutive_error(qapp, store, context) -> None:  # noqa: ANN001
    """LLM 失败 → 合成 assistant + consecutive_errors 累计 → 超阈值终止。"""
    llm = FailingLLM()
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=MockExecutor(),
        consecutive_error_threshold=3,
        max_steps=10,
    )
    result = orch.run_turn("hi")
    # 3 次失败后终止
    assert result.termination_reason == TerminationReason.CONSECUTIVE_ERRORS


def test_run_turn_doom_loop_detected(qapp, store, context) -> None:  # noqa: ANN001
    """重复相同工具调用 → doom_loop 终止。"""
    # LLM 每次都返回相同的 tool_call
    same_response = '```json\n{"id": "c1", "name": "read_file", "arguments": {"path": "x.py"}}\n```'
    llm = MockLLM([same_response] * 10)
    executor = MockExecutor()
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=executor,
        doom_loop_threshold=3,
        max_steps=20,
    )
    result = orch.run_turn("读 x.py")
    assert result.termination_reason == TerminationReason.DOOM_LOOP


def test_run_turn_max_steps_reached(qapp, store, context) -> None:  # noqa: ANN001
    """达 max_steps 软截止。"""
    # LLM 每次返回不同的工具调用（避免 doom_loop）
    responses = [
        f'```json\n{{"id": "c{i}", "name": "tool_{i}", "arguments": {{}}}}\n```' for i in range(20)
    ]
    llm = MockLLM(responses)
    executor = MockExecutor()
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=executor,
        max_steps=5,
        doom_loop_threshold=100,  # 避免 doom_loop 先触发
    )
    result = orch.run_turn("go")
    assert result.termination_reason == TerminationReason.MAX_STEPS_REACHED


def test_run_turn_tool_result_compacted(qapp, store, context, tmp_path) -> None:  # noqa: ANN001
    """工具结果 > 2000 字符 → 落盘 + 占位回喂。"""
    long_result = "x" * 3000
    llm = MockLLM(
        [
            '```json\n{"id": "c1", "name": "read_big", "arguments": {}}\n```',
            "完成",
        ]
    )
    executor = MockExecutor(return_value=long_result)
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=executor,
    )
    result = orch.run_turn("读大文件")
    assert result.termination_reason == TerminationReason.LLM_STOPPED
    # 检查 tool_result 消息内容被替换为占位
    tool_msgs = [m for m in context.messages if m.role == Role.TOOL]
    assert len(tool_msgs) == 1
    assert "内容已清空" in tool_msgs[0].content


def test_run_turn_on_step_callback(qapp, store, context) -> None:  # noqa: ANN001
    """on_step 回调被调用。"""
    llm = MockLLM(["hello"])
    steps: list[Any] = []
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=MockExecutor(),
        on_step=steps.append,
    )
    orch.run_turn("hi")
    assert len(steps) >= 1


def test_run_turn_on_compaction_callback(qapp, store, context) -> None:  # noqa: ANN001
    """第 2 级压缩触发时 on_compaction 回调。"""
    # max_tokens 设小，触发第 2 级
    context.config = ContextConfig(
        max_tokens=20,
        soft_limit_l1_ratio=0.7,
        soft_limit_l2_ratio=0.85,
        keep_recent=2,
    )
    # LLM 不断调工具，制造长上下文
    responses = [
        f'```json\n{{"id": "c{i}", "name": "tool_{i}", "arguments": {{}}}}\n```' for i in range(10)
    ] + ["done"]
    llm = MockLLM(responses)
    executor = MockExecutor(return_value="result" * 10)
    compactions: list[tuple[int, int, int]] = []
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=executor,
        on_compaction=lambda lvl, b, a: compactions.append((lvl, b, a)),
        doom_loop_threshold=100,
        max_steps=15,
    )
    orch.run_turn("go")
    # 至少触发过一次压缩（第 2 级）
    assert len(compactions) >= 1
    assert any(c[0] == 2 for c in compactions)


def test_run_turn_persists_messages(qapp, store, context) -> None:  # noqa: ANN001
    """消息持久化到 sqlite3（重启可恢复）。"""
    llm = MockLLM(["hello"])
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=MockExecutor(),
    )
    orch.run_turn("hi")

    # sqlite3 中应有消息
    msgs_in_db = store.load_messages("s1")
    # 用户消息 + assistant 消息
    assert len(msgs_in_db) >= 2
    assert any(m.role == Role.USER and m.content == "hi" for m in msgs_in_db)
    assert any(m.role == Role.ASSISTANT and m.content == "hello" for m in msgs_in_db)


def test_run_turn_user_message_appended_first(qapp, store, context) -> None:  # noqa: ANN001
    """用户消息先入历史。"""
    llm = MockLLM(["reply"])
    orch = Orchestrator(
        llm_client=llm,
        context_manager=context,
        session_store=store,
        executor=MockExecutor(),
    )
    orch.run_turn("user_text")
    msgs = context.messages
    # 第一条应是用户消息
    assert msgs[0].role == Role.USER
    assert msgs[0].content == "user_text"
