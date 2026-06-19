"""@tool 装饰器 + 工具注册表。LLM 通过工具调用层执行操作。"""

import inspect
from collections.abc import Callable
from typing import Any

from q_agent.tools.base import ToolMeta

_TOOLS: dict[str, ToolMeta] = {}


def tool(name: str, desc: str = "") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器：登记工具函数 + 元数据。"""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _TOOLS:
            raise ValueError(f"工具名冲突: {name}")
        _TOOLS[name] = ToolMeta(
            name=name,
            desc=desc,
            fn=fn,
            signature=str(inspect.signature(fn)),
        )
        return fn

    return deco


def lookup(name: str) -> ToolMeta | None:
    """按名查找工具。"""
    return _TOOLS.get(name)


def all_tools() -> list[ToolMeta]:
    """返回所有已注册工具。"""
    return list(_TOOLS.values())
