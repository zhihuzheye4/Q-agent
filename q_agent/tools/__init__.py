"""工具调用层（替代沙箱）。让 LLM 发出的指令被软件理解并执行。"""

from q_agent.tools.executor import execute_shell, execute_tool  # noqa: F401
from q_agent.tools.registry import all_tools, lookup, tool  # noqa: F401
