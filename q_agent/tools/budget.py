"""输出预算：三档分级降级。

L1 占位：直接落盘 + 回喂占位符（超 2000 字符）
L2 截断：保留前 N + 后 N 字符，中间省略
L3 摘要：调小模型生成摘要（v0.0.20 接通 SummaryWorker，v0.0.19 占位返回截断版）
"""

from __future__ import annotations

from q_agent.tools.results import RESULTS_BUDGET, placeholder, spill


def apply_budget(
    text: str,
    tool_name: str,
    call_id: str,
    session_id: str,
    budget: int = RESULTS_BUDGET,
) -> str:
    """对工具输出应用预算降级。

    - text 长度 ≤ budget：原样返回
    - text 长度 > budget：落盘 + 返回占位符（L1 占位）
    """
    if len(text) <= budget:
        return text
    path = spill(
        session_id=session_id,
        call_id=call_id,
        tool_name=tool_name,
        output=text,
    )
    return placeholder(tool_name, call_id, path)


def truncate(text: str, head: int = 200, tail: int = 200) -> str:
    """L2 截断：保留前 head + 后 tail 字符，中间省略。"""
    if len(text) <= head + tail:
        return text
    return f"{text[:head]}\n...截断({len(text) - head - tail} 字符)...\n{text[-tail:]}"


def summarize_placeholder(text: str, limit: int = 100) -> str:
    """L3 摘要占位（v0.0.19 简版：返回前 limit 字符）。

    v0.0.20 接通 SummaryWorker 后改为真调小模型生成摘要。
    """
    return text[:limit] + ("..." if len(text) > limit else "")
