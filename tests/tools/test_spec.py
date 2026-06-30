"""M1 协议层测试：@tool 装饰器扩展 + ToolMeta.to_spec() + ToolSpec + ExternalToolSource Protocol。

覆盖：
- @tool 装饰器新参数（version/timeout/long_running/concurrency_safe/
  permission_level/needs_confirmation）
- needs_confirmation=None 自动推导逻辑（read_only→False / write→True / destructive→True）
- needs_confirmation 显式覆盖
- lookup 找不到返回 None
- lookup_spec 返回 ToolSpec 视图且字段映射正确
- ToolMeta.to_spec() 字段转换
- ExternalToolSource Protocol runtime_checkable
- 工具名冲突抛 ValueError
"""

from __future__ import annotations

import pytest

from q_agent.tools.registry import _TOOLS, lookup, lookup_spec, tool
from q_agent.tools.spec import ExternalToolSource, ToolSpec

# ---------- @tool 装饰器新参数 ----------


def test_tool_default_params() -> None:
    """@tool 不传可选参数时应使用默认值。"""

    @tool(name="test_default", desc="测试默认参数")
    def fn(x: str) -> str:
        return x

    try:
        meta = lookup("test_default")
        assert meta is not None
        assert meta.version == "1.0.0"
        assert meta.timeout is None
        assert meta.long_running is False
        assert meta.concurrency_safe is False
        assert meta.permission_level == "read_only"
        # read_only 默认推导为 False
        assert meta.needs_confirmation is False
    finally:
        _TOOLS.pop("test_default", None)


def test_tool_custom_params() -> None:
    """@tool 传自定义参数时应正确填入 ToolMeta。"""

    @tool(
        name="test_custom",
        desc="测试自定义参数",
        version="2.1.3",
        timeout=30.0,
        long_running=True,
        concurrency_safe=True,
        permission_level="write",
    )
    def fn(x: str) -> str:
        return x

    try:
        meta = lookup("test_custom")
        assert meta is not None
        assert meta.version == "2.1.3"
        assert meta.timeout == 30.0
        assert meta.long_running is True
        assert meta.concurrency_safe is True
        assert meta.permission_level == "write"
        # write 默认推导为 True
        assert meta.needs_confirmation is True
    finally:
        _TOOLS.pop("test_custom", None)


# ---------- needs_confirmation 推导逻辑 ----------


def test_needs_confirmation_auto_read_only() -> None:
    """read_only 权限 + needs_confirmation=None → 推导为 False。"""

    @tool(name="test_auto_ro", desc="测试", permission_level="read_only")
    def fn(x: str) -> str:
        return x

    try:
        assert lookup("test_auto_ro").needs_confirmation is False
    finally:
        _TOOLS.pop("test_auto_ro", None)


def test_needs_confirmation_auto_write() -> None:
    """write 权限 + needs_confirmation=None → 推导为 True。"""

    @tool(name="test_auto_w", desc="测试", permission_level="write")
    def fn(x: str) -> str:
        return x

    try:
        assert lookup("test_auto_w").needs_confirmation is True
    finally:
        _TOOLS.pop("test_auto_w", None)


def test_needs_confirmation_auto_destructive() -> None:
    """destructive 权限 + needs_confirmation=None → 推导为 True。"""

    @tool(name="test_auto_d", desc="测试", permission_level="destructive")
    def fn(x: str) -> str:
        return x

    try:
        assert lookup("test_auto_d").needs_confirmation is True
    finally:
        _TOOLS.pop("test_auto_d", None)


def test_needs_confirmation_explicit_override() -> None:
    """needs_confirmation 显式传值应覆盖默认推导。"""

    @tool(
        name="test_override",
        desc="测试",
        permission_level="destructive",
        needs_confirmation=False,
    )
    def fn(x: str) -> str:
        return x

    try:
        # destructive 默认推导为 True，但显式传 False 应覆盖
        assert lookup("test_override").needs_confirmation is False
    finally:
        _TOOLS.pop("test_override", None)


# ---------- lookup / lookup_spec ----------


def test_lookup_not_found() -> None:
    """查找不存在的工具应返回 None。"""
    assert lookup("nonexistent_tool_xyz") is None


def test_lookup_spec_not_found() -> None:
    """lookup_spec 查找不到应返回 None。"""
    assert lookup_spec("nonexistent_tool_xyz") is None


def test_lookup_spec_returns_tool_spec() -> None:
    """lookup_spec 应返回 ToolSpec 实例，且字段映射正确。"""

    @tool(
        name="test_spec_view",
        desc="测试 ToolSpec 视图",
        version="1.2.0",
        timeout=20.0,
        permission_level="write",
    )
    def fn(x: str, y: int = 0) -> str:
        return x

    try:
        spec = lookup_spec("test_spec_view")
        assert spec is not None
        assert isinstance(spec, ToolSpec)
        assert spec.name == "test_spec_view"
        assert spec.description == "测试 ToolSpec 视图"
        assert spec.version == "1.2.0"
        assert spec.timeout == 20.0
        assert spec.permission_level == "write"
        assert spec.needs_confirmation is True  # write 推导
        assert spec.output_schema == "str"
        # inspect.signature 输出格式（from __future__ import annotations 下类型字符串化为 'str'）
        assert "x" in spec.input_schema and "str" in spec.input_schema
        assert spec.call("hello") == "hello"
    finally:
        _TOOLS.pop("test_spec_view", None)


# ---------- ToolMeta.to_spec() ----------


def test_toolmeta_to_spec_field_mapping() -> None:
    """ToolMeta.to_spec() 应正确映射所有字段到 ToolSpec。"""

    @tool(
        name="test_mapping",
        desc="测试字段映射",
        version="3.0.0",
        timeout=42.0,
        long_running=True,
        concurrency_safe=True,
        permission_level="destructive",
    )
    def fn(a: str, b: int) -> str:
        return f"{a}-{b}"

    try:
        meta = lookup("test_mapping")
        assert meta is not None
        spec = meta.to_spec()
        assert isinstance(spec, ToolSpec)
        assert spec.name == meta.name
        assert spec.description == meta.desc
        assert spec.version == meta.version
        assert spec.timeout == meta.timeout
        assert spec.concurrency_safe == meta.concurrency_safe
        assert spec.permission_level == meta.permission_level
        assert spec.needs_confirmation == meta.needs_confirmation
        # call 应指向原函数
        assert spec.call("x", 1) == "x-1"
        # input_schema 应为 inspect.signature 字符串（含参数名和类型）
        assert "a" in spec.input_schema and "b" in spec.input_schema
        assert "str" in spec.input_schema and "int" in spec.input_schema
    finally:
        _TOOLS.pop("test_mapping", None)


# ---------- ExternalToolSource Protocol ----------


class _FakeExternalSource:
    """模拟外部工具源（实现 ExternalToolSource Protocol）。"""

    def list_tools(self) -> list[ToolSpec]:
        return []

    def get_tool(self, name: str) -> ToolSpec | None:
        return None

    def refresh(self) -> None:
        pass


def test_external_tool_source_protocol_runtime_checkable() -> None:
    """实现 ExternalToolSource 三个方法的类应通过 isinstance 检查。"""
    source = _FakeExternalSource()
    assert isinstance(source, ExternalToolSource)


def test_external_tool_source_protocol_rejects_incomplete() -> None:
    """缺方法的类不应通过 isinstance 检查。"""

    class _Incomplete:
        def list_tools(self) -> list[ToolSpec]:
            return []

    # 缺 get_tool / refresh 两个方法
    assert not isinstance(_Incomplete(), ExternalToolSource)


# ---------- 工具名冲突 ----------


def test_tool_name_conflict_rejected() -> None:
    """重名注册应抛 ValueError，且不影响已有项。"""

    @tool(name="test_conflict", desc="第一次")
    def fn1(x: str) -> str:
        return x

    try:
        with pytest.raises(ValueError, match="工具名冲突"):

            @tool(name="test_conflict", desc="第二次")
            def fn2(x: str) -> str:
                return x

        # 原注册项未被覆盖
        meta = lookup("test_conflict")
        assert meta is not None
        assert meta.desc == "第一次"
        assert meta.fn("a") == "a"
    finally:
        _TOOLS.pop("test_conflict", None)


# ---------- ToolSpec 直接构造 ----------


def test_toolspec_direct_construction() -> None:
    """ToolSpec 应能直接构造（v0.0.21+ MCP 适配器用此方式）。"""

    def call(x: str) -> str:
        return x

    spec = ToolSpec(
        name="external_tool",
        description="外部工具示例",
        version="0.1.0",
        input_schema='{"type": "object", "properties": {"x": {"type": "string"}}}',
        output_schema='{"type": "string"}',
        concurrency_safe=False,
        permission_level="read_only",
        needs_confirmation=False,
        timeout=10.0,
        call=call,
    )
    assert spec.name == "external_tool"
    assert spec.call("hello") == "hello"
    assert spec.permission_level == "read_only"
