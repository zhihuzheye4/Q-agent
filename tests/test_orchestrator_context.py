"""ContextManager 测试（v0.0.18）。

4 级压缩 + 标识符保留 + token 计数 + 工具结果落盘。
"""

from pathlib import Path

import pytest

from q_agent.orchestrator.context import SUMMARY_SYSTEM_PROMPT, ContextConfig, ContextManager
from q_agent.orchestrator.persistence import SessionStore
from q_agent.orchestrator.types import Message, Role, ToolCall


@pytest.fixture
def context(tmp_path: Path) -> ContextManager:
    """临时 ContextManager + SessionStore。"""
    store = SessionStore(tmp_path / "test.db")
    store.create_session("s1")
    return ContextManager(
        session_id="s1",
        session_store=store,
        tool_results_dir=tmp_path / "tool_results",
    )


def test_append_message_basic(context: ContextManager) -> None:
    """追加消息到内存 + sqlite3。"""
    msg = Message(session_id="s1", role=Role.USER, content="hello")
    persisted = context.append_message(msg)
    assert persisted.id is not None
    assert persisted.created_at is not None
    assert len(context.messages) == 1


def test_estimate_tokens(context: ContextManager) -> None:
    """token 计数 = 字符数 / 4。"""
    msg = Message(session_id="s1", role=Role.USER, content="abcd")
    context.append_message(msg)
    # "abcd" 4 字符 / 4 = 1 token
    assert context.estimate_tokens() == 1


def test_estimate_tokens_with_tool_calls(context: ContextManager) -> None:
    """含 tool_calls 的 token 计数。"""
    tc = ToolCall(id="c1", name="read_file", arguments={"path": "x.py"})
    msg = Message(session_id="s1", role=Role.ASSISTANT, content="ok", tool_calls=[tc])
    context.append_message(msg)
    # "ok" + "read_file" + str({"path": "x.py"}) 字符总和 / 4
    tokens = context.estimate_tokens()
    assert tokens > 0


def test_check_compaction_no_trigger(context: ContextManager) -> None:
    """低 token 不触发压缩。"""
    context.append_message(Message(session_id="s1", role=Role.USER, content="短"))
    trigger = context.check_compaction()
    assert trigger.triggered is False
    assert trigger.level == 0


def test_check_compaction_level2(context: ContextManager) -> None:
    """70% 触发第 2 级。"""
    config = ContextConfig(max_tokens=100, soft_limit_l1_ratio=0.7)
    context.config = config
    # 70 字符 / 4 = 17 token，70% of 100 = 70，所以需要 280 字符
    context.append_message(Message(session_id="s1", role=Role.USER, content="x" * 280))
    trigger = context.check_compaction()
    assert trigger.triggered is True
    assert trigger.level == 2


def test_check_compaction_level3(context: ContextManager) -> None:
    """85% 触发第 3 级。"""
    context.config = ContextConfig(
        max_tokens=100, soft_limit_l1_ratio=0.7, soft_limit_l2_ratio=0.85
    )
    # 85% of 100 = 85 tokens = 340 字符
    context.append_message(Message(session_id="s1", role=Role.USER, content="x" * 340))
    trigger = context.check_compaction()
    assert trigger.triggered is True
    assert trigger.level == 3


def test_check_compaction_level4(context: ContextManager) -> None:
    """100% 触发第 4 级。"""
    context.config = ContextConfig(
        max_tokens=100,
        soft_limit_l1_ratio=0.7,
        soft_limit_l2_ratio=0.85,
        hard_limit_ratio=1.0,
    )
    # 100 tokens = 400 字符
    context.append_message(Message(session_id="s1", role=Role.USER, content="x" * 400))
    trigger = context.check_compaction()
    assert trigger.triggered is True
    assert trigger.level == 4


def test_apply_level2_truncate(context: ContextManager) -> None:
    """第 2 级截断：旧消息取前 200 字符。"""
    context.config = ContextConfig(keep_recent=2, old_message_truncate_chars=50)
    # 加 5 条消息，保留最近 2 条
    for i in range(5):
        context.append_message(
            Message(session_id="s1", role=Role.USER, content=f"msg{i}_" + "x" * 100)
        )

    result = context.apply_level2_truncate()
    assert result.triggered is True

    msgs = context.messages
    # 前 3 条被截断
    assert msgs[0].is_compacted is True
    assert "...[已截断]" in msgs[0].content
    # 最近 2 条不动
    assert msgs[3].is_compacted is False
    assert msgs[4].is_compacted is False


def test_apply_level2_truncate_skip_compacted(context: ContextManager) -> None:
    """已截断的消息不再二次截断。"""
    context.config = ContextConfig(keep_recent=1, old_message_truncate_chars=50)
    # 第一条长
    context.append_message(Message(session_id="s1", role=Role.USER, content="x" * 100))
    # 第二条短（在 keep_recent 内）
    context.append_message(Message(session_id="s1", role=Role.USER, content="短"))

    context.apply_level2_truncate()
    first_content = context.messages[0].content

    # 再次截断，内容不应再变
    context.apply_level2_truncate()
    assert context.messages[0].content == first_content


def test_apply_level2_truncate_no_action_when_short(context: ContextManager) -> None:
    """消息数 <= keep_recent 时不截断。"""
    context.config = ContextConfig(keep_recent=10)
    context.append_message(Message(session_id="s1", role=Role.USER, content="a"))
    context.append_message(Message(session_id="s1", role=Role.USER, content="b"))

    result = context.apply_level2_truncate()
    assert result.triggered is False


def test_compact_tool_result(context: ContextManager) -> None:
    """第 1 级：工具结果 > 2000 字符落盘 + 占位。"""
    long_content = "x" * 3000
    msg = Message(
        session_id="s1",
        role=Role.TOOL,
        content=long_content,
        tool_call_id="call_1",
    )
    persisted = context.append_message(msg)

    assert "x" * 100 not in persisted.content  # 原文已替换
    assert "内容已清空" in persisted.content
    # 落盘文件存在
    out_file = context.tool_results_dir / "call_1.txt"
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == long_content


def test_compact_tool_result_short_kept(context: ContextManager) -> None:
    """短工具结果不压缩。"""
    msg = Message(
        session_id="s1",
        role=Role.TOOL,
        content="short result",
        tool_call_id="call_1",
    )
    persisted = context.append_message(msg)
    assert persisted.content == "short result"


def test_to_llm_messages(context: ContextManager) -> None:
    """转 Ollama 格式。"""
    context.append_message(Message(session_id="s1", role=Role.SYSTEM, content="sys"))
    context.append_message(Message(session_id="s1", role=Role.USER, content="hi"))

    llm_msgs = context.to_llm_messages()
    assert llm_msgs[0] == {"role": "system", "content": "sys"}
    assert llm_msgs[1] == {"role": "user", "content": "hi"}


def test_load_history(context: ContextManager) -> None:
    """load_history 从 sqlite3 加载。"""
    context.append_message(Message(session_id="s1", role=Role.USER, content="m1"))
    context.append_message(Message(session_id="s1", role=Role.ASSISTANT, content="m2"))

    # 新 ContextManager（模拟重启）
    store = context.session_store
    new_ctx = ContextManager(session_id="s1", session_store=store)
    assert new_ctx.messages == []
    new_ctx.load_history()
    assert len(new_ctx.messages) == 2
    assert new_ctx.messages[0].content == "m1"


def test_summary_system_prompt_contains_identifiers() -> None:
    """标识符保留指令包含关键类别。"""
    assert "文件路径" in SUMMARY_SYSTEM_PROMPT
    assert "工具调用 ID" in SUMMARY_SYSTEM_PROMPT
    assert "URL" in SUMMARY_SYSTEM_PROMPT
    assert "哈希值" in SUMMARY_SYSTEM_PROMPT
    assert "函数名" in SUMMARY_SYSTEM_PROMPT
    assert "错误码" in SUMMARY_SYSTEM_PROMPT


def test_prepare_summary_chunks(context: ContextManager) -> None:
    """第 3 级：切分消息块。"""
    context.config = ContextConfig(keep_recent=2, compaction_chunk_tokens=100)
    # 加 5 条消息，保留最近 2 条，前 3 条进入分块
    for i in range(5):
        context.append_message(Message(session_id="s1", role=Role.USER, content=f"msg{i}"))

    chunks = context.prepare_summary_chunks()
    assert len(chunks) >= 1
    # 前 3 条消息应在某个 chunk 里
    all_text = "\n".join(chunks)
    assert "msg0" in all_text
    assert "msg2" in all_text
    # 最近 2 条不在 chunk 里
    assert "msg3" not in all_text
    assert "msg4" not in all_text


def test_merge_pending_summary(context: ContextManager) -> None:
    """合并摘要：旧消息替换为一条 SYSTEM 摘要消息。"""
    context.config = ContextConfig(keep_recent=2)
    for i in range(5):
        context.append_message(Message(session_id="s1", role=Role.USER, content=f"msg{i}"))

    context.merge_pending_summary("这是摘要内容")

    msgs = context.messages
    # 第一条应是摘要 SYSTEM 消息
    assert msgs[0].role == Role.SYSTEM
    assert "上下文摘要" in msgs[0].content
    assert "这是摘要内容" in msgs[0].content
    # 最近 2 条保留
    assert msgs[-1].content == "msg4"


def test_is_hard_overflow(context: ContextManager) -> None:
    """硬溢出判定。"""
    context.config = ContextConfig(max_tokens=100)
    context.append_message(Message(session_id="s1", role=Role.USER, content="x" * 400))
    assert context.is_hard_overflow() is True
