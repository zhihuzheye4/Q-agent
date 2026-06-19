"""技能元数据 dataclass。"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class SkillMeta:
    """技能元数据：名称、描述、函数、签名。"""

    name: str
    desc: str
    fn: Callable[..., Any]
    signature: str
