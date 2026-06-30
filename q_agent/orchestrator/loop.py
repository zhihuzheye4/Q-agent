"""Orchestrator 主循环（v0.0.18 2000+ 轮设计版）。

10 步主循环（修订版）：
1. 初始化：从 SessionStore 加载历史到 ContextManager
2. 终止判定：多 bool 检查（错误数 / doom / 步数 / 溢出）
3. LLM 调用：流式调 chat；失败 → 合成 assistant + consecutive_errors+1
4. assistant 入历史：ContextManager.append_message 同步写 sqlite3
5. LLM 自然停止：tool_calls 为空 → finalize
6. 工具执行：dispatcher.execute_tool_calls；>2000 字符落盘 + 占位回喂
7. tool_result 入历史：每条工具结果作为 role=TOOL 消息写入 sqlite3
8. doom_loop 检测：新签名 vs 上次签名 → 计数或清零
9. 压缩触发检查：70% → 第 2 级 / 85% → 第 3 级异步 / 100% → 第 4 级终止
10. 状态整体覆写 + UI 回调

异步摘要合流：第 3 级触发时启动 SummaryWorker，不阻塞主循环；
             summary_completed 信号触发时，下一轮迭代开头合并摘要到上下文。

借鉴 Claude Code：while-true 主循环 + 状态整体覆写 + 错误转 tool_result 回喂 + 合成 assistant。
借鉴 OpenCode：doom_loop 检测 + MAX_STEPS 软截止。
借鉴 OpenClaw：分块压缩 + 多块摘要合并 + 标识符保留指令 + 消息历史持久化 + 异步摘要避免阻塞。
"""

from __future__ import annotations

import contextlib
import threading
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from q_agent.orchestrator.context import ContextManager
from q_agent.orchestrator.dispatcher import (
    ParsedResponse,
    execute_tool_calls,
    parse_response,
    synthetic_assistant_message,
    tool_results_to_messages,
    tool_signature,
)
from q_agent.orchestrator.persistence import SessionStore
from q_agent.orchestrator.summary_worker import SummaryWorker
from q_agent.orchestrator.turn import Turn
from q_agent.orchestrator.types import (
    CompactionRecord,
    Message,
    Role,
    TerminationReason,
    ToolCall,
    TurnResult,
)


class Orchestrator:
    """编排层主循环协调器。

    用法：
        orch = Orchestrator(llm_client, context_manager, session_store, ...)
        result = orch.run_turn("用户输入文本")
        # result.final_assistant_text 是最终回复
    """

    def __init__(
        self,
        llm_client: Any,  # OllamaClient 或其他 LLMClient
        context_manager: ContextManager,
        session_store: SessionStore,
        executor: Any,  # q_agent.tools.executor 或 mock
        summary_worker: SummaryWorker | None = None,
        max_steps: int = 30,
        consecutive_error_threshold: int = 3,
        doom_loop_threshold: int = 3,
        on_step: Callable[[Any], None] | None = None,
        on_compaction: Callable[[int, int, int], None] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.context_manager = context_manager
        self.session_store = session_store
        self.executor = executor
        self.summary_worker = summary_worker
        self.max_steps = max_steps
        self.consecutive_error_threshold = consecutive_error_threshold
        self.doom_loop_threshold = doom_loop_threshold
        self.on_step = on_step
        self.on_compaction = on_compaction

        # 异步摘要合流锁 + 待合并摘要
        self._summary_lock = threading.Lock()
        self._pending_summary: str | None = None
        self._summary_in_progress = False

        # 连接 SummaryWorker 信号（如果传入了）
        if self.summary_worker is not None:
            self.summary_worker.summary_completed.connect(self._on_summary_completed)
            self.summary_worker.summary_failed.connect(self._on_summary_failed)

    # ---- 异步摘要回调 ----

    def _on_summary_completed(self, summary_text: str) -> None:
        """SummaryWorker 完成时存到待合并槽，下一轮迭代开头合并。"""
        with self._summary_lock:
            self._pending_summary = summary_text
            self._summary_in_progress = False

    def _on_summary_failed(self, error_msg: str) -> None:
        """摘要失败时降级到第 2 级文本截断（不重试 3 次抖动退避）。"""
        with self._summary_lock:
            self._summary_in_progress = False
        # 记录 CompactionRecord（level=3 失败）
        self._record_compaction(3, 0, 0, summary_failed=True, error_msg=error_msg)
        # 降级到第 2 级
        self.context_manager.apply_level2_truncate()
        if self.on_compaction is not None:
            self.on_compaction(3, 0, 0)

    def _record_compaction(
        self,
        level: int,
        tokens_before: int,
        tokens_after: int,
        summary_failed: bool = False,
        error_msg: str | None = None,
    ) -> None:
        """记录压缩事件到 sqlite3。"""
        record = CompactionRecord(
            compaction_id=str(uuid.uuid4()),
            session_id=self.context_manager.session_id,
            triggered_at=datetime.utcnow(),
            level=level,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            summary_model=self.summary_worker.summary_model if self.summary_worker else None,
            identifier_preservation=(level == 3),
        )
        with contextlib.suppress(Exception):
            # 记录失败不影响主流程
            self.session_store.record_compaction(record)

    # ---- 主循环 ----

    def run_turn(self, user_text: str) -> TurnResult:
        """执行一轮对话。

        1. 追加用户消息
        2. while-true 主循环：LLM 调用 → 解析 → 工具执行 → 压缩检查
        3. 返回 TurnResult
        """
        session_id = self.context_manager.session_id
        turn = Turn(
            session_id=session_id,
            initial_messages=self.context_manager.messages,
            max_steps=self.max_steps,
            consecutive_error_threshold=self.consecutive_error_threshold,
            doom_loop_threshold=self.doom_loop_threshold,
        )

        # 异步摘要合流（如果有 pending_summary，先合并）
        self._maybe_merge_pending_summary()

        # 第 1 步：追加用户消息
        user_msg = Message(
            session_id=session_id,
            role=Role.USER,
            content=user_text,
        )
        self.context_manager.append_message(user_msg)

        all_tool_calls: list[ToolCall] = []
        final_assistant_text = ""

        # 主循环
        while True:
            # 第 2 步：终止判定
            term = turn.check_termination()
            if term is not None:
                turn.mark_terminated(term)
                break

            # 异步摘要合流（如果有 pending_summary）
            self._maybe_merge_pending_summary()

            # 第 3 步：LLM 调用
            llm_messages = self.context_manager.to_llm_messages()
            try:
                raw_text = self._call_llm(llm_messages)
                turn.reset_errors()
            except Exception as e:  # noqa: BLE001 - LLM 调用顶层兜底
                # 失败 → 合成 assistant 消息 + consecutive_errors+1
                turn.record_error()
                synth = synthetic_assistant_message(f"[LLM 调用失败] {type(e).__name__}: {e}")
                self.context_manager.append_message(
                    Message(
                        session_id=session_id,
                        role=Role.ASSISTANT,
                        content=synth.content,
                        is_synthetic=True,
                    )
                )
                if self.on_step is not None:
                    self.on_step(turn.state)
                # 检查是否连续错误超阈值
                term = turn.check_termination(llm_failed=False)
                if term is not None:
                    turn.mark_terminated(term)
                    break
                turn.increment_step()
                continue

            # 第 4 步：解析 + assistant 入历史
            parsed: ParsedResponse = parse_response(raw_text)
            assistant_msg = Message(
                session_id=session_id,
                role=Role.ASSISTANT,
                content=parsed.assistant_text,
                tool_calls=parsed.tool_calls,
            )
            self.context_manager.append_message(assistant_msg)

            # 第 5 步：LLM 自然停止（无 tool_calls）→ finalize
            if not parsed.tool_calls:
                final_assistant_text = parsed.assistant_text
                turn.mark_terminated(TerminationReason.LLM_STOPPED)
                if self.on_step is not None:
                    self.on_step(turn.state)
                break

            # 第 6 步：工具执行
            results = execute_tool_calls(parsed.tool_calls, self.executor)
            all_tool_calls.extend(parsed.tool_calls)

            # 第 7 步：tool_result 入历史（每条作为 role=TOOL 消息）
            tool_msgs = tool_results_to_messages(results)
            for m in tool_msgs:
                m.session_id = session_id
                self.context_manager.append_message(m)

            # 第 8 步：doom_loop 检测（用第一个工具调用签名）
            sig = tool_signature(parsed.tool_calls[0])
            turn.update_tool_signature(sig)

            # 第 9 步：压缩触发检查
            self._check_and_compact(turn)

            # 第 10 步：状态整体覆写 + UI 回调
            turn.increment_step()
            if self.on_step is not None:
                self.on_step(turn.state)

        return TurnResult(
            messages=self.context_manager.messages,
            final_assistant_text=final_assistant_text,
            termination_reason=turn.state.termination_reason or TerminationReason.LLM_STOPPED,
            steps_executed=turn.state.steps,
            tool_calls_made=all_tool_calls,
        )

    # ---- 内部辅助 ----

    def _call_llm(self, messages: list[dict[str, object]]) -> str:
        """调 LLM 客户端，返回完整文本。

        优先用 chat_stream 流式拼接（如果有），否则用 chat。
        """
        chat_stream = getattr(self.llm_client, "chat_stream", None)
        if chat_stream is not None:
            # chat_stream 接收 list[dict]，但 dict 值可能含非 str，转一下
            clean = [
                {"role": str(m["role"]), "content": str(m.get("content", ""))} for m in messages
            ]
            chunks: list[str] = list(chat_stream(clean))
            return "".join(chunks)
        chat = getattr(self.llm_client, "chat", None)
        if chat is None:
            raise RuntimeError("LLM 客户端未实现 chat 或 chat_stream 方法")
        result: str = chat(messages)
        return result

    def _maybe_merge_pending_summary(self) -> None:
        """如果有 pending_summary，合并到上下文。"""
        with self._summary_lock:
            summary = self._pending_summary
            self._pending_summary = None
        if summary:
            self.context_manager.merge_pending_summary(summary)

    def _check_and_compact(self, turn: Turn) -> None:
        """检查压缩触发 + 执行对应级别。

        70% → 第 2 级旧消息截断（同步）
        85% → 第 3 级异步真摘要（启动 SummaryWorker，不阻塞）
        100% → 第 4 级硬溢出终止
        """
        trigger = self.context_manager.check_compaction()
        if not trigger.triggered:
            return

        if trigger.level == 2:
            # 第 2 级：同步截断
            result = self.context_manager.apply_level2_truncate()
            self._record_compaction(2, result.tokens_before, result.tokens_after)
            if self.on_compaction is not None:
                self.on_compaction(2, result.tokens_before, result.tokens_after)

        elif trigger.level == 3:
            # 第 3 级：异步真摘要（启动 SummaryWorker）
            if self.summary_worker is None:
                # 无 SummaryWorker 配置 → 降级到第 2 级
                result = self.context_manager.apply_level2_truncate()
                self._record_compaction(2, result.tokens_before, result.tokens_after)
                if self.on_compaction is not None:
                    self.on_compaction(2, result.tokens_before, result.tokens_after)
                return

            with self._summary_lock:
                if self._summary_in_progress:
                    return  # 已在跑，不重复启动
                self._summary_in_progress = True

            chunks = self.context_manager.prepare_summary_chunks()
            if not chunks:
                with self._summary_lock:
                    self._summary_in_progress = False
                return

            # 记录压缩事件（before；after 在摘要完成后由 _on_summary_completed 触发的合流记录）
            self._record_compaction(
                3,
                tokens_before=trigger.tokens_before,
                tokens_after=trigger.tokens_before,  # 先记 before，合流时再记 after
            )
            if self.on_compaction is not None:
                self.on_compaction(3, trigger.tokens_before, trigger.tokens_before)

            # 启动 SummaryWorker（新实例，避免 QThread 复用问题）
            # v0.0.18 骨架：用注入的 summary_worker 实例（骨架版）
            self.summary_worker.set_chunks(chunks)
            self.summary_worker.start()

        elif trigger.level == 4:
            # 第 4 级：硬溢出终止
            self._record_compaction(4, trigger.tokens_before, trigger.tokens_before)
            if self.on_compaction is not None:
                self.on_compaction(4, trigger.tokens_before, trigger.tokens_before)
            turn.mark_terminated(TerminationReason.CONTEXT_OVERFLOW)
