"""M3 exec.py 测试：exec_shell + 危险命令拦截。"""

from __future__ import annotations

import pytest

from q_agent.tools.exec import exec_shell


def test_exec_shell_echo() -> None:
    """echo 命令应返回 stdout。"""
    result = exec_shell(["python", "-c", "print('hello')"])
    assert "returncode=0" in result
    assert "hello" in result


def test_exec_shell_returncode_nonzero() -> None:
    """失败命令应返回非零 returncode。"""
    result = exec_shell(["python", "-c", "import sys; sys.exit(3)"])
    assert "returncode=3" in result


def test_exec_shell_danger_command_rejected() -> None:
    """危险命令 rm -rf / 应被拦截。"""
    with pytest.raises(PermissionError, match="危险命令"):
        exec_shell(["rm", "-rf", "/"])


def test_exec_shell_format_command_rejected() -> None:
    """format 命令应被拦截。"""
    with pytest.raises(PermissionError, match="危险命令"):
        exec_shell(["format", "C:"])


def test_exec_shell_truncates_long_output() -> None:
    """超长 stdout 应被截断到 2000 字符。"""
    result = exec_shell(["python", "-c", "print('x' * 5000)"])
    # stdout 部分不超过 2000 字符（不含 returncode/stderr 标签）
    stdout_part = result.split("stdout:\n")[1].split("\nstderr:")[0]
    assert len(stdout_part) <= 2000


def test_exec_shell_with_cwd(tmp_path) -> None:
    """带 cwd 应在指定目录执行。"""
    result = exec_shell(["python", "-c", "import os; print(os.getcwd())"], cwd=str(tmp_path))
    assert str(tmp_path) in result


def test_exec_shell_cwd_protected_root_rejected() -> None:
    """cwd 为受保护根 G:\\agent 应被拦截。"""
    with pytest.raises(PermissionError, match="受保护根目录"):
        exec_shell(["python", "--version"], cwd=r"G:\agent")
