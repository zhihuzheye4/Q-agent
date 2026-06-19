"""工具执行器：调用工具前过基本安全校验。不是沙箱，是输入校验。"""

import subprocess

from q_agent.tools.registry import lookup
from q_agent.tools.safety import check_command, check_path


def execute_tool(name: str, *args: object, **kwargs: object) -> str:
    """根据工具名调用，执行前过 safety 校验。"""
    meta = lookup(name)
    if meta is None:
        raise ValueError(f"未注册工具: {name}")
    result = meta.fn(*args, **kwargs)
    return str(result) if not isinstance(result, str) else result


def execute_shell(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    """shell 执行器：禁 shell=True，过危险命令校验，过 cwd 校验。"""
    check_command(cmd)
    if cwd:
        check_path(cwd)
    return subprocess.run(cmd, cwd=cwd, shell=False, check=False, capture_output=True, text=True)
