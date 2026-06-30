"""工具调用层（替代沙箱）。让 LLM 发出的指令被软件理解并执行。

v0.0.19 扩展导出：lookup_spec / ToolSpec / ExternalToolSource / PermissionLevel
"""

# 触发 10 个内置工具的 @tool 注册（files/search/exec/web 各模块顶层 @tool 装饰器）
import q_agent.tools.exec  # noqa: F401
import q_agent.tools.files  # noqa: F401
import q_agent.tools.search  # noqa: F401
import q_agent.tools.web  # noqa: F401
from q_agent.tools.base import PermissionLevel, ToolMeta  # noqa: F401
from q_agent.tools.executor import execute_shell, execute_tool  # noqa: F401
from q_agent.tools.registry import all_tools, lookup, lookup_spec, tool  # noqa: F401
from q_agent.tools.spec import ExternalToolSource, ToolSpec  # noqa: F401
