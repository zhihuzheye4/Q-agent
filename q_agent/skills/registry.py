"""@skill 装饰器 + 全局注册表。函数签名即协议。"""

import inspect
from collections.abc import Callable
from typing import Any

from q_agent.skills.base import SkillMeta

_REGISTRY: dict[str, SkillMeta] = {}


def skill(name: str, desc: str = "") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器：登记函数 + 元数据，签名 inspect 用于协议校验。"""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _REGISTRY:
            raise ValueError(f"技能名冲突: {name}")
        _REGISTRY[name] = SkillMeta(
            name=name,
            desc=desc,
            fn=fn,
            signature=str(inspect.signature(fn)),
        )
        return fn

    return deco


def lookup(name: str) -> SkillMeta | None:
    """按名查找技能。"""
    return _REGISTRY.get(name)


def all_skills() -> list[SkillMeta]:
    """返回所有已注册技能。"""
    return list(_REGISTRY.values())
