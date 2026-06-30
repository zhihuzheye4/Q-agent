"""审批与权限：三级权限判定 + 会话内缓存 + 永不沙箱风险知情。

三级权限：
- read_only：自动通过，不弹窗
- write：首次弹窗，"会话内允许"后相同 args_hash 不再弹（会话内缓存）
- destructive：每次必弹，永不缓存

永不沙箱风险知情：首次使用 destructive 工具前一次性弹窗，
ack 后写入 ~/.q-agent/settings.json，后续启动不再显示。

args_hash 复用 q_agent.tools.audit.args_hash，不重复实现。
"""

from __future__ import annotations

import json
from pathlib import Path

from q_agent.tools.audit import args_hash
from q_agent.tools.spec import PermissionLevel

SETTINGS_FILE = Path.home() / ".q-agent" / "settings.json"

ApprovalMode = str  # "auto" / "once" / "always" / "deny"

# 会话内 write 级缓存：{args_hash: True}
# destructive 不入缓存，每次必弹
_WRITE_CACHE: set[str] = set()
# deny 缓存：用户已拒绝的 args_hash，本会话内不再允许
_DENY_CACHE: set[str] = set()


def reset_session_cache() -> None:
    """重置会话内缓存（测试用 + 新会话开启时调）。"""
    _WRITE_CACHE.clear()
    _DENY_CACHE.clear()


def check_permission(
    tool_name: str,
    permission_level: PermissionLevel,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> ApprovalMode:
    """根据权限级 + 缓存判定是否需要弹窗，返回审批模式。

    - read_only → "auto"（直接通过）
    - write → 命中 deny 缓存 → "deny"
    - write → 命中 allow 缓存 → "auto"
    - write → 否则返回 "pending"（需弹窗，由 UI 决定 once/always/deny）
    - destructive → "pending"（每次必弹）
    """
    if permission_level == "read_only":
        return "auto"

    key = args_hash(tool_name, args, kwargs)

    if key in _DENY_CACHE:
        return "deny"

    if permission_level == "write" and key in _WRITE_CACHE:
        return "auto"

    return "pending"


def record_approval(
    tool_name: str,
    permission_level: PermissionLevel,
    args: tuple[object, ...],
    kwargs: dict[str, object],
    mode: ApprovalMode,
) -> None:
    """记录 UI 弹窗后的审批结果。

    - "once"：不缓存（下次相同参数仍弹）
    - "always"：write 级入 allow 缓存；destructive 不入（每次必弹）
    - "deny"：入 deny 缓存（本会话内拒绝相同参数）
    - "auto"：无需记录
    """
    if mode == "deny":
        _DENY_CACHE.add(args_hash(tool_name, args, kwargs))
        return

    if mode == "always" and permission_level == "write":
        _WRITE_CACHE.add(args_hash(tool_name, args, kwargs))


def is_cached_allow(
    tool_name: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> bool:
    """查询是否命中会话内 allow 缓存（调试用）。"""
    return args_hash(tool_name, args, kwargs) in _WRITE_CACHE


def is_cached_deny(
    tool_name: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> bool:
    """查询是否命中会话内 deny 缓存（调试用）。"""
    return args_hash(tool_name, args, kwargs) in _DENY_CACHE


# ---- 永不沙箱风险知情 ----


def needs_sandbox_risk_ack() -> bool:
    """首次使用 destructive 工具前检查 settings 是否已确认。"""
    if not SETTINGS_FILE.exists():
        return True
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    return not bool(data.get("sandbox_risk_acked", False))


def ack_sandbox_risk() -> None:
    """用户已了解永不沙箱风险，写入 settings.json。"""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data["sandbox_risk_acked"] = True
    SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
