"""LLM 输出解析 + 工具调用调度（v0.0.18 骨架）。

设计要点：
- parse_response 把 LLM 文本输出解析为 (assistant_text, tool_calls)
  v0.0.18 骨架：解析 JSON 格式的 tool_calls（LLM 输出含 ```json ... ``` 块时提取）
  v0.0.19 实化：按 Ollama tools API 真解析 native tool_calls 字段
- execute_tool_calls 调 q_agent.tools.executor + safety 执行工具
- 错误转为 ToolResult.error，回喂给 LLM 让它知道工具失败

借鉴 Claude Code：错误转 tool_result 回喂 + 合成 assistant 消息。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from q_agent.orchestrator.types import Message, Role, ToolCall, ToolResult

# ---- LLM 输出解析 ----

# 匹配 ```json ... ``` 或 ```tool_calls ... ``` 代码块
_TOOL_CALLS_BLOCK_RE = re.compile(
    r"```(?:json|tool_calls)?\s*\n(.*?)\n```",
    re.DOTALL,
)


@dataclass
class ParsedResponse:
    """LLM 输出解析结果。"""

    assistant_text: str
    tool_calls: list[ToolCall]


def parse_response(raw_text: str) -> ParsedResponse:
    """解析 LLM 文本输出为 (assistant_text, tool_calls)。

    v0.0.18 骨架策略：
    - 在 raw_text 中找 ```json ... ``` 代码块
    - 块内容解析为 tool_calls 列表（JSON 数组，每项含 id/name/arguments）
    - 块外的文本作为 assistant_text
    - 找不到合法 JSON 块 → assistant_text = raw_text，tool_calls = []

    v0.0.19 实化：按 Ollama /api/chat 的 native tools API 解析
    (响应含 message.tool_calls 字段，每项 {id, function: {name, arguments}})。
    """
    tool_calls: list[ToolCall] = []
    text_parts: list[str] = []

    last_end = 0
    for m in _TOOL_CALLS_BLOCK_RE.finditer(raw_text):
        text_parts.append(raw_text[last_end : m.start()])
        block_body = m.group(1).strip()
        parsed = _try_parse_tool_calls(block_body)
        if parsed is not None:
            tool_calls.extend(parsed)
        else:
            # JSON 解析失败，把整个块作为文本保留
            text_parts.append(raw_text[m.start() : m.end()])
        last_end = m.end()
    text_parts.append(raw_text[last_end:])

    assistant_text = "".join(text_parts).strip()
    return ParsedResponse(assistant_text=assistant_text, tool_calls=tool_calls)


def _try_parse_tool_calls(block_body: str) -> list[ToolCall] | None:
    """尝试把 JSON 块解析为 ToolCall 列表。失败返回 None。"""
    try:
        data = json.loads(block_body)
    except json.JSONDecodeError:
        return None

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return None

    result: list[ToolCall] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        call_id = item.get("id") or f"call_{hashlib.md5(block_body.encode()).hexdigest()[:8]}"
        func = item.get("function")
        if isinstance(func, dict):
            name = item.get("name") or func.get("name")
            args = item.get("arguments") or func.get("arguments")
        else:
            name = item.get("name")
            args = item.get("arguments")
        if not name or not isinstance(name, str):
            continue
        if not isinstance(args, dict):
            args = {}
        result.append(ToolCall(id=str(call_id), name=name, arguments=args))
    return result if result else None


# ---- 工具调用调度 ----


def execute_tool_calls(
    tool_calls: list[ToolCall],
    executor: Any,  # q_agent.tools.executor 模块或 stub
) -> list[ToolResult]:
    """执行工具调用列表，返回结果列表。

    executor 需要暴露 execute_tool(name, **kwargs) -> str 接口。
    v0.0.18 骨架：executor 可以是 mock，v0.0.19 接真 q_agent.tools.executor。
    """
    results: list[ToolResult] = []
    for call in tool_calls:
        result = _execute_one(call, executor)
        results.append(result)
    return results


def _execute_one(call: ToolCall, executor: Any) -> ToolResult:
    """执行单个工具调用。失败时返回 ToolResult.error，不抛异常。"""
    try:
        # executor.execute_tool(name, **kwargs) -> str
        fn = getattr(executor, "execute_tool", None)
        if fn is None:
            return ToolResult(
                call_id=call.id,
                content="",
                error="executor 未实现 execute_tool 方法",
            )
        kwargs = {k: v for k, v in call.arguments.items() if isinstance(k, str)}
        raw = fn(call.name, **kwargs) if kwargs else fn(call.name)
        content = raw if isinstance(raw, str) else str(raw)
        return ToolResult(call_id=call.id, content=content)
    except PermissionError as e:
        # safety.check_command / check_path 抛的权限错误
        return ToolResult(call_id=call.id, content="", error=f"权限拒绝: {e}")
    except Exception as e:  # noqa: BLE001 - 工具执行顶层兜底
        return ToolResult(call_id=call.id, content="", error=f"{type(e).__name__}: {e}")


# ---- 工具结果回喂消息 ----


def tool_results_to_messages(results: list[ToolResult]) -> list[Message]:
    """把 ToolResult 列表转为 role=TOOL 消息列表，回喂给 LLM。"""
    return [
        Message(
            role=Role.TOOL,
            content=r.content if not r.error else f"[工具执行失败] {r.error}",
            tool_call_id=r.call_id,
        )
        for r in results
    ]


def synthetic_assistant_message(text: str, tool_calls: list[ToolCall] | None = None) -> Message:
    """合成 assistant 消息（错误时产出，非 LLM 真实输出）。

    借鉴 Claude Code：错误转 tool_result 回喂 + 合成 assistant 消息。
    """
    return Message(
        role=Role.ASSISTANT,
        content=text,
        tool_calls=tool_calls or [],
        is_synthetic=True,
    )


# ---- doom_loop 检测辅助 ----


def tool_signature(call: ToolCall) -> tuple[str, str]:
    """工具调用签名 (name, args_hash)，用于 doom_loop 检测。"""
    args_str = json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)
    args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
    return (call.name, args_hash)
