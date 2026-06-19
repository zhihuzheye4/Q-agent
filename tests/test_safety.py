"""基本安全校验测试（不是沙箱）。

覆盖三类用例：
1. 精确命中（happy-path 拦截）
2. 绕过路径（修复后应能拦截：多空格、子目录路径、等价 flag、通配根）
3. 误报排除（合法命令不应被拦：含 "format" 子串的单词等）
"""

import pytest

from q_agent.tools.safety import check_command, check_path

# ---------- 命令校验：精确命中 ----------


def test_danger_command_rejected() -> None:
    """危险命令应被拦截。"""
    with pytest.raises(PermissionError):
        check_command(["rm", "-rf", "/"])


def test_danger_command_str_input_rejected() -> None:
    """str 形式输入也应命中。"""
    with pytest.raises(PermissionError):
        check_command("rm -rf /")


# ---------- 命令校验：绕过路径（修复后应命中） ----------


def test_danger_command_multispace_rejected() -> None:
    """多空格不能绕过——str 输入按空白拆分。"""
    with pytest.raises(PermissionError):
        check_command("rm  -rf  /")


def test_danger_command_split_flags_rejected() -> None:
    """拆分等价 flag 不能绕过。"""
    with pytest.raises(PermissionError):
        check_command(["rm", "-r", "-f", "/"])


def test_danger_command_long_flags_rejected() -> None:
    """长形式 flag 不能绕过。"""
    with pytest.raises(PermissionError):
        check_command(["rm", "--recursive", "--force", "/"])


def test_danger_command_wildcard_root_rejected() -> None:
    """通配根 /* 应被拦截。"""
    with pytest.raises(PermissionError):
        check_command(["rm", "-rf", "/*"])


def test_danger_command_windows_format_rejected() -> None:
    """Windows format 单独出现应被拦截。"""
    with pytest.raises(PermissionError):
        check_command(["format"])


def test_danger_command_windows_del_rejected() -> None:
    """Windows del /s /q 应被拦截。"""
    with pytest.raises(PermissionError):
        check_command(["del", "/s", "/q"])


# ---------- 命令校验：误报排除（合法命令不应被拦） ----------


def test_safe_command_with_format_substring_not_rejected() -> None:
    """含 'format' 子串的合法命令不应被误拦。"""
    # 旧实现会因 'format' in 'information' 误报
    check_command(["information"])
    check_command(["reformat", "document.md"])
    check_command(["echo", "informational"])


def test_safe_command_not_rejected() -> None:
    """普通安全命令不拦截。"""
    check_command(["ls", "-la"])
    check_command(["echo", "hello"])
    check_command(["python", "-m", "q_agent", "version"])


# ---------- 路径校验：精确命中 ----------


def test_protected_path_rejected() -> None:
    """受保护根目录路径应被拦截。"""
    with pytest.raises(PermissionError):
        check_path("G:/agent")


def test_protected_path_backslash_rejected() -> None:
    """反斜杠形式也应命中。"""
    with pytest.raises(PermissionError):
        check_path(r"G:\agent")


# ---------- 路径校验：绕过路径（修复后应命中） ----------


def test_protected_path_subdir_rejected() -> None:
    """受保护根目录的子路径也应被拦截（前缀归属判断）。"""
    with pytest.raises(PermissionError):
        check_path("G:/agent/q_agent")
    with pytest.raises(PermissionError):
        check_path(r"G:\agent\some\deep\subdir")


def test_protected_path_relative_to_cwd_rejected(tmp_path) -> None:
    """当 cwd 在受保护根下时，相对子路径也应命中。"""
    # tmp_path 本身作为 cwd 时不命中，因为 cwd 不在 PROTECTED_ROOTS 内
    # 但传 "G:/agent/任意子路径" 必命中
    with pytest.raises(PermissionError):
        check_path("G:/agent/.git/config")
