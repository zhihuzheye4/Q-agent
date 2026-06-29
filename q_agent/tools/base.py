"""工具元数据 dataclass。工具调用层（替代沙箱）。

v0.0.19 扩展：增加 version/timeout/long_running/concurrency_safe/permission_level/
needs_confirmation 字段，支持审批/超时/权限分级生命周期。
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from q_agent.tools.spec import ToolSpec

PermissionLevel = Literal["read_only", "write", "destructive"]


@dataclass
class ToolMeta:
    """工具元数据：名称、描述、函数、签名 + 协议字段。

    协议字段由 @tool 装饰器在注册时填入，to_spec() 转换为 ToolSpec 供编排层使用。
    """

    name: str
    desc: str
    fn: Callable[..., Any]
    signature: str
    version: str = "1.0.0"
    timeout: float | None = None
    long_running: bool = False
    concurrency_safe: bool = False
    permission_level: PermissionLevel = "read_only"
    needs_confirmation: bool = False

    def to_spec(self) -> ToolSpec:
        """转换为 ToolSpec 协议视图（供编排层 / 外部源使用）。"""
        return ToolSpec(
            name=self.name,
            description=self.desc,
            version=self.version,
            input_schema=self.signature,
            output_schema="str",
            concurrency_safe=self.concurrency_safe,
            permission_level=self.permission_level,
            needs_confirmation=self.needs_confirmation,
            timeout=self.timeout,
            call=self.fn,
        )
