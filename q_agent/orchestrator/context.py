"""上下文管理器（v0.0.18 2000+ 轮设计版）。

4 级压缩策略：
1. 工具结果预算：>2000 字符的工具结果落盘 + 占位回喂
2. 旧消息截断：N 轮前消息每条取前 200 字符，保留工具调用元数据
3. 异步真摘要：独立小模型后台摘要 + 标识符保留指令
4. 硬溢出终止：压缩后仍超 max_tokens 则终止

标识符保留指令：第 3 级摘要时附加给 SummaryWorker 的系统提示，
强制保留文件路径 / 任务 ID / 工具调用 ID / URL / 哈希 / 模型名 / 函数名 / 错误码。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from q_agent.orchestrator.types import (
    Message,
    Role,
)

# ---- 标识符保留指令模板（第 3 级异步真摘要用）----

SUMMARY_SYSTEM_PROMPT = """\
你是 Q-agent 的上下文压缩助手。请将以下对话历史压缩成简洁摘要，保留主线信息。

**必须保留的标识符（不可压缩丢失）**：
- 文件路径（如 G:\\agent\\memory\\xxx.md、q_agent/orchestrator/loop.py）
- 任务 ID / 工具调用 ID（如 call_abc123）
- URL（如 https://github.com/...）
- 哈希值（如 git commit 6e76d6c）
- IP 地址（如 192.168.1.1）
- 模型名 / 版本号（如 qwen2.5:3b、v0.0.18）
- 函数名 / 类名 / 方法名（如 Orchestrator.run_turn）
- 错误码（如 413、503）

**保留要点**：
- 用户的核心请求
- AI 的关键决策与结论
- 工具调用及其结果要点
- 未完成的任务与下一步

**输出格式**：
[上下文摘要] <摘要正文>

待压缩对话历史：
<chunks>
"""


@dataclass
class CompactionTrigger:
    """压缩触发记录（ContextManager 内部用，不入库）。"""

    level: int
    triggered: bool
    tokens_before: int
    tokens_after: int


@dataclass
class ContextConfig:
    """ContextManager 配置。"""

    max_tokens: int = 8000
    soft_limit_l1_ratio: float = 0.7  # 70% 触发第 2 级
    soft_limit_l2_ratio: float = 0.85  # 85% 触发第 3 级
    hard_limit_ratio: float = 1.0  # 100% 触发第 4 级
    keep_recent: int = 20  # 第 2 级保留最近 N 条
    old_message_truncate_chars: int = 200  # 第 2 级旧消息截断字符数
    tool_result_budget: int = 2000  # 第 1 级工具结果字符上限
    compaction_chunk_tokens: int = 2000  # 第 3 级分块大小


class ContextManager:
    """上下文管理器：消息历史 + token 计数 + 4 级压缩 + 标识符保留。

    线程安全：messages 列表加 threading.Lock 保护（主循环 + SummaryWorker 可能同时访问）。
    持久化：每条消息 append 时同步写入 SessionStore。
    异步摘要：第 3 级触发时启动 SummaryWorker，不阻塞主循环；
             summary_completed 信号触发时，下一轮迭代开头合并摘要。
    """

    def __init__(
        self,
        session_id: str,
        session_store: Any,  # SessionStore，循环引用用 Any 避免导入循环
        config: ContextConfig | None = None,
        tool_results_dir: Path | None = None,
    ) -> None:
        self.session_id = session_id
        self.session_store = session_store
        self.config = config or ContextConfig()
        self.tool_results_dir = tool_results_dir or Path("q_agent/data/tool_results")
        self.tool_results_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._messages: list[Message] = []
        self._pending_summary: str | None = None

    # ---- 消息历史管理 ----

    @property
    def messages(self) -> list[Message]:
        with self._lock:
            return list(self._messages)

    def load_history(self, limit: int | None = None) -> None:
        """从 SessionStore 加载历史消息到内存。limit 不为空时只加载最近 N 条。"""
        with self._lock:
            self._messages = self.session_store.load_messages(self.session_id, limit=limit)

    def append_message(self, msg: Message) -> Message:
        """追加消息到内存 + sqlite3。返回持久化后的 msg（含 id/created_at）。"""
        # 第 1 级压缩：工具结果 > 2000 字符落盘 + 占位替换
        if msg.role == Role.TOOL and len(msg.content) > self.config.tool_result_budget:
            msg = self._compact_tool_result(msg)

        persisted: Message = self.session_store.append_message(msg)
        with self._lock:
            self._messages.append(persisted)
        return persisted

    def _compact_tool_result(self, msg: Message) -> Message:
        """第 1 级压缩：工具结果 > 预算字符数 → 落盘 + 占位替换。

        原文写 q_agent/data/tool_results/<tool_call_id>.txt
        消息 content 替换为 "[内容已清空，详见文件 X]" 占位
        """
        from dataclasses import replace

        call_id = msg.tool_call_id or "unknown"
        safe_id = "".join(c if c.isalnum() else "_" for c in call_id)
        out_file = self.tool_results_dir / f"{safe_id}.txt"
        try:
            out_file.write_text(msg.content, encoding="utf-8")
            placeholder = (
                f"[内容已清空（>{self.config.tool_result_budget}字符），详见文件 {out_file}]"
            )
            return replace(msg, content=placeholder)
        except OSError:
            # 落盘失败则保留原文（降级，不丢失数据）
            return msg

    # ---- token 计数（粗估：字符数 / 4）----

    def estimate_tokens(self, messages: list[Message] | None = None) -> int:
        """粗估 token 数。字符数 / 4 是常见启发式估算。"""
        msgs = messages if messages is not None else self.messages
        total_chars = 0
        for m in msgs:
            total_chars += len(m.content)
            for tc in m.tool_calls:
                total_chars += len(tc.name) + len(str(tc.arguments))
        return total_chars // 4

    # ---- 4 级压缩触发检查 ----

    def check_compaction(self) -> CompactionTrigger:
        """检查是否触发压缩，返回触发记录（不入库，由 loop.py 决定是否启动 SummaryWorker）。"""
        tokens = self.estimate_tokens()
        max_t = self.config.max_tokens

        if tokens >= int(max_t * self.config.hard_limit_ratio):
            return CompactionTrigger(
                level=4, triggered=True, tokens_before=tokens, tokens_after=tokens
            )
        if tokens >= int(max_t * self.config.soft_limit_l2_ratio):
            return CompactionTrigger(
                level=3, triggered=True, tokens_before=tokens, tokens_after=tokens
            )
        if tokens >= int(max_t * self.config.soft_limit_l1_ratio):
            return CompactionTrigger(
                level=2, triggered=True, tokens_before=tokens, tokens_after=tokens
            )
        return CompactionTrigger(
            level=0, triggered=False, tokens_before=tokens, tokens_after=tokens
        )

    # ---- 第 2 级：旧消息截断（同步、毫秒级）----

    def apply_level2_truncate(self) -> CompactionTrigger:
        """第 2 级压缩：N 轮前的消息每条取前 200 字符，保留工具调用元数据。

        - 保留最近 keep_recent 条不动
        - 较早的消息 content 截断到前 old_message_truncate_chars 字符
        - tool_calls / tool_call_id 等元数据完全不动（防标识符丢失）
        - 已截断的消息在 sqlite3 更新 is_compacted=1 + 新 content
        """
        with self._lock:
            msgs = self._messages
            keep = self.config.keep_recent
            if len(msgs) <= keep:
                # 传 msgs 避免嵌套加锁：无参 estimate_tokens 会读 self.messages 再加锁
                tokens = self.estimate_tokens(msgs)
                return CompactionTrigger(
                    level=2,
                    triggered=False,
                    tokens_before=tokens,
                    tokens_after=tokens,
                )

            # 从第 keep 倒数往前截断（保留最近 keep 条不动）
            cutoff_idx = len(msgs) - keep
            for i in range(cutoff_idx):
                m = msgs[i]
                if m.is_compacted:
                    continue  # 已压缩过不再二次截断
                if len(m.content) <= self.config.old_message_truncate_chars:
                    continue
                from dataclasses import replace

                truncated = m.content[: self.config.old_message_truncate_chars] + "...[已截断]"
                new_msg = replace(m, content=truncated, is_compacted=True)
                msgs[i] = new_msg
                if m.id is not None:
                    self.session_store.update_message_content(m.id, truncated, is_compacted=True)

            after_tokens = self.estimate_tokens(msgs)
            return CompactionTrigger(
                level=2,
                triggered=True,
                tokens_before=after_tokens,  # 简化：用 after 作 before 记录（精确 before 已记录过）
                tokens_after=after_tokens,
            )

    # ---- 第 3 级：异步真摘要（启动 SummaryWorker，不阻塞）----

    def prepare_summary_chunks(self) -> list[str]:
        """第 3 级压缩准备：把较早的消息切成 ~2000 token 的块，供 SummaryWorker 摘要。

        保留最近 keep_recent 条不动（与第 2 级一致的保留策略）。
        """
        with self._lock:
            msgs = self._messages
            keep = self.config.keep_recent
            if len(msgs) <= keep:
                return []
            cutoff_idx = len(msgs) - keep
            old_msgs = msgs[:cutoff_idx]

        # 每块目标 ~2000 token ≈ 8000 字符
        chunk_char_limit = self.config.compaction_chunk_tokens * 4
        chunks: list[str] = []
        current: list[str] = []
        current_chars = 0
        for m in old_msgs:
            text = f"[{m.role.value}] {m.content}"
            if current_chars + len(text) > chunk_char_limit and current:
                chunks.append("\n".join(current))
                current = []
                current_chars = 0
            current.append(text)
            current_chars += len(text)
        if current:
            chunks.append("\n".join(current))
        return chunks

    def merge_pending_summary(self, summary_text: str) -> None:
        """合并异步摘要到上下文（SummaryWorker.summary_completed 触发时调用）。

        把被摘要的旧消息替换为一条 role=SYSTEM 的摘要消息。
        """
        if not summary_text:
            return
        with self._lock:
            msgs = self._messages
            keep = self.config.keep_recent
            if len(msgs) <= keep:
                return
            cutoff_idx = len(msgs) - keep
            old_msgs = msgs[:cutoff_idx]
            # 删除旧消息对应的 sqlite3 记录（标记 is_compacted，不真删）
            for m in old_msgs:
                if m.id is not None and not m.is_compacted:
                    self.session_store.update_message_content(
                        m.id, "[已被异步摘要替换]", is_compacted=True
                    )
            # 用摘要消息替换旧消息块
            summary_msg = Message(
                session_id=self.session_id,
                role=Role.SYSTEM,
                content=f"[上下文摘要] {summary_text}",
                is_synthetic=True,
                is_compacted=True,
            )
            persisted = self.session_store.append_message(summary_msg)
            self._messages = [persisted] + msgs[cutoff_idx:]

    # ---- 第 4 级：硬溢出终止（loop.py 决策，ContextManager 仅记录）----

    def is_hard_overflow(self) -> bool:
        """是否触发硬溢出（第 4 级）。"""
        return self.estimate_tokens() >= int(self.config.max_tokens * self.config.hard_limit_ratio)

    # ---- 给 LLM 调用：消息转 dict 格式 ----

    def to_llm_messages(self) -> list[dict[str, object]]:
        """转 Ollama 格式 [{"role":..., "content":...}, ...]。

        tool_calls 和 tool_call_id 不直接送 LLM（Ollama chat 格式简化），
        v0.0.19 接真工具调用时按 Ollama tools API 扩展。
        """
        msgs = self.messages
        result: list[dict[str, object]] = []
        for m in msgs:
            result.append({"role": m.role.value, "content": m.content})
        return result
