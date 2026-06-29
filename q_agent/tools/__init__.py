"""工具调用层（替代沙箱）。让 LLM 发出的指令被软件理解并执行。

v0.0.19 扩展导出：lookup_spec / ToolSpec / ExternalToolSource / PermissionLevel
"""

from q_agent.tools.base import PermissionLevel, ToolMeta  # noqa: F401
from q_agent.tools.executor import execute_shell, execute_tool  # noqa: F401
from q_agent.tools.registry import all_tools, lookup, lookup_spec, tool  # noqa: F401
from q_agent.tools.spec import ExternalToolSource, ToolSpec  # noqa: F401
