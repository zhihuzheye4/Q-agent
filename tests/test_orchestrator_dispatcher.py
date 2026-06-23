"""dispatcher 测试（v0.0.18）。

mock executor + 解析各种 LLM 输出格式 + doom_loop 签名。
"""

from q_agent.orchestrator.dispatcher import (
    execute_tool_calls,
    parse_response,
    synthetic_assistant_message,
    tool_results_to_messages,
    tool_signature,
)
from q_agent.orchestrator.types import Role, ToolCall, ToolResult

# ---- parse_response ----


def test_parse_response_plain_text() -> None:
    """纯文本无工具调用。"""
    parsed = parse_response("你好，我是 AI")
    assert parsed.assistant_text == "你好，我是 AI"
    assert parsed.tool_calls == []


def test_parse_response_with_json_block() -> None:
    """含 ```json ... ``` 块的 tool_calls。"""
    raw = (
        "正在读取文件\n```json\n"
        '{"id": "call_1", "name": "read_file", "arguments": {"path": "x.py"}}\n'
        "```\n完成"
    )
    parsed = parse_response(raw)
    assert "正在读取文件" in parsed.assistant_text
    assert "完成" in parsed.assistant_text
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].id == "call_1"
    assert parsed.tool_calls[0].name == "read_file"
    assert parsed.tool_calls[0].arguments == {"path": "x.py"}


def test_parse_response_with_array_json() -> None:
    """JSON 数组多个工具调用。"""
    raw = (
        "```json\n"
        '[{"id": "c1", "name": "a", "arguments": {}}, '
        '{"id": "c2", "name": "b", "arguments": {"x": 1}}]\n```'
    )
    parsed = parse_response(raw)
    assert len(parsed.tool_calls) == 2
    assert parsed.tool_calls[0].name == "a"
    assert parsed.tool_calls[1].name == "b"


def test_parse_response_invalid_json_kept_as_text() -> None:
    """JSON 解析失败 → 整块作为文本保留。"""
    raw = "```json\nnot valid json\n```"
    parsed = parse_response(raw)
    assert "```json" in parsed.assistant_text
    assert parsed.tool_calls == []


def test_parse_response_openai_function_format() -> None:
    """OpenAI function 格式 {id, function: {name, arguments}}。"""
    raw = '```json\n{"id": "c1", "function": {"name": "read", "arguments": {"path": "y.py"}}}\n```'
    parsed = parse_response(raw)
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "read"
    assert parsed.tool_calls[0].arguments == {"path": "y.py"}


def test_parse_response_auto_generated_id() -> None:
    """无 id 字段自动生成 call_xxx。"""
    raw = '```json\n{"name": "echo", "arguments": {}}\n```'
    parsed = parse_response(raw)
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].id.startswith("call_")


# ---- execute_tool_calls ----


class MockExecutor:
    """mock executor，支持配置返回值 + 记录调用。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.return_values: dict[str, str] = {}
        self.raise_errors: dict[str, Exception] = {}

    def execute_tool(self, name: str, **kwargs: object) -> str:
        self.calls.append((name, dict(kwargs)))
        if name in self.raise_errors:
            raise self.raise_errors[name]
        return self.return_values.get(name, f"result_of_{name}")


def test_execute_tool_calls_happy() -> None:
    """工具调用 happy path。"""
    executor = MockExecutor()
    executor.return_values["read_file"] = "file content"
    calls = [ToolCall(id="c1", name="read_file", arguments={"path": "x.py"})]

    results = execute_tool_calls(calls, executor)
    assert len(results) == 1
    assert results[0].call_id == "c1"
    assert results[0].content == "file content"
    assert results[0].error is None
    assert executor.calls == [("read_file", {"path": "x.py"})]


def test_execute_tool_calls_error_captured() -> None:
    """工具抛异常 → ToolResult.error 不外泄。"""
    executor = MockExecutor()
    executor.raise_errors["bad_tool"] = ValueError("boom")
    calls = [ToolCall(id="c1", name="bad_tool", arguments={})]

    results = execute_tool_calls(calls, executor)
    assert results[0].error is not None
    assert "ValueError" in results[0].error
    assert "boom" in results[0].error


def test_execute_tool_calls_permission_error() -> None:
    """权限错误单独捕获。"""
    executor = MockExecutor()
    executor.raise_errors["rm"] = PermissionError("危险命令")
    calls = [ToolCall(id="c1", name="rm", arguments={})]

    results = execute_tool_calls(calls, executor)
    assert "权限拒绝" in (results[0].error or "")


def test_execute_tool_calls_no_execute_method() -> None:
    """executor 未实现 execute_tool → 错误回喂。"""

    class Empty:
        pass

    calls = [ToolCall(id="c1", name="x", arguments={})]
    results = execute_tool_calls(calls, Empty())
    assert "executor 未实现" in (results[0].error or "")


def test_execute_tool_calls_multiple() -> None:
    """多个工具调用顺序执行。"""
    executor = MockExecutor()
    calls = [
        ToolCall(id="c1", name="a", arguments={}),
        ToolCall(id="c2", name="b", arguments={}),
    ]
    results = execute_tool_calls(calls, executor)
    assert len(results) == 2
    assert len(executor.calls) == 2


# ---- tool_results_to_messages ----


def test_tool_results_to_messages_success() -> None:
    """成功结果 → role=TOOL 消息。"""
    results = [ToolResult(call_id="c1", content="ok")]
    msgs = tool_results_to_messages(results)
    assert len(msgs) == 1
    assert msgs[0].role == Role.TOOL
    assert msgs[0].content == "ok"
    assert msgs[0].tool_call_id == "c1"


def test_tool_results_to_messages_error() -> None:
    """失败结果 → role=TOOL 消息含 [工具执行失败]。"""
    results = [ToolResult(call_id="c1", content="", error="boom")]
    msgs = tool_results_to_messages(results)
    assert "[工具执行失败]" in msgs[0].content
    assert "boom" in msgs[0].content


# ---- synthetic_assistant_message ----


def test_synthetic_assistant_message() -> None:
    """合成消息标记 is_synthetic=True。"""
    m = synthetic_assistant_message("[LLM 失败] xxx")
    assert m.role == Role.ASSISTANT
    assert m.is_synthetic is True
    assert m.content == "[LLM 失败] xxx"


def test_synthetic_assistant_message_with_tool_calls() -> None:
    """带 tool_calls 的合成消息。"""
    tc = ToolCall(id="c1", name="x", arguments={})
    m = synthetic_assistant_message("text", [tc])
    assert len(m.tool_calls) == 1


# ---- tool_signature ----


def test_tool_signature_stable() -> None:
    """相同参数 → 相同签名。"""
    tc1 = ToolCall(id="c1", name="read", arguments={"path": "x.py"})
    tc2 = ToolCall(id="c2", name="read", arguments={"path": "x.py"})
    assert tool_signature(tc1) == tool_signature(tc2)


def test_tool_signature_diff_args() -> None:
    """不同参数 → 不同签名。"""
    tc1 = ToolCall(id="c1", name="read", arguments={"path": "x.py"})
    tc2 = ToolCall(id="c2", name="read", arguments={"path": "y.py"})
    assert tool_signature(tc1) != tool_signature(tc2)


def test_tool_signature_diff_name() -> None:
    """不同名 → 不同签名。"""
    tc1 = ToolCall(id="c1", name="read", arguments={})
    tc2 = ToolCall(id="c2", name="write", arguments={})
    assert tool_signature(tc1) != tool_signature(tc2)
