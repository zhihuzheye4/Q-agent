"""@tool 装饰器 + 工具注册表。LLM 通过工具调用层执行操作。

v0.0.19 扩展：装饰器签名增加 version/timeout/long_running/concurrency_safe/
permission_level/needs_confirmation 参数，支持审批/超时/权限分级生命周期。
新增 lookup_spec() 返回 ToolSpec 视图供编排层使用。
"""

import inspect
from collections.abc import Callable
from typing import Any

from q_agent.tools.base import PermissionLevel, ToolMeta
from q_agent.tools.spec import ToolSpec

_TOOLS: dict[str, ToolMeta] = {}


def tool(
    name: str,
    desc: str = "",
    *,
    version: str = "1.0.0",
    timeout: float | None = None,
    long_running: bool = False,
    concurrency_safe: bool = False,
    permission_level: PermissionLevel = "read_only",
    needs_confirmation: bool | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器：登记工具函数 + 元数据 + 协议字段。

    参数说明：
    - name: snake_case，前缀 file_/search_/exec_/web_
    - desc: ≤200 字中文，四要素模板（何时用 / 何时不用 / 参数约束 / 返回格式）
    - version: 语义化 major.minor.patch，回放时宽松兼容
    - timeout: 秒；None 走工具类默认（read 15 / write 10 / shell 120 / http 30）
    - long_running: 仅 exec_shell，True 时 timeout 提升到 600
    - concurrency_safe: v0.0.19 串行全 False，预留 v0.0.21+ 多线程
    - permission_level: read_only / write / destructive
    - needs_confirmation: None 时按 destructive→True / write→True / read_only→False 推导
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _TOOLS:
            raise ValueError(f"工具名冲突: {name}")
        meta = ToolMeta(
            name=name,
            desc=desc,
            fn=fn,
            signature=str(inspect.signature(fn)),
            version=version,
            timeout=timeout,
            long_running=long_running,
            concurrency_safe=concurrency_safe,
            permission_level=permission_level,
            needs_confirmation=(
                needs_confirmation
                if needs_confirmation is not None
                else permission_level in ("write", "destructive")
            ),
        )
        _TOOLS[name] = meta
        return fn

    return deco


def lookup(name: str) -> ToolMeta | None:
    """按名查找工具元数据。"""
    return _TOOLS.get(name)


def lookup_spec(name: str) -> ToolSpec | None:
    """返回 ToolSpec 视图（供编排层 / 外部源使用）。"""
    meta = _TOOLS.get(name)
    return meta.to_spec() if meta else None


def all_tools() -> list[ToolMeta]:
    """返回所有已注册工具。"""
    return list(_TOOLS.values())
