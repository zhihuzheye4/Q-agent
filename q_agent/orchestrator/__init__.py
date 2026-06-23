"""编排层：意图识别 → 技能/工具选择 → 执行调度。

v0.0.18 起新增 2000+ 轮设计版编排层（7 模块）：
    types.py           数据类型（Role/Message/ToolCall/TurnState/SessionData/CompactionRecord）
    turn.py            单轮 turn 状态机
    dispatcher.py      LLM 输出解析 + 工具调用调度
    context.py         4 级压缩 + 标识符保留
    persistence.py     sqlite3 持久化层
    summary_worker.py  SummaryWorker(QThread) 异步真摘要
    loop.py            Orchestrator 主循环（2000+ 轮设计版，含压缩触发 + 异步摘要合流）

v0.0.1 旧编排层（core.py + planner.py）保留为 LegacyOrchestrator，
供 cli.py / test_smoke.py 等既有代码使用，永不动。
新代码应使用 loop.py 的 Orchestrator。
"""

# v0.0.18 新编排层（主推）
from q_agent.orchestrator.context import ContextConfig, ContextManager  # noqa: F401

# v0.0.1 旧编排层（向后兼容，既有模块永不动）
from q_agent.orchestrator.core import Orchestrator as LegacyOrchestrator  # noqa: F401
from q_agent.orchestrator.dispatcher import (  # noqa: F401
    ParsedResponse,
    execute_tool_calls,
    parse_response,
    synthetic_assistant_message,
    tool_results_to_messages,
    tool_signature,
)
from q_agent.orchestrator.loop import Orchestrator  # noqa: F401
from q_agent.orchestrator.persistence import SessionStore  # noqa: F401
from q_agent.orchestrator.planner import Planner  # noqa: F401
from q_agent.orchestrator.summary_worker import SummaryWorker  # noqa: F401
from q_agent.orchestrator.turn import Turn  # noqa: F401
from q_agent.orchestrator.types import (  # noqa: F401
    CompactionRecord,
    Message,
    Role,
    SessionData,
    TerminationReason,
    ToolCall,
    ToolResult,
    TurnResult,
    TurnState,
)
