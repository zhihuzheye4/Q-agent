"""M7 撤销栈测试：snapshot_before_write / snapshot_before_move / undo_last。

覆盖：
- snapshot_before_write 既有文件备份
- snapshot_before_write 新建文件不备份但记录"新建"
- snapshot_before_move 备份原文件 + 记录原/目标位置
- undo_last write 撤销（用备份覆盖）
- undo_last write 新建撤销（删除文件）
- undo_last move 撤销（恢复到原位置 + 删目标）
- 撤销栈空时 undo_last 返回 None
- 撤销栈容量上限 20（超出丢最旧）
"""

from __future__ import annotations

from pathlib import Path

from q_agent.tools.undo import (
    UNDO_STACK_CAPACITY,
    clear_undo_stack,
    snapshot_before_move,
    snapshot_before_write,
    undo_last,
    undo_stack_size,
)


def test_snapshot_write_existing_file(tmp_path: Path) -> None:
    """写前快照：既有文件应备份到 snapshots 目录。"""
    clear_undo_stack()
    f = tmp_path / "orig.txt"
    f.write_text("原内容", encoding="utf-8")

    backup_dir = snapshot_before_write(str(f))
    assert "snapshots" in backup_dir
    assert undo_stack_size() == 1


def test_snapshot_write_new_file(tmp_path: Path) -> None:
    """写前快照：新建文件不备份但记录"新建"标记。"""
    clear_undo_stack()
    f = tmp_path / "new.txt"
    # 文件不存在
    backup = snapshot_before_write(str(f))
    assert "新建" in backup
    assert undo_stack_size() == 1


def test_snapshot_move_existing_file(tmp_path: Path) -> None:
    """移动前快照：备份原文件 + 记录原/目标位置。"""
    clear_undo_stack()
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("待移动", encoding="utf-8")

    backup_dir = snapshot_before_move(str(src), str(dst))
    assert "snapshots" in backup_dir
    assert undo_stack_size() == 1


def test_undo_write_existing_file(tmp_path: Path) -> None:
    """write 撤销：既有文件应用备份覆盖回原内容。"""
    clear_undo_stack()
    f = tmp_path / "a.txt"
    f.write_text("原内容", encoding="utf-8")
    snapshot_before_write(str(f))
    # 模拟写入新内容
    f.write_text("新内容", encoding="utf-8")
    assert f.read_text(encoding="utf-8") == "新内容"

    record = undo_last()
    assert record is not None
    assert record["op"] == "write"
    # 撤销后应恢复原内容
    assert f.read_text(encoding="utf-8") == "原内容"
    assert undo_stack_size() == 0


def test_undo_write_new_file(tmp_path: Path) -> None:
    """write 撤销：新建文件应删除当前文件。"""
    clear_undo_stack()
    f = tmp_path / "newfile.txt"
    snapshot_before_write(str(f))  # 原不存在
    # 模拟创建新文件
    f.write_text("新建内容", encoding="utf-8")
    assert f.exists()

    undo_last()
    assert not f.exists()


def test_undo_move_existing_file(tmp_path: Path) -> None:
    """move 撤销：从备份恢复到原位置 + 删除目标位置。"""
    clear_undo_stack()
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("待移动内容", encoding="utf-8")
    snapshot_before_move(str(src), str(dst))
    # 模拟移动：删源 + 写目标
    src.unlink()
    dst.write_text("待移动内容", encoding="utf-8")
    assert not src.exists()
    assert dst.exists()

    undo_last()
    assert src.exists()
    assert src.read_text(encoding="utf-8") == "待移动内容"
    assert not dst.exists()


def test_undo_empty_stack_returns_none() -> None:
    """撤销栈空时 undo_last 应返回 None。"""
    clear_undo_stack()
    assert undo_last() is None


def test_undo_stack_capacity_limit(tmp_path: Path) -> None:
    """撤销栈超过容量 20 应丢弃最旧。"""
    clear_undo_stack()
    for i in range(UNDO_STACK_CAPACITY + 5):
        f = tmp_path / f"f{i}.txt"
        f.write_text(f"内容{i}", encoding="utf-8")
        snapshot_before_write(str(f))

    assert undo_stack_size() == UNDO_STACK_CAPACITY  # 不超过容量