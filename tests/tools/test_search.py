"""M3 search.py 2 工具测试：search_content / search_glob。"""

from __future__ import annotations

import json
from pathlib import Path

from q_agent.tools.search import search_content, search_glob


def test_search_content_happy(tmp_path: Path) -> None:
    """内容搜索应返回 path:line:matched。"""
    (tmp_path / "a.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def bar():\n    return 2\n", encoding="utf-8")
    result = search_content(str(tmp_path), r"return \d")
    assert "a.py:2:" in result
    assert "return 1" in result
    assert "b.py:2:" in result
    assert "return 2" in result


def test_search_content_no_match(tmp_path: Path) -> None:
    """无匹配应返回'无匹配'。"""
    (tmp_path / "a.py").write_text("print(1)", encoding="utf-8")
    assert search_content(str(tmp_path), "nonexistent_xyz") == "无匹配"


def test_search_content_max_results(tmp_path: Path) -> None:
    """超过 max_results 应截断。"""
    for i in range(10):
        (tmp_path / f"f{i}.py").write_text("target_line\n", encoding="utf-8")
    result = search_content(str(tmp_path), "target_line", max_results=3)
    assert "max_results=3" in result


def test_search_content_invalid_pattern(tmp_path: Path) -> None:
    """非法正则应返回 InvalidPattern。"""
    result = search_content(str(tmp_path), "[unclosed")
    assert json.loads(result)["error"] == "InvalidPattern"


def test_search_content_skip_large_files(tmp_path: Path) -> None:
    """超过 500KB 的文件应跳过。"""
    (tmp_path / "big.txt").write_text("x" * 600_000, encoding="utf-8")
    (tmp_path / "small.txt").write_text("target\n", encoding="utf-8")
    result = search_content(str(tmp_path), "target")
    assert "small.txt" in result
    assert "big.txt" not in result


def test_search_glob_happy(tmp_path: Path) -> None:
    """glob 模式应返回匹配文件路径。"""
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "b.py").write_text("x", encoding="utf-8")
    (tmp_path / "c.txt").write_text("x", encoding="utf-8")
    result = search_glob(str(tmp_path), "*.py")
    assert "a.py" in result
    assert "b.py" in result
    assert "c.txt" not in result


def test_search_glob_recursive(tmp_path: Path) -> None:
    """**/*.py 应递归匹配。"""
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "top.py").write_text("x", encoding="utf-8")
    (sub / "nested.py").write_text("x", encoding="utf-8")
    result = search_glob(str(tmp_path), "**/*.py")
    assert "top.py" in result
    assert "nested.py" in result


def test_search_glob_no_match(tmp_path: Path) -> None:
    """无匹配应返回'无匹配'。"""
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    assert search_glob(str(tmp_path), "*.py") == "无匹配"


def test_search_glob_not_a_directory(tmp_path: Path) -> None:
    """非目录应返回 NotADirectory。"""
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    result = search_glob(str(f), "*.py")
    assert json.loads(result)["error"] == "NotADirectory"
