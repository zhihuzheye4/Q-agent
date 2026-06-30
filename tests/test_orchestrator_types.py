"""编排层数据类型测试（v0.0.18）。"""

from datetime import datetime

from q_agent.orchestrator.types import (
    CompactionRecord,
    Message,
    Role,
    SessionData,
    TerminationReason,
    ToolCall,
    ToolResult,
    TurnResult,
    TurnState,
)


def test_role_str_enum_values() -> None:
    """Role str Enum 值正确，便于 sqlite3 存储。"""
    assert Role.SYSTEM == "system"
    assert Role.USER == "user"
    assert Role.ASSISTANT == "assistant"
    assert Role.TOOL == "tool"


def test_message_default_fields() -> None:
    """Message 默认字段正确。"""
    m = Message()
    assert m.id is None
    assert m.session_id is None
    assert m.role == Role.USER
    assert m.content == ""
    assert m.tool_calls == []
    assert m.tool_call_id is None
    assert m.is_synthetic is False
    assert m.is_compacted is False
    assert m.created_at is None


def test_tool_call_fields() -> None:
    """ToolCall 字段。"""
    tc = ToolCall(id="call_1", name="read_file", arguments={"path": "x.py"})
    assert tc.id == "call_1"
    assert tc.name == "read_file"
    assert tc.arguments == {"path": "x.py"}


def test_tool_result_defaults() -> None:
    """ToolResult 默认。"""
    r = ToolResult(call_id="call_1")
    assert r.call_id == "call_1"
    assert r.content == ""
    assert r.error is None


def test_tool_result_with_error() -> None:
    """ToolResult 错误场景。"""
    r = ToolResult(call_id="call_1", content="", error="权限拒绝")
    assert r.error == "权限拒绝"


def test_termination_reason_values() -> None:
    """TerminationReason str Enum。"""
    assert TerminationReason.LLM_STOPPED == "llm_stopped"
    assert TerminationReason.USER_CANCEL == "user_cancel"
    assert TerminationReason.MAX_STEPS_REACHED == "max_steps_reached"
    assert TerminationReason.CONSECUTIVE_ERRORS == "consecutive_errors"
    assert TerminationReason.CONTEXT_OVERFLOW == "context_overflow"
    assert TerminationReason.DOOM_LOOP == "doom_loop"
    assert TerminationReason.LLM_FAILED == "llm_failed"


def test_turn_state_defaults() -> None:
    """TurnState 默认。"""
    state = TurnState(messages=[], session_id="s1")
    assert state.session_id == "s1"
    assert state.steps == 0
    assert state.consecutive_errors == 0
    assert state.last_tool_signature is None
    assert state.doom_loop_count == 0
    assert state.terminated is False
    assert state.termination_reason is None


def test_turn_result_fields() -> None:
    """TurnResult 字段。"""
    result = TurnResult(
        messages=[],
        final_assistant_text="hello",
        termination_reason=TerminationReason.LLM_STOPPED,
        steps_executed=3,
        tool_calls_made=[],
    )
    assert result.final_assistant_text == "hello"
    assert result.termination_reason == TerminationReason.LLM_STOPPED
    assert result.steps_executed == 3


def test_session_data_defaults() -> None:
    """SessionData 默认。"""
    now = datetime.utcnow()
    s = SessionData(session_id="s1", created_at=now, last_active_at=now)
    assert s.message_count == 0
    assert s.is_archived is False
    assert s.summary_model is None


def test_compaction_record_fields() -> None:
    """CompactionRecord 字段。"""
    now = datetime.utcnow()
    r = CompactionRecord(
        compaction_id="c1",
        session_id="s1",
        triggered_at=now,
        level=3,
        tokens_before=1000,
        tokens_after=500,
        summary_model="qwen2.5:3b",
        identifier_preservation=True,
    )
    assert r.level == 3
    assert r.summary_model == "qwen2.5:3b"
    assert r.identifier_preservation is True
