"""M3 files.py 5 工具测试：file_read / file_write / file_edit / file_list_dir / file_move。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from q_agent.tools.files import file_edit, file_list_dir, file_move, file_read, file_write
from q_agent.tools.undo import clear_undo_stack


@pytest.fixture(autouse=True)
def _clear_undo():
    """每条测试前清空撤销栈，避免互相污染。"""
    clear_undo_stack()


# ---------- file_read ----------


def test_file_read_happy(tmp_path: Path) -> None:
    """读小文件应返回内容。"""
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    assert file_read(str(f)) == "hello world"


def test_file_read_utf8_chinese(tmp_path: Path) -> None:
    """读中文 UTF-8 应正常。"""
    f = tmp_path / "zh.txt"
    f.write_text("你好，世界", encoding="utf-8")
    assert file_read(str(f)) == "你好，世界"


def test_file_read_empty_file(tmp_path: Path) -> None:
    """读空文件应返回空字符串。"""
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    assert file_read(str(f)) == ""


def test_file_read_not_found(tmp_path: Path) -> None:
    """读不存在文件应返回 FileNotFound 错误 JSON。"""
    result = file_read(str(tmp_path / "nonexistent.txt"))
    data = json.loads(result)
    assert data["error"] == "FileNotFound"
    assert data["recoverable"] is True


def test_file_read_too_large(tmp_path: Path) -> None:
    """读超过 1MB 文件应返回 FileTooLarge。"""
    f = tmp_path / "big.txt"
    f.write_text("x" * 1_100_000, encoding="utf-8")
    result = file_read(str(f))
    data = json.loads(result)
    assert data["error"] == "FileTooLarge"


def test_file_read_sensitive_rejected(tmp_path: Path) -> None:
    """读 .env 文件应被 sensitive 拦截。"""
    f = tmp_path / ".env"
    f.write_text("SECRET=xxx", encoding="utf-8")
    with pytest.raises(PermissionError, match="敏感文件"):
        file_read(str(f))


# ---------- file_write ----------


def test_file_write_create_new(tmp_path: Path) -> None:
    """写新文件应创建并返回字节数。"""
    f = tmp_path / "new.txt"
    result = file_write(str(f), "hello")
    assert "写入 5 bytes" in result
    assert f.read_text(encoding="utf-8") == "hello"


def test_file_write_overwrite_existing(tmp_path: Path) -> None:
    """覆盖既有文件应保留备份。"""
    f = tmp_path / "exist.txt"
    f.write_text("原内容", encoding="utf-8")
    result = file_write(str(f), "新内容")
    assert "backup" in result
    assert f.read_text(encoding="utf-8") == "新内容"


def test_file_write_chinese(tmp_path: Path) -> None:
    """写中文应正确。"""
    f = tmp_path / "zh.txt"
    file_write(str(f), "你好")
    assert f.read_text(encoding="utf-8") == "你好"


def test_file_write_secret_content_rejected(tmp_path: Path) -> None:
    """写入含 PEM 私钥的内容应被嗅探拦截。"""
    f = tmp_path / "leak.txt"
    content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAI...\n-----END RSA PRIVATE KEY-----"
    with pytest.raises(PermissionError, match="私密凭证"):
        file_write(str(f), content)


def test_file_write_sensitive_path_rejected(tmp_path: Path) -> None:
    """写到 .pem 文件应被 sensitive 拦截。"""
    f = tmp_path / "server.pem"
    with pytest.raises(PermissionError, match="敏感文件"):
        file_write(str(f), "fake cert")


# ---------- file_edit ----------


def test_file_edit_happy(tmp_path: Path) -> None:
    """精确替换应成功。"""
    f = tmp_path / "code.py"
    f.write_text("def foo():\n    return 1\n", encoding="utf-8")
    result = file_edit(str(f), "return 1", "return 2")
    assert "替换 1 处" in result
    assert "hit_line=2" in result
    assert f.read_text(encoding="utf-8") == "def foo():\n    return 2\n"


def test_file_edit_empty_old_string_rejected(tmp_path: Path) -> None:
    """old_string 为空应返回 EmptyOldString。"""
    f = tmp_path / "a.txt"
    f.write_text("内容", encoding="utf-8")
    result = file_edit(str(f), "", "new")
    assert json.loads(result)["error"] == "EmptyOldString"


def test_file_edit_noop_rejected(tmp_path: Path) -> None:
    """old_string 与 new_string 相同应返回 NoOp。"""
    f = tmp_path / "a.txt"
    f.write_text("内容", encoding="utf-8")
    result = file_edit(str(f), "内容", "内容")
    assert json.loads(result)["error"] == "NoOp"


def test_file_edit_string_not_found(tmp_path: Path) -> None:
    """old_string 不在文件中应返回 StringNotFound。"""
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    result = file_edit(str(f), "goodbye", "hi")
    assert json.loads(result)["error"] == "StringNotFound"


def test_file_edit_ambiguous_match(tmp_path: Path) -> None:
    """old_string 多次出现应返回 AmbiguousMatch。"""
    f = tmp_path / "a.txt"
    f.write_text("foo foo foo", encoding="utf-8")
    result = file_edit(str(f), "foo", "bar")
    data = json.loads(result)
    assert data["error"] == "AmbiguousMatch"
    assert "3 次" in data["message"]
    # 文件内容应未被修改
    assert f.read_text(encoding="utf-8") == "foo foo foo"


def test_file_edit_file_not_found(tmp_path: Path) -> None:
    """编辑不存在的文件应返回 FileNotFound。"""
    result = file_edit(str(tmp_path / "no.txt"), "a", "b")
    assert json.loads(result)["error"] == "FileNotFound"


def test_file_edit_secret_in_new_string_rejected(tmp_path: Path) -> None:
    """new_string 含私密凭证应被嗅探拦截。"""
    f = tmp_path / "a.txt"
    f.write_text("placeholder", encoding="utf-8")
    with pytest.raises(PermissionError, match="私密凭证"):
        file_edit(str(f), "placeholder", "AKIAIOSFODNN7EXAMPLE")


# ---------- file_list_dir ----------


def test_file_list_dir_happy(tmp_path: Path) -> None:
    """列目录应返回文件 + 目录（目录后缀 /）。"""
    (tmp_path / "file1.txt").write_text("x", encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    result = file_list_dir(str(tmp_path))
    lines = result.split("\n")
    assert "file1.txt" in lines
    assert "subdir/" in lines


def test_file_list_dir_empty(tmp_path: Path) -> None:
    """列空目录应返回空字符串。"""
    assert file_list_dir(str(tmp_path)) == ""


def test_file_list_dir_not_a_directory(tmp_path: Path) -> None:
    """列非目录应返回 NotADirectory。"""
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    result = file_list_dir(str(f))
    assert json.loads(result)["error"] == "NotADirectory"


# ---------- file_move ----------


def test_file_move_happy(tmp_path: Path) -> None:
    """移动文件应成功 + 备份。"""
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("待移动", encoding="utf-8")
    result = file_move(str(src), str(dst))
    assert "moved" in result
    assert "backup" in result
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "待移动"


def test_file_move_rename_in_same_dir(tmp_path: Path) -> None:
    """同目录改名应成功。"""
    src = tmp_path / "old.txt"
    dst = tmp_path / "new.txt"
    src.write_text("改名", encoding="utf-8")
    file_move(str(src), str(dst))
    assert not src.exists()
    assert dst.exists()


def test_file_move_src_not_found(tmp_path: Path) -> None:
    """移动不存在的源应返回 FileNotFound。"""
    result = file_move(str(tmp_path / "no.txt"), str(tmp_path / "dst.txt"))
    assert json.loads(result)["error"] == "FileNotFound"


def test_file_move_sensitive_rejected(tmp_path: Path) -> None:
    """移动 .env 文件应被 sensitive 拦截。"""
    src = tmp_path / ".env"
    src.write_text("SECRET=xxx", encoding="utf-8")
    with pytest.raises(PermissionError, match="敏感文件"):
        file_move(str(src), str(tmp_path / "dst"))
