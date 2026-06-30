"""M4 持久化层测试：tool_calls/tool_audit 表 + 落盘 + 预算降级。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from q_agent.orchestrator.persistence import SessionStore
from q_agent.tools.audit import args_hash, summarize, write_audit
from q_agent.tools.budget import apply_budget, summarize_placeholder, truncate
from q_agent.tools.results import cleanup_old, gen_call_id, placeholder, spill


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    """临时 SessionStore，测试后自动清理。"""
    s = SessionStore(tmp_path / "test.db")
    yield s
    s.close()


# ---------- persistence: tool_calls / tool_audit 表 ----------


def test_insert_and_load_tool_calls(store: SessionStore) -> None:
    """插入 tool_call 应能查回。"""
    store.create_session("sess1")
    store.insert_tool_call(
        call_id="call1",
        session_id="sess1",
        tool_name="file_read",
        status="success",
        started_at="2026-06-29T15:30:00",
        output_text="hello",
    )
    rows = store.load_tool_calls("sess1")
    assert len(rows) == 1
    assert rows[0]["call_id"] == "call1"
    assert rows[0]["tool_name"] == "file_read"
    assert rows[0]["status"] == "success"


def test_update_tool_call_output(store: SessionStore) -> None:
    """更新 output_text 应反映新内容（L1/L2 降级用）。"""
    store.create_session("sess1")
    store.insert_tool_call(
        call_id="call1",
        session_id="sess1",
        tool_name="file_read",
        status="success",
        started_at="2026-06-29T15:30:00",
        output_text="原始输出",
    )
    store.update_tool_call_output("call1", "[已落盘]")
    rows = store.load_tool_calls("sess1")
    assert rows[0]["output_text"] == "[已落盘]"


def test_insert_audit(store: SessionStore) -> None:
    """插入 audit 应成功（不抛异常即通过）。"""
    store.create_session("sess1")
    store.insert_tool_call(
        call_id="call1",
        session_id="sess1",
        tool_name="exec_shell",
        status="success",
        started_at="2026-06-29T15:30:00",
    )
    store.insert_audit(
        call_id="call1",
        tool_name="exec_shell",
        permission_level="destructive",
        args_hash="abc123",
        status="success",
        started_at="2026-06-29T15:30:00",
        approval_mode="once",
        input_summary="ls -la",
        output_summary="file1.txt",
    )
    # 查回验证（直接 SQL）
    rows = list(store._conn.execute("SELECT * FROM tool_audit WHERE call_id = ?", ("call1",)))
    assert len(rows) == 1
    assert rows[0]["approval_mode"] == "once"


# ---------- audit 辅助 ----------


def test_args_hash_stable() -> None:
    """相同参数应生成相同 hash。"""
    h1 = args_hash("file_read", ("/path",), {})
    h2 = args_hash("file_read", ("/path",), {})
    assert h1 == h2


def test_args_hash_differs() -> None:
    """不同参数应生成不同 hash。"""
    h1 = args_hash("file_read", ("/path1",), {})
    h2 = args_hash("file_read", ("/path2",), {})
    assert h1 != h2


def test_summarize_truncates() -> None:
    """summarize 应截断到 limit。"""
    assert summarize("x" * 300, limit=100) == "x" * 100
    assert summarize("short") == "short"


def test_write_audit_wraps_persistence(store: SessionStore) -> None:
    """write_audit 应正确写入 audit 表。"""
    store.create_session("sess1")
    store.insert_tool_call(
        call_id="call1",
        session_id="sess1",
        tool_name="file_write",
        status="success",
        started_at="2026-06-29T15:30:00",
    )
    write_audit(
        store=store,
        call_id="call1",
        tool_name="file_write",
        permission_level="write",
        args=("/path",),
        kwargs={},
        status="success",
        started_at="2026-06-29T15:30:00",
        input_text="new content",
        output_text="写入 10 bytes",
    )
    rows = list(store._conn.execute("SELECT * FROM tool_audit WHERE call_id = ?", ("call1",)))
    assert rows[0]["input_summary"] == "new content"
    assert rows[0]["output_summary"] == "写入 10 bytes"


# ---------- results：落盘 ----------


def test_gen_call_id_unique() -> None:
    """call_id 应唯一（12 位 hex）。"""
    ids = {gen_call_id() for _ in range(100)}
    assert len(ids) == 100


def test_spill_writes_txt_and_meta(tmp_path: Path, monkeypatch) -> None:
    """spill 应写 .txt + .meta.json。"""
    # 重定向 RESULTS_DIR 到 tmp_path 避免污染用户家目录
    from q_agent.tools import results as results_mod

    monkeypatch.setattr(results_mod, "RESULTS_DIR", tmp_path / "tool-results")
    path = spill(
        session_id="sess1",
        call_id="call1",
        tool_name="file_read",
        output="完整输出内容" * 100,
    )
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "完整输出内容" * 100
    meta_path = path.parent / "call1.meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["tool_name"] == "file_read"
    assert meta["call_id"] == "call1"


def test_placeholder_format(tmp_path: Path) -> None:
    """placeholder 应含工具名 + 路径。"""
    p = tmp_path / "out.txt"
    text = placeholder("file_read", "call1", p)
    assert "file_read" in text
    assert str(p) in text


def test_cleanup_old_removes_expired(tmp_path: Path, monkeypatch) -> None:
    """cleanup_old 应清理超过 max_age_days 的文件。"""
    from q_agent.tools import results as results_mod

    monkeypatch.setattr(results_mod, "RESULTS_DIR", tmp_path / "tool-results")
    # 落盘一个文件
    spill("sess1", "call1", "file_read", "x" * 3000)
    # 把 mtime 改成 40 天前
    import os
    import time as time_mod

    txt = tmp_path / "tool-results" / "sess1" / "call1.txt"
    old_time = time_mod.time() - 40 * 86400
    os.utime(txt, (old_time, old_time))
    count = cleanup_old(max_age_days=30)
    assert count >= 1
    assert not txt.exists()


# ---------- budget：三档降级 ----------


def test_apply_budget_short_text_returns_as_is() -> None:
    """短文本应原样返回（不落盘）。"""
    result = apply_budget("短文本", "file_read", "call1", "sess1")
    assert result == "短文本"


def test_apply_budget_long_text_spills(tmp_path: Path, monkeypatch) -> None:
    """长文本应落盘 + 返回占位符。"""
    from q_agent.tools import results as results_mod

    monkeypatch.setattr(results_mod, "RESULTS_DIR", tmp_path / "tool-results")
    long_text = "x" * 3000
    result = apply_budget(long_text, "file_read", "call1", "sess1", budget=2000)
    assert "已落盘" in result
    assert "file_read" in result


def test_truncate_keeps_head_and_tail() -> None:
    """truncate 应保留头尾 + 中间省略。"""
    text = "0123456789" * 50  # 500 字符
    result = truncate(text, head=100, tail=100)
    assert len(result) < len(text)
    assert "截断" in result
    assert result.startswith("0123456789" * 10)  # 前 100


def test_summarize_placeholder_truncates() -> None:
    """summarize_placeholder 应截断到 limit。"""
    text = "x" * 200
    result = summarize_placeholder(text, limit=100)
    assert len(result) <= 103  # 100 + "..."
    assert result.endswith("...")
