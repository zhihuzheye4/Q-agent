"""工具协议规范。内置 @tool 与外部源（v0.0.21+ MCP）统一形态。

编排层只认 ToolSpec，不认具体源——这让未来 MCP 适配器可以零侵入接入。
"""

from collections.abc import Callable
from typing import Literal, Protocol, runtime_checkable

PermissionLevel = Literal["read_only", "write", "destructive"]


class ToolSpec:
    """工具协议规范：内置 @tool 与外部 tool 源（MCP 等）统一形态。

    v0.0.19 内置工具通过 ToolMeta.to_spec() 转换；
    v0.0.21+ MCP 外部源直接实现 ExternalToolSource Protocol 返回 ToolSpec 列表。

    字段说明：
    - name: snake_case 工具名，前缀 file_/search_/exec_/web_
    - description: 工具描述，供编排层注入 system prompt
    - version: 语义化版本号 major.minor.patch
    - input_schema: inspect.signature 字符串（内置）或 JSON Schema（外部源）
    - output_schema: "str"（v0.0.19 内置统一）或 JSON Schema
    - concurrency_safe: v0.0.19 全 False（串行），v0.0.21+ 多线程时再标 True
    - permission_level: read_only / write / destructive
    - needs_confirmation: 是否需用户审批
    - timeout: 超时秒数；None 走工具类默认
    - call: 实际调用入口（内置=fn，外部源=适配器包装）
    """

    name: str
    description: str
    version: str
    input_schema: str
    output_schema: str
    concurrency_safe: bool
    permission_level: PermissionLevel
    needs_confirmation: bool
    timeout: float | None
    call: Callable[..., str]

    def __init__(
        self,
        name: str,
        description: str,
        version: str,
        input_schema: str,
        output_schema: str,
        concurrency_safe: bool,
        permission_level: PermissionLevel,
        needs_confirmation: bool,
        timeout: float | None,
        call: Callable[..., str],
    ) -> None:
        self.name = name
        self.description = description
        self.version = version
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.concurrency_safe = concurrency_safe
        self.permission_level = permission_level
        self.needs_confirmation = needs_confirmation
        self.timeout = timeout
        self.call = call


@runtime_checkable
class ExternalToolSource(Protocol):
    """外部工具源协议：v0.0.21+ MCP 适配器实现此 Protocol 即可零侵入接入。

    编排层只认 ToolSpec，不认具体源——MCP 适配器只需把 MCP 工具转成 ToolSpec 列表，
    实现 list_tools / get_tool / refresh 三个方法即可被编排层统一调度。
    """

    def list_tools(self) -> list[ToolSpec]: ...
    def get_tool(self, name: str) -> ToolSpec | None: ...
    def refresh(self) -> None: ...
