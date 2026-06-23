"""SessionStore 持久化层测试（v0.0.18）。

使用 tmp_path fixture 创建临时 sqlite3 文件，测试所有 CRUD 路径。
"""

from pathlib import Path

import pytest

from q_agent.orchestrator.persistence import SessionStore
from q_agent.orchestrator.types import (
    CompactionRecord,
    Message,
    Role,
    ToolCall,
)


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    """临时 SessionStore。"""
    return SessionStore(tmp_path / "test.db")


def test_create_and_load_session(store: SessionStore) -> None:
    """创建会话 + 加载。"""
    data = store.create_session("s1")
    assert data.session_id == "s1"
    assert data.message_count == 0
    assert data.is_archived is False

    loaded = store.load_session("s1")
    assert loaded is not None
    assert loaded.session_id == "s1"


def test_create_session_duplicate_raises(store: SessionStore) -> None:
    """重复创建会话抛 ValueError。"""
    store.create_session("s1")
    with pytest.raises(ValueError, match="会话已存在"):
        store.create_session("s1")


def test_load_session_not_exist(store: SessionStore) -> None:
    """加载不存在的会话返回 None。"""
    assert store.load_session("nonexistent") is None


def test_append_and_load_messages(store: SessionStore) -> None:
    """追加消息 + 按时间正序加载。"""
    store.create_session("s1")
    m1 = Message(session_id="s1", role=Role.USER, content="hello")
    m2 = Message(session_id="s1", role=Role.ASSISTANT, content="hi")
    store.append_message(m1)
    store.append_message(m2)

    loaded = store.load_messages("s1")
    assert len(loaded) == 2
    assert loaded[0].content == "hello"
    assert loaded[1].content == "hi"
    # id 被回填
    assert loaded[0].id is not None
    assert loaded[1].id is not None
    # created_at 被回填
    assert loaded[0].created_at is not None


def test_load_messages_with_limit(store: SessionStore) -> None:
    """limit 只加载最近 N 条（分页加载 2000+ 轮）。"""
    store.create_session("s1")
    for i in range(10):
        store.append_message(Message(session_id="s1", role=Role.USER, content=f"msg{i}"))

    loaded = store.load_messages("s1", limit=3)
    assert len(loaded) == 3
    # 最近 3 条（按时间正序）
    assert loaded[0].content == "msg7"
    assert loaded[2].content == "msg9"


def test_append_message_with_tool_calls(store: SessionStore) -> None:
    """带 tool_calls 的消息持久化 + 回读。"""
    store.create_session("s1")
    tc = ToolCall(id="call_1", name="read_file", arguments={"path": "x.py"})
    msg = Message(
        session_id="s1",
        role=Role.ASSISTANT,
        content="正在读取",
        tool_calls=[tc],
    )
    store.append_message(msg)

    loaded = store.load_messages("s1")
    assert len(loaded[0].tool_calls) == 1
    assert loaded[0].tool_calls[0].id == "call_1"
    assert loaded[0].tool_calls[0].name == "read_file"
    assert loaded[0].tool_calls[0].arguments == {"path": "x.py"}


def test_append_tool_result_message(store: SessionStore) -> None:
    """role=TOOL 消息带 tool_call_id。"""
    store.create_session("s1")
    msg = Message(
        session_id="s1",
        role=Role.TOOL,
        content="file content here",
        tool_call_id="call_1",
    )
    store.append_message(msg)

    loaded = store.load_messages("s1")
    assert loaded[0].role == Role.TOOL
    assert loaded[0].tool_call_id == "call_1"


def test_update_message_content(store: SessionStore) -> None:
    """压缩后更新消息内容 + is_compacted 标记。"""
    store.create_session("s1")
    msg = Message(session_id="s1", role=Role.USER, content="原长文本" * 100)
    persisted = store.append_message(msg)

    store.update_message_content(persisted.id, "[已截断]", is_compacted=True)
    loaded = store.load_messages("s1")
    assert loaded[0].content == "[已截断]"
    assert loaded[0].is_compacted is True


def test_archive_session(store: SessionStore) -> None:
    """归档会话 + 列表过滤。"""
    store.create_session("s1")
    store.create_session("s2")
    store.archive_session("s1")

    # 默认排除归档
    active = store.list_sessions()
    assert len(active) == 1
    assert active[0].session_id == "s2"

    # 包含归档
    all_sessions = store.list_sessions(include_archived=True)
    assert len(all_sessions) == 2
    archived = next(s for s in all_sessions if s.session_id == "s1")
    assert archived.is_archived is True


def test_record_and_list_compaction(store: SessionStore) -> None:
    """记录压缩事件 + 列表。"""
    from datetime import datetime

    store.create_session("s1")
    record = CompactionRecord(
        compaction_id="c1",
        session_id="s1",
        triggered_at=datetime.utcnow(),
        level=2,
        tokens_before=1000,
        tokens_after=500,
        identifier_preservation=False,
    )
    store.record_compaction(record)

    records = store.list_compaction_records("s1")
    assert len(records) == 1
    assert records[0].level == 2
    assert records[0].tokens_before == 1000
    assert records[0].tokens_after == 500


def test_load_empty_session(store: SessionStore) -> None:
    """加载空会话返回空列表。"""
    store.create_session("s1")
    assert store.load_messages("s1") == []


def test_close(store: SessionStore) -> None:
    """close 不抛异常。"""
    store.create_session("s1")
    store.close()
