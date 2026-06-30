"""shell 执行工具：exec_shell。

destructive 权限 + needs_confirmation=True（每次都问，永不缓存）。
long_running=True 时 timeout 提升到 600s。
"""

import subprocess

from q_agent.tools.registry import tool
from q_agent.tools.safety import check_command, check_path


@tool(
    name="exec_shell",
    desc=(
        "执行 shell 命令（非交互、捕获 stdout/stderr）。"
        "何时用：运行测试、跑构建、查 git 状态、装依赖（在用户授权后）。"
        "何时不用：长时间运行的服务进程、需要交互输入的命令、批量删除（危险）。"
        "参数约束：cmd 为 list[str] 禁 shell=True；cwd 可选；long_running=True 时超时 600s。"
        "返回格式：returncode + stdout（前 2000 字符）+ stderr（前 500 字符）。"
    ),
    version="1.0.0",
    timeout=120.0,
    long_running=False,
    permission_level="destructive",
    needs_confirmation=True,
)
def exec_shell(cmd: list[str], cwd: str | None = None, long_running: bool = False) -> str:
    check_command(cmd)
    if cwd:
        check_path(cwd)
    timeout = 600.0 if long_running else 120.0
    cp = subprocess.run(
        cmd,
        cwd=cwd,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (cp.stdout or "")[:2000]
    err = (cp.stderr or "")[:500]
    return f"returncode={cp.returncode}\nstdout:\n{out}\nstderr:\n{err}"
