"""编排层数据类型（v0.0.18 2000+ 轮设计版）。

纯数据定义，无逻辑。仅依赖 Python 标准库（dataclass + enum + datetime）。

设计要点：
- Message 统一 LLM 输入输出与历史持久化的消息结构
- TurnState 每轮整体覆写，防跨迭代状态泄漏
- SessionData 会话元数据，>2000 轮可归档
- CompactionRecord 4 级压缩记录，供回溯与调试
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Role(str, Enum):
    """消息角色。str Enum 便于 JSON 序列化与 sqlite3 存储。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """工具调用意图（来自 LLM 输出的 tool_use 块）。

    id: LLM 返回的调用 ID（如 "call_abc123"），回喂 tool_result 时需对应
    name: 工具名（注册表中的 name）
    arguments: 工具参数（LLM 输出的 JSON dict）
    """

    id: str
    name: str
    arguments: dict[str, object]


@dataclass
class ToolResult:
    """工具执行结果（回喂给 LLM 作为 tool_result 块）。

    call_id: 对应的 ToolCall.id
    content: 工具输出文本（>2000 字符时会被第 1 级压缩落盘 + 占位替换）
    error: 执行失败时的错误信息，None 表示成功
    """

    call_id: str
    content: str = ""
    error: str | None = None


@dataclass
class Message:
    """统一消息结构（送入 LLM 和存入历史）。

    id: sqlite3 主键（UUID），持久化前为 None
    session_id: 所属会话 ID
    role: 消息角色
    content: 文本内容
    tool_calls: assistant 触发的工具调用列表（仅 role=ASSISTANT 时有）
    tool_call_id: role=TOOL 时对应的 ToolCall.id（让 LLM 知道这是哪个工具的结果）
    is_synthetic: True 表示合成消息（错误时产出，非 LLM 真实输出）
    is_compacted: True 表示已被压缩（原文被摘要替换）
    created_at: 持久化时间戳
    """

    id: str | None = None
    session_id: str | None = None
    role: Role = Role.USER
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    is_synthetic: bool = False
    is_compacted: bool = False
    created_at: datetime | None = None


class TerminationReason(str, Enum):
    """循环终止原因。"""

    LLM_STOPPED = "llm_stopped"  # LLM 自然停止（无 tool_calls）
    USER_CANCEL = "user_cancel"  # 用户主动取消
    MAX_STEPS_REACHED = "max_steps_reached"  # 达到最大步数软截止
    CONSECUTIVE_ERRORS = "consecutive_errors"  # 连续错误超阈值
    CONTEXT_OVERFLOW = "context_overflow"  # 第 4 级硬溢出
    DOOM_LOOP = "doom_loop"  # 检测到死循环
    LLM_FAILED = "llm_failed"  # LLM 调用本身失败


@dataclass
class TurnState:
    """单轮状态（每轮迭代结束整体覆写，防跨迭代泄漏）。

    messages: 当前上下文消息列表
    session_id: 当前会话 ID
    steps: 已执行步数
    consecutive_errors: 连续错误计数
    last_tool_signature: 上次工具调用签名 (name, args_hash)，用于 doom_loop 检测
    doom_loop_count: 重复工具调用计数
    terminated: 是否已终止
    termination_reason: 终止原因
    """

    messages: list[Message]
    session_id: str
    steps: int = 0
    consecutive_errors: int = 0
    last_tool_signature: tuple[str, str] | None = None
    doom_loop_count: int = 0
    terminated: bool = False
    termination_reason: TerminationReason | None = None


@dataclass
class TurnResult:
    """单轮 run_turn 返回结果。"""

    messages: list[Message]
    final_assistant_text: str
    termination_reason: TerminationReason
    steps_executed: int
    tool_calls_made: list[ToolCall]


@dataclass
class SessionData:
    """会话元数据（持久化到 sqlite3 sessions 表）。

    session_id: 会话 ID（UUID）
    created_at: 创建时间
    last_active_at: 最后活跃时间
    message_count: 消息总数
    is_archived: 是否已归档（>2000 轮的旧会话）
    summary_model: 本会话用的摘要模型名
    """

    session_id: str
    created_at: datetime
    last_active_at: datetime
    message_count: int = 0
    is_archived: bool = False
    summary_model: str | None = None


@dataclass
class CompactionRecord:
    """压缩记录（持久化到 sqlite3 compaction_records 表供回溯）。

    compaction_id: 压缩事件 ID（UUID）
    session_id: 所属会话 ID
    triggered_at: 触发时间
    level: 1=工具结果预算 2=旧消息截断 3=异步真摘要 4=硬溢出终止
    tokens_before: 压缩前 token 数
    tokens_after: 压缩后 token 数
    summary_model: 第 3 级时记录摘要模型名
    identifier_preservation: 是否启用标识符保留指令
    """

    compaction_id: str
    session_id: str
    triggered_at: datetime
    level: int
    tokens_before: int
    tokens_after: int
    summary_model: str | None = None
    identifier_preservation: bool = False
