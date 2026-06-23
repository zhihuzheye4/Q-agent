"""Turn 状态机测试（v0.0.18）。"""

from q_agent.orchestrator.turn import Turn
from q_agent.orchestrator.types import Message, TerminationReason


def test_turn_init_defaults() -> None:
    """Turn 初始化默认状态。"""
    turn = Turn(session_id="s1")
    assert turn.session_id == "s1"
    assert turn.state.messages == []
    assert turn.state.steps == 0
    assert turn.state.consecutive_errors == 0


def test_turn_increment_step() -> None:
    """步数递增。"""
    turn = Turn(session_id="s1")
    turn.increment_step()
    turn.increment_step()
    assert turn.state.steps == 2


def test_turn_record_and_reset_errors() -> None:
    """记录错误 + 成功后清零。"""
    turn = Turn(session_id="s1")
    turn.record_error()
    turn.record_error()
    assert turn.state.consecutive_errors == 2
    turn.reset_errors()
    assert turn.state.consecutive_errors == 0


def test_turn_reset_errors_idempotent() -> None:
    """错误已为 0 时 reset_errors 不触发覆写。"""
    turn = Turn(session_id="s1")
    initial_state = turn.state
    turn.reset_errors()
    assert turn.state is initial_state  # 同一对象，未覆写


def test_turn_update_tool_signature_new() -> None:
    """新签名 → 清零 + 更新签名。"""
    turn = Turn(session_id="s1")
    turn.update_tool_signature(("read_file", "abc12345"))
    assert turn.state.last_tool_signature == ("read_file", "abc12345")
    assert turn.state.doom_loop_count == 0


def test_turn_update_tool_signature_repeat() -> None:
    """重复签名 → doom_loop_count +1。"""
    turn = Turn(session_id="s1")
    sig = ("read_file", "abc12345")
    turn.update_tool_signature(sig)
    turn.update_tool_signature(sig)
    assert turn.state.doom_loop_count == 1
    turn.update_tool_signature(sig)
    assert turn.state.doom_loop_count == 2


def test_turn_check_termination_user_cancel_priority() -> None:
    """用户取消优先级最高。"""
    turn = Turn(session_id="s1")
    term = turn.check_termination(user_cancel=True)
    assert term == TerminationReason.USER_CANCEL


def test_turn_check_termination_context_overflow() -> None:
    """硬溢出终止。"""
    turn = Turn(session_id="s1")
    term = turn.check_termination(context_overflow=True)
    assert term == TerminationReason.CONTEXT_OVERFLOW


def test_turn_check_termination_llm_stopped() -> None:
    """LLM 自然停止。"""
    turn = Turn(session_id="s1")
    term = turn.check_termination(llm_stopped=True)
    assert term == TerminationReason.LLM_STOPPED


def test_turn_check_termination_doom_loop() -> None:
    """doom_loop 触发：3 次重复相同签名（共 4 次循环，首次设置签名 + 3 次重复）。"""
    turn = Turn(session_id="s1", doom_loop_threshold=3)
    sig = ("read_file", "abc12345")
    for _ in range(4):
        turn.update_tool_signature(sig)
    term = turn.check_termination()
    assert term == TerminationReason.DOOM_LOOP


def test_turn_check_termination_consecutive_errors() -> None:
    """连续错误触发。"""
    turn = Turn(session_id="s1", consecutive_error_threshold=3)
    turn.record_error()
    turn.record_error()
    turn.record_error()
    term = turn.check_termination()
    assert term == TerminationReason.CONSECUTIVE_ERRORS


def test_turn_check_termination_max_steps() -> None:
    """最大步数软截止。"""
    turn = Turn(session_id="s1", max_steps=5)
    for _ in range(5):
        turn.increment_step()
    term = turn.check_termination()
    assert term == TerminationReason.MAX_STEPS_REACHED


def test_turn_check_termination_none() -> None:
    """无终止条件返回 None。"""
    turn = Turn(session_id="s1")
    term = turn.check_termination()
    assert term is None


def test_turn_mark_terminated() -> None:
    """标记终止。"""
    turn = Turn(session_id="s1")
    turn.mark_terminated(TerminationReason.LLM_STOPPED)
    assert turn.state.terminated is True
    assert turn.state.termination_reason == TerminationReason.LLM_STOPPED


def test_turn_with_initial_messages() -> None:
    """带初始消息。"""
    msgs = [Message(content="hi")]
    turn = Turn(session_id="s1", initial_messages=msgs)
    assert len(turn.state.messages) == 1
    # 修改不影响原 msgs
    turn.state.messages.append(Message(content="bye"))
    assert len(msgs) == 1  # 原列表未变
