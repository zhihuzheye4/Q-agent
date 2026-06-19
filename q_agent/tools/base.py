"""工具元数据 dataclass。工具调用层（替代沙箱）。"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolMeta:
    """工具元数据：名称、描述、函数、签名。"""

    name: str
    desc: str
    fn: Callable[..., Any]
    signature: str
