"""审计日志：包装 SessionStore.insert_audit，提供工具调用审计写入。

v0.0.19 简版：仅写不读（编排层未接通）。
v0.0.20+ 候选：查询接口供 tool_history_page 用。
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from q_agent.orchestrator.persistence import SessionStore


def args_hash(tool_name: str, args: tuple[object, ...], kwargs: dict[str, object]) -> str:
    """同会话缓存键：tool_name + 参数指纹（sha256 hex）。"""
    payload = json.dumps(
        {"t": tool_name, "a": list(args), "k": kwargs},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def summarize(text: str | None, limit: int = 200) -> str:
    """生成摘要（前 limit 字符），不记完整明文。"""
    if not text:
        return ""
    return text[:limit]


def write_audit(
    store: SessionStore,
    call_id: str,
    tool_name: str,
    permission_level: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
    status: str,
    started_at: str,
    approval_mode: str | None = None,
    error_kind: str | None = None,
    input_text: str | None = None,
    output_text: str | None = None,
) -> None:
    """写入一条审计记录（含 args_hash + 摘要）。"""
    store.insert_audit(
        call_id=call_id,
        tool_name=tool_name,
        permission_level=permission_level,
        args_hash=args_hash(tool_name, args, kwargs),
        status=status,
        started_at=started_at,
        approval_mode=approval_mode,
        error_kind=error_kind,
        input_summary=summarize(input_text),
        output_summary=summarize(output_text),
    )
