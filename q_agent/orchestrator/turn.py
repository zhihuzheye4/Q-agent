"""单轮 turn 状态机抽象。

每轮（run_turn）从用户消息开始，到 LLM 自然停止 / 工具循环 / 终止条件触发结束。
TurnState 在每次循环迭代结束整体覆写，防跨迭代状态泄漏。
"""

from __future__ import annotations

from typing import Any

from q_agent.orchestrator.types import Message, TerminationReason, TurnState


class Turn:
    """单轮 turn 抽象，封装状态机操作。

    设计要点：
    - state 在每步操作后整体覆写（TurnState(**new_fields)），不用原地修改
    - 终止判定集中在一个方法（check_termination），返回终止原因或 None
    - doom_loop 检测：当前工具调用签名与上次相同则计数+1，超阈值返回 DOOM_LOOP
    """

    def __init__(
        self,
        session_id: str,
        initial_messages: list[Message] | None = None,
        max_steps: int = 30,
        consecutive_error_threshold: int = 3,
        doom_loop_threshold: int = 3,
    ) -> None:
        self.session_id = session_id
        self.max_steps = max_steps
        self.consecutive_error_threshold = consecutive_error_threshold
        self.doom_loop_threshold = doom_loop_threshold
        self._state = TurnState(
            messages=list(initial_messages) if initial_messages else [],
            session_id=session_id,
        )

    @property
    def state(self) -> TurnState:
        return self._state

    def replace(self, **fields: Any) -> TurnState:
        """整体覆写状态。dataclasses.replace 的语义封装。"""
        from dataclasses import replace

        self._state = replace(self._state, **fields)
        return self._state

    def increment_step(self) -> TurnState:
        """步数 +1。"""
        return self.replace(steps=self._state.steps + 1)

    def record_error(self) -> TurnState:
        """记录一次错误，consecutive_errors +1。"""
        return self.replace(consecutive_errors=self._state.consecutive_errors + 1)

    def reset_errors(self) -> TurnState:
        """错误清零（成功一次后调用）。"""
        if self._state.consecutive_errors == 0:
            return self._state
        return self.replace(consecutive_errors=0)

    def update_tool_signature(self, signature: tuple[str, str]) -> TurnState:
        """更新上次工具调用签名 + doom_loop 计数。

        新签名 vs 上次签名相同 → doom_loop_count +1
        不同 → doom_loop_count 清零，更新签名
        """
        if self._state.last_tool_signature == signature:
            return self.replace(doom_loop_count=self._state.doom_loop_count + 1)
        return self.replace(
            last_tool_signature=signature,
            doom_loop_count=0,
        )

    def check_termination(
        self,
        context_overflow: bool = False,
        llm_stopped: bool = False,
        user_cancel: bool = False,
        llm_failed: bool = False,
    ) -> TerminationReason | None:
        """检查终止条件，返回终止原因或 None（继续循环）。

        优先级（从前到后）：
        1. user_cancel（用户主动取消，优先级最高）
        2. context_overflow（第 4 级硬溢出）
        3. llm_failed（LLM 调用本身失败）
        4. llm_stopped（LLM 自然停止，无 tool_calls）
        5. doom_loop（重复工具调用超阈值）
        6. consecutive_errors（连续错误超阈值）
        7. max_steps（达到最大步数软截止）
        """
        if user_cancel:
            return TerminationReason.USER_CANCEL
        if context_overflow:
            return TerminationReason.CONTEXT_OVERFLOW
        if llm_failed:
            return TerminationReason.LLM_FAILED
        if llm_stopped:
            return TerminationReason.LLM_STOPPED
        if self._state.doom_loop_count >= self.doom_loop_threshold:
            return TerminationReason.DOOM_LOOP
        if self._state.consecutive_errors >= self.consecutive_error_threshold:
            return TerminationReason.CONSECUTIVE_ERRORS
        if self._state.steps >= self.max_steps:
            return TerminationReason.MAX_STEPS_REACHED
        return None

    def mark_terminated(self, reason: TerminationReason) -> TurnState:
        """标记终止。"""
        return self.replace(terminated=True, termination_reason=reason)
