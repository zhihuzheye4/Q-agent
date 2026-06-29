"""撤销栈：写前快照备份 + 内存撤销栈。

v0.0.19 简版：
- snapshot_before_write / snapshot_before_move 备份原文件到 ~/.q-agent/snapshots/{call_id}/
- 内存撤销栈（容量 20，最近 20 条）
- undo_last() 恢复最近一次操作

v0.0.20+ 候选扩展：
- git 兜底（如果项目是 git 仓库，调 git stash 临时存）
- 跨工具事务撤销
- 持久化撤销栈（重启不丢）
"""

import contextlib
import shutil
import uuid
from pathlib import Path

SNAPSHOT_DIR = Path.home() / ".q-agent" / "snapshots"
UNDO_STACK_CAPACITY = 20

# 内存撤销栈：最近 20 条 write/move 记录
_UNDO_STACK: list[dict[str, str | bool | None]] = []


def _gen_call_id() -> str:
    """生成 12 位 hex 调用 ID（用作快照目录名）。"""
    return uuid.uuid4().hex[:12]


def _push_undo(record: dict[str, str | bool | None]) -> None:
    """压入撤销栈，超过容量则丢弃最旧。"""
    _UNDO_STACK.append(record)
    if len(_UNDO_STACK) > UNDO_STACK_CAPACITY:
        _UNDO_STACK.pop(0)


def snapshot_before_write(path: str) -> str:
    """写前快照：备份原文件到 snapshots 目录，返回备份目录路径。

    若原文件不存在，记录"新建"标记但不备份（撤销时删除文件）。
    """
    call_id = _gen_call_id()
    src = Path(path).resolve()
    backup_dir = SNAPSHOT_DIR / call_id
    backup_dir.mkdir(parents=True, exist_ok=True)

    if src.exists():
        backup_path = backup_dir / src.name
        shutil.copy2(src, backup_path)
        record: dict[str, str | bool | None] = {
            "call_id": call_id,
            "op": "write",
            "path": str(src),
            "backup": str(backup_path),
            "existed": True,
        }
    else:
        record = {
            "call_id": call_id,
            "op": "write",
            "path": str(src),
            "backup": None,
            "existed": False,
        }

    _push_undo(record)
    return str(backup_dir) if src.exists() else f"(新建){call_id}"


def snapshot_before_move(src: str, dst: str) -> str:
    """移动前快照：备份原文件 + 记录原/目标位置。"""
    call_id = _gen_call_id()
    src_path = Path(src).resolve()
    dst_path = Path(dst).resolve()
    backup_dir = SNAPSHOT_DIR / call_id
    backup_dir.mkdir(parents=True, exist_ok=True)

    if src_path.exists():
        backup_path = backup_dir / src_path.name
        shutil.copy2(src_path, backup_path)
        record: dict[str, str | bool | None] = {
            "call_id": call_id,
            "op": "move",
            "src": str(src_path),
            "dst": str(dst_path),
            "backup": str(backup_path),
            "existed": True,
        }
    else:
        record = {
            "call_id": call_id,
            "op": "move",
            "src": str(src_path),
            "dst": str(dst_path),
            "backup": None,
            "existed": False,
        }

    _push_undo(record)
    return str(backup_dir)


def undo_last() -> dict[str, str | bool | None] | None:
    """撤销最近一次写/移动操作。

    write 撤销：若原文件存在则用备份覆盖；若原不存在则删除当前文件。
    move 撤销：从备份恢复到原位置 + 删除目标位置文件。
    """
    if not _UNDO_STACK:
        return None
    record = _UNDO_STACK.pop()
    op = record.get("op")

    if op == "write":
        path = str(record.get("path", ""))
        backup = record.get("backup")
        existed = record.get("existed")
        if existed and backup:
            shutil.copy2(str(backup), path)
        else:
            with contextlib.suppress(FileNotFoundError):
                Path(path).unlink()
    elif op == "move":
        src = str(record.get("src", ""))
        dst = str(record.get("dst", ""))
        backup = record.get("backup")
        if backup:
            shutil.copy2(str(backup), src)
            with contextlib.suppress(FileNotFoundError):
                Path(dst).unlink()

    return record


def undo_stack_size() -> int:
    """返回当前撤销栈大小（供测试 / UI 显示用）。"""
    return len(_UNDO_STACK)


def clear_undo_stack() -> None:
    """清空撤销栈（供测试隔离用）。"""
    _UNDO_STACK.clear()
