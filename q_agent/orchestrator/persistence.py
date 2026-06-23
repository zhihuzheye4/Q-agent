"""sqlite3 持久化层（零第三方依赖，Python 标准库 sqlite3）。

v0.0.18 2000+ 轮设计：消息历史 + 会话元数据 + 压缩记录全部落盘，
关闭重启可恢复，>2000 轮可归档。

三表 + 索引：
- sessions: 会话元数据
- messages: 消息历史（核心）
- compaction_records: 压缩记录

并发安全：sqlite3 连接 + threading.Lock 保护写操作。
2000+ 轮历史加载：load_messages(limit) 分页加载，只加载最近 N 轮到内存。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

from q_agent.orchestrator.types import (
    CompactionRecord,
    Message,
    Role,
    SessionData,
)


def _now_iso() -> str:
    """当前 UTC 时间 ISO 字符串（sqlite3 存储）。"""
    return datetime.utcnow().isoformat(timespec="seconds")


def _parse_iso(s: str) -> datetime:
    """解析 ISO 时间字符串。"""
    return datetime.fromisoformat(s)


def _uuid() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


class SessionStore:
    """sqlite3 持久化层。

    所有写操作加 threading.Lock 保护（主循环 + SummaryWorker 可能同时写）。
    消息历史支持分页加载，避免 2000+ 轮撑爆内存。
    """

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        last_active_at TEXT NOT NULL,
        message_count INTEGER NOT NULL DEFAULT 0,
        is_archived INTEGER NOT NULL DEFAULT 0,
        summary_model TEXT
    );

    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        tool_calls_json TEXT,
        tool_call_id TEXT,
        is_synthetic INTEGER NOT NULL DEFAULT 0,
        is_compacted INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );

    CREATE TABLE IF NOT EXISTS compaction_records (
        compaction_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        triggered_at TEXT NOT NULL,
        level INTEGER NOT NULL,
        tokens_before INTEGER NOT NULL,
        tokens_after INTEGER NOT NULL,
        summary_model TEXT,
        identifier_preservation INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );

    CREATE INDEX IF NOT EXISTS idx_messages_session_created
        ON messages(session_id, created_at);

    CREATE INDEX IF NOT EXISTS idx_compaction_records_session
        ON compaction_records(session_id, triggered_at);
    """

    def __init__(self, db_path: Path) -> None:
        """初始化 sqlite3 连接 + 建表。

        db_path 默认应传 q_agent/data/sessions.db。
        父目录不存在则创建。
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """建表 + 建索引（IF NOT EXISTS 幂等）。"""
        with self._lock:
            self._conn.executescript(self.SCHEMA_SQL)
            self._conn.commit()

    def close(self) -> None:
        """关闭连接。"""
        with self._lock:
            self._conn.close()

    # ---- 会话表 CRUD ----

    def create_session(self, session_id: str, summary_model: str | None = None) -> SessionData:
        """创建新会话。已存在则抛 ValueError。"""
        now = datetime.utcnow()
        now_iso = _now_iso()
        data = SessionData(
            session_id=session_id,
            created_at=now,
            last_active_at=now,
            message_count=0,
            is_archived=False,
            summary_model=summary_model,
        )
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO sessions (session_id, created_at, last_active_at, "
                    "message_count, is_archived, summary_model) VALUES (?, ?, ?, 0, 0, ?)",
                    (session_id, now_iso, now_iso, summary_model),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as e:
                raise ValueError(f"会话已存在: {session_id}") from e
        return data

    def load_session(self, session_id: str) -> SessionData | None:
        """加载会话元数据。不存在返回 None。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT session_id, created_at, last_active_at, message_count, "
                "is_archived, summary_model FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return SessionData(
            session_id=row["session_id"],
            created_at=_parse_iso(row["created_at"]),
            last_active_at=_parse_iso(row["last_active_at"]),
            message_count=row["message_count"],
            is_archived=bool(row["is_archived"]),
            summary_model=row["summary_model"],
        )

    def update_session_active(self, session_id: str, message_count_delta: int) -> None:
        """更新会话最后活跃时间 + 消息计数增量。"""
        now_iso = _now_iso()
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET last_active_at = ?, "
                "message_count = message_count + ? WHERE session_id = ?",
                (now_iso, message_count_delta, session_id),
            )
            self._conn.commit()

    def archive_session(self, session_id: str) -> None:
        """归档会话（is_archived=1，不删数据）。"""
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET is_archived = 1 WHERE session_id = ?",
                (session_id,),
            )
            self._conn.commit()

    def list_sessions(self, include_archived: bool = False) -> list[SessionData]:
        """列出会话。include_archived=False 时排除归档会话。"""
        with self._lock:
            if include_archived:
                rows = self._conn.execute(
                    "SELECT session_id, created_at, last_active_at, message_count, "
                    "is_archived, summary_model FROM sessions ORDER BY last_active_at DESC"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT session_id, created_at, last_active_at, message_count, "
                    "is_archived, summary_model FROM sessions WHERE is_archived = 0 "
                    "ORDER BY last_active_at DESC"
                ).fetchall()
        return [
            SessionData(
                session_id=r["session_id"],
                created_at=_parse_iso(r["created_at"]),
                last_active_at=_parse_iso(r["last_active_at"]),
                message_count=r["message_count"],
                is_archived=bool(r["is_archived"]),
                summary_model=r["summary_model"],
            )
            for r in rows
        ]

    # ---- 消息表 CRUD ----

    def append_message(self, msg: Message) -> Message:
        """追加消息到 sqlite3。

        msg.id 为 None 时自动生成 UUID 并回填。
        msg.created_at 为 None 时自动填当前时间。
        返回回填后的 msg（dataclasses.replace）。
        """
        from dataclasses import replace

        if msg.id is None:
            msg = replace(msg, id=_uuid())
        if msg.created_at is None:
            msg = replace(msg, created_at=datetime.utcnow())

        # mypy 已知此时 created_at 不为 None（上面 replace 保证），但需显式断言
        assert msg.created_at is not None
        created_iso = msg.created_at.isoformat(timespec="seconds")

        tool_calls_json = (
            json.dumps(
                [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in msg.tool_calls
                ],
                ensure_ascii=False,
            )
            if msg.tool_calls
            else None
        )

        with self._lock:
            self._conn.execute(
                "INSERT INTO messages (id, session_id, role, content, tool_calls_json, "
                "tool_call_id, is_synthetic, is_compacted, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    msg.id,
                    msg.session_id,
                    msg.role.value,
                    msg.content,
                    tool_calls_json,
                    msg.tool_call_id,
                    int(msg.is_synthetic),
                    int(msg.is_compacted),
                    created_iso,
                ),
            )
            self._conn.execute(
                "UPDATE sessions SET last_active_at = ?, "
                "message_count = message_count + 1 WHERE session_id = ?",
                (created_iso, msg.session_id),
            )
            self._conn.commit()
        return msg

    def load_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[Message]:
        """加载会话消息历史，按插入顺序（rowid）正序。

        limit: 只加载最近 N 条（2000+ 轮场景分页加载）。None 表示全部加载。
        用 rowid 隐式列作 tiebreaker，避免同秒内消息 created_at 相同导致排序不稳定。
        子查询必须显式 SELECT rowid，否则外层 ORDER BY rowid 看不到该列。
        """
        with self._lock:
            if limit is None:
                rows = self._conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY rowid ASC",
                    (session_id,),
                ).fetchall()
            else:
                # 子查询显式带 rowid，外层按 rowid 正序排
                rows = self._conn.execute(
                    "SELECT id, session_id, role, content, tool_calls_json, "
                    "tool_call_id, is_synthetic, is_compacted, created_at FROM ("
                    "SELECT rowid, id, session_id, role, content, tool_calls_json, "
                    "tool_call_id, is_synthetic, is_compacted, created_at "
                    "FROM messages WHERE session_id = ? "
                    "ORDER BY rowid DESC LIMIT ?) ORDER BY rowid ASC",
                    (session_id, limit),
                ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def update_message_content(
        self,
        msg_id: str,
        new_content: str,
        is_compacted: bool = True,
    ) -> None:
        """更新消息内容（压缩后用摘要替换原文）。"""
        with self._lock:
            self._conn.execute(
                "UPDATE messages SET content = ?, is_compacted = ? WHERE id = ?",
                (new_content, int(is_compacted), msg_id),
            )
            self._conn.commit()

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        """sqlite3.Row 转 Message dataclass。"""
        from q_agent.orchestrator.types import ToolCall

        tool_calls_json = row["tool_calls_json"]
        tool_calls: list[ToolCall] = []
        if tool_calls_json:
            try:
                raw = json.loads(tool_calls_json)
                if isinstance(raw, list):
                    for item in raw:
                        if isinstance(item, dict):
                            tool_calls.append(
                                ToolCall(
                                    id=str(item.get("id", "")),
                                    name=str(item.get("name", "")),
                                    arguments=item.get("arguments", {}) or {},
                                )
                            )
            except (json.JSONDecodeError, TypeError):
                pass

        created_at_str = row["created_at"]
        return Message(
            id=row["id"],
            session_id=row["session_id"],
            role=Role(row["role"]),
            content=row["content"],
            tool_calls=tool_calls,
            tool_call_id=row["tool_call_id"],
            is_synthetic=bool(row["is_synthetic"]),
            is_compacted=bool(row["is_compacted"]),
            created_at=_parse_iso(created_at_str) if created_at_str else None,
        )

    # ---- 压缩记录表 ----

    def record_compaction(self, record: CompactionRecord) -> None:
        """记录压缩事件。"""
        with self._lock:
            self._conn.execute(
                "INSERT INTO compaction_records (compaction_id, session_id, triggered_at, "
                "level, tokens_before, tokens_after, summary_model, identifier_preservation) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.compaction_id,
                    record.session_id,
                    record.triggered_at.isoformat(timespec="seconds"),
                    record.level,
                    record.tokens_before,
                    record.tokens_after,
                    record.summary_model,
                    int(record.identifier_preservation),
                ),
            )
            self._conn.commit()

    def list_compaction_records(self, session_id: str) -> list[CompactionRecord]:
        """列出会话压缩记录（调试用）。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM compaction_records WHERE session_id = ? ORDER BY triggered_at ASC",
                (session_id,),
            ).fetchall()
        return [
            CompactionRecord(
                compaction_id=r["compaction_id"],
                session_id=r["session_id"],
                triggered_at=_parse_iso(r["triggered_at"]),
                level=r["level"],
                tokens_before=r["tokens_before"],
                tokens_after=r["tokens_after"],
                summary_model=r["summary_model"],
                identifier_preservation=bool(r["identifier_preservation"]),
            )
            for r in rows
        ]
