# Codex（openai/codex）编排调度层拆解报告

## 1. 项目概况

- 仓库：github.com/openai/codex
- 语言：Rust（约占 96%，另有少量 TUI/TypeScript 配套）
- 协议：Apache-2.0
- 定位：终端轻量 coding agent，CLI 形态，主打"对话 → 规划 → 工具调用"的本地闭环
- 架构风格：Cargo workspace 多 crate 拆分，核心逻辑全部异步（tokio + futures），强类型 trait 抽象，错误传播靠 `CodexErr` 枚举
- crate 划分（`codex-rs/Cargo.toml:1-504`）：
  - `core`：编排调度核心（turn loop / ToolOrchestrator / guardian / compact / session / agent 注册）
  - `protocol`：协议层（`protocol.rs` 定义 EventMsg、Op、RolloutItem、Approval、ToolName 等）
  - `sandboxing`：跨平台沙箱（seatbelt/landlock/bwrap/windows restricted token）
  - `execpolicy`：命令前缀规则策略解析与修订
  - `exec` / `exec-server`：独立可执行入口与远程执行服务器
  - `tools`：工具底层抽象（ToolSpec / ToolExecutor / ToolCall / dynamic_tool）
  - `state`：状态数据库（sqlite + migrations + log_db）
  - `thread-store`：线程存储（LiveThread / InMemory）
  - `rollout`：会话回放持久化（compression / recorder / state_db）
  - `agent-graph-store` / `agent-identity`：在 `Cargo.toml:5-6,140-141` 声明，但当前本地 clone 未包含源码，属外部 workspace crate
- 整体风格：编译期强约束 + 运行期最小反射；编排逻辑全部用 `trait` + `impl` 落地，避免动态字典传递

## 2. 编排调度层定位

`codex-rs/core/` 是整个项目的编排中枢，其他 crate 都是它的"供应商"：

- `protocol`：提供类型协议。`CodexErr`、`ResponseItem`、`TurnItem`、`EventMsg`、`AskForApproval`、`ReviewDecision` 全部在 `protocol/src/protocol.rs` 定义，core 只消费不定义
- `sandboxing`：core 通过 `codex_sandboxing::SandboxManager`（`core/src/tools/orchestrator.rs:40-41`）选择并转换沙箱类型；沙箱本身的平台实现（seatbelt/landlock/windows）完全封装在 sandboxing crate 内
- `execpolicy`：core 通过 `core/src/exec_policy.rs` 调用 execpolicy 解析器判断命令前缀是否被允许；`ExecPolicyAmendment` 由 protocol 定义，core 把"提议修订"传回 execpolicy
- `exec` / `exec-server`：core 的 `unified_exec` 模块通过 sandboxing transform 产出 `ExecRequest`，再交给 exec-server 或本地 PTY 执行
- `tools`：core 内部 `core/src/tools/registry.rs` 实现 `ToolRegistry`，把 `codex_tools::ToolSpec` 和 `ToolExecutor` 拼装成可调度单元
- `state` / `thread-store` / `rollout`：core 的 `Session`（`core/src/session/session.rs`）通过这些 crate 持久化对话、线程、rollout trace

core 自己内部又分两层：
- 顶层：`Session`（`session/session.rs`，1235 行）+ `SessionTask` trait（`tasks/mod.rs:214`），负责线程生命周期、任务调度、token 计量
- 编排层：`turn::run_turn`（`session/turn.rs:141`）+ `ToolOrchestrator`（`tools/orchestrator.rs:45`）+ `ToolRouter`（`tools/router.rs:35`），负责单次采样 + 工具调用循环

## 3. Planner 实现

Codex 不存在独立的 "Planner" 模块——"规划"职责被拆成两块：

**a. 协议层解析（LLM 输出 → 结构化意图）**

`core/src/tools/router.rs:113-160` 的 `ToolRouter::build_tool_call` 把 `ResponseItem::FunctionCall` / `ToolSearchCall` / `CustomToolCall` 三种 LLM 输出统一解析为 `ToolCall { tool_name, call_id, payload }`。这里 `ToolName::new(namespace, name)` 保留命名空间，`ToolPayload` 是枚举区分 Function/ToolSearch/Custom，避免用 `serde_json::Value` 一把抓。

`core/src/session/turn.rs:2018-2112` 的 `ResponseEvent::OutputItemDone` 分支是入口：流式响应每完成一个 item 就交给 `handle_output_item_done`（在 `stream_events_utils.rs`），后者调用 `build_tool_call` 决定是否产生 `tool_future` 推入 `in_flight` 队列。

**b. 计划模式（plan mode）**

`core/src/session/turn.rs:1374-1490` 的 `PlanModeStreamState` + `ProposedPlanItemState` 实现了独立的"计划流"：当 `collaboration_mode.mode == ModeKind::Plan` 时，模型输出的文本被 `AssistantTextStreamParser`（`codex-utils-stream-parser` crate）切成 `ProposedPlanSegment::Normal` / `ProposedPlanStart` / `ProposedPlanDelta` / `ProposedPlanEnd` 四种段，计划段走 `PlanDeltaEvent`，普通段走 `AgentMessageContentDeltaEvent`。这是一个**轻量 Planner**：把 LLM 文本流就地分成"计划"和"叙述"两条道，而不是把整段文本当 plan 交给后端解析。

**c. execpolicy 决策**

`core/src/exec_policy.rs` + `execpolicy/src/policy.rs` 负责把 shell 命令字符串解析为 `Decision::Allow` / `Decision::Deny` / `Decision::Ask`，这是"意图校验"而非"意图生成"——LLM 已经决定要跑某条命令，execpolicy 只判断是否需要进一步审批。

## 4. Orchestrator 实现

`core/src/tools/orchestrator.rs:45-605` 的 `ToolOrchestrator` 是 Codex 编排的真正核心。它是个泛型驱动器，签名是：

```rust
pub async fn run<Rq, Out, T>(
    &mut self, tool: &mut T, req: &Rq, tool_ctx: &ToolCtx,
    turn_ctx: &TurnContext, approval_policy: AskForApproval,
) -> Result<OrchestratorRunResult<Out>, ToolError>
where T: ToolRuntime<Rq, Out>
```

`ToolRuntime` trait（`core/src/tools/sandboxing.rs:394-409`）组合了 `Approvable` + `Sandboxable`，提供 `run` / `start_approval_async` / `network_approval_spec` / `sandbox_cwd` 等方法。`ShellRuntime`、`UnifiedExecRuntime`、`ApplyPatchRuntime` 都是它的实现。

**完整驱动流程**（`orchestrator.rs:134-508`）：

1. **审批决策（orchestrator.rs:151-221）**：先算 `ExecApprovalRequirement`（`sandboxing.rs:162-181`，三态 `Skip` / `NeedsApproval` / `Forbidden`）。`Skip` 且非严格自动审查时直接放行；`Forbidden` 直接返回 `ToolError::Rejected`；`NeedsApproval` 调 `request_approval`（orchestrator.rs:513-575），其中先跑 `run_permission_request_hooks`（hook 优先），hook 没决断再调 `tool.start_approval_async` 走 guardian 或用户
2. **沙箱选择（orchestrator.rs:223-250）**：`sandbox_override_for_first_attempt`（`sandboxing.rs:248-277`）决定首 attempt 是否跳沙箱；否则 `SandboxManager::should_sandbox` + `select_initial` 选 `SandboxType::MacosSeatbelt` / `LinuxSeccomp` / `WindowsRestrictedToken` / `None`
3. **首 attempt（orchestrator.rs:260-296）**：构造 `SandboxAttempt`，调 `run_attempt`（orchestrator.rs:61-132），其中先 `begin_network_approval`（网络审批和工具执行并行进行），再 `tool.run(req, &attempt, ctx)`，最后根据 `NetworkApprovalMode::Immediate` / `Deferred` 收尾
4. **拒绝时升级重试（orchestrator.rs:297-494）**：若首 attempt 返回 `CodexErr::Sandbox(SandboxErr::Denied { output, .. })`，且 `tool.escalate_on_failure()` 为 true 且策略允许跳沙箱，则构造 `retry_attempt` 用 `SandboxType::None` 重跑——**关键设计**：`should_bypass_approval`（`sandboxing.rs:336-343`）+ `already_approved` 让"已批准"的请求免二次审批，依靠 `ApprovalStore`（`sandboxing.rs:41-64`）缓存
5. **错误归类（orchestrator.rs:607-614）**：`sandbox_outcome_from_tool_error` 把 `Denied` / `Timeout` / `Signal` 映射成 otel 指标 tag

**turn loop 在哪里**：`core/src/session/turn.rs:141-454` 的 `run_turn` 函数。它是个外层 `loop`（turn.rs:214），每轮：
- 读 pending_input（用户在模型生成时新发的消息，turn.rs:218-222）
- 调 `run_sampling_request`（turn.rs:1107-1201）做一次完整 LLM 采样 + 工具并行执行
- 根据返回的 `SamplingRequestResult.needs_follow_up` + `token_limit_reached` 决定 continue / break / 触发 auto-compact

`run_sampling_request` 内部又有重试循环（turn.rs:1137-1200），处理 `is_retryable()` 的流式错误，靠 `handle_retryable_response_stream_error` 做指数退避。

## 5. 工具调用循环

完整路径（一次 `run_turn` 内的一次 `run_sampling_request`）：

1. **构造 prompt（turn.rs:245-251）**：`sess.clone_history().await.for_prompt(...)` 把会话历史按模型输入模态过滤成 `Vec<ResponseItem>`
2. **build_prompt（turn.rs:1079-1095）**：组装 `Prompt { input, tools: router.model_visible_specs(), parallel_tool_calls, base_instructions, output_schema }`，其中 `base_instructions` 来自 `sess.get_base_instructions()`
3. **stream 调用（turn.rs:1944-1957）**：`client_session.stream(prompt, &model_info, ...)` 返回 `ResponseEvent` 流
4. **流事件分发（turn.rs:2018-2370）**：`try_run_sampling_request` 的主 `loop`（turn.rs:1977）匹配 `ResponseEvent::Created` / `OutputItemAdded` / `OutputItemDone` / `OutputTextDelta` / `ToolCallInputDelta` / `ReasoningSummaryDelta` / `Completed` 等
5. **工具派发（turn.rs:2020-2112）**：`OutputItemDone` 分支调 `handle_output_item_done` → `ToolRouter::build_tool_call` → 产出 `tool_future`，推入 `in_flight: FuturesOrdered`（turn.rs:1958）
6. **并行执行（parallel.rs:62-133）**：`ToolCallRuntime::handle_tool_call_with_source` 用 `tokio::spawn` 派发；`supports_parallel` 决定用 `RwLock` read 还是 write 锁——非并行工具拿 write 锁阻塞其它，并行工具拿 read 锁共存
7. **取消传播（parallel.rs:135-180）**：`tokio::select!` 监听 `cancellation_token.cancelled()`，取消时若工具 `waits_for_runtime_cancellation` 则等它自己 teardown
8. **结果回喂（turn.rs:1884-1908）**：`drain_in_flight` 把每个工具的 `ResponseInputItem` 通过 `sess.record_conversation_items` 追加到历史，下一轮 `run_sampling_request` 的 `clone_history` 就能看到
9. **终止（turn.rs:2235-2262）**：`ResponseEvent::Completed` 分支处理 token usage，若 `end_turn == Some(false)` 则 `needs_follow_up = true`，外层 loop 继续

`run_turn` 外层 loop（turn.rs:214-451）的终止条件见第 8 节。

## 6. 上下文管理

**a. auto-compaction（90% 触发）**

触发判定在 `core/src/session/turn.rs:799-846` 的 `auto_compact_token_status`：

```rust
let token_limit_reached =
    auto_compact_scope_tokens >= auto_compact_scope_limit
    || full_context_window_limit_reached;
```

两个维度：
- `auto_compact_scope_tokens` vs `auto_compact_scope_limit`：作用域内 token（可选 `Total` 或 `BodyAfterPrefix`，由 `AutoCompactTokenLimitScope` 决定）超过配置限额
- `full_context_window_limit_reached`：active context tokens 超过模型 context window

`auto_compact_scope_limit` 来自 `model_info.auto_compact_token_limit()`（模型自带）或 `config.model_auto_compact_token_limit`，常见默认是 context window 的 90%。

**触发时机**（两处）：
- **pre-sampling**（turn.rs:849-877）：`run_pre_sampling_compact` 在 turn 开始前先检查，若超限就调 `run_auto_compact(..., CompactionPhase::PreTurn)`
- **mid-turn**（turn.rs:336-364）：采样完成后若 `token_limit_reached && needs_follow_up`，调 `run_auto_compact(..., CompactionPhase::MidTurn, InitialContextInjection::BeforeLastUserMessage)`

**compact 实现**（`core/src/compact.rs:131-343`）：
- 把 `SUMMARIZATION_PROMPT` + 历史喂给模型，drain_to_completed 拿到摘要
- `build_compacted_history`：清空历史，只保留 `user_messages` + `SUMMARY_PREFIX` + 摘要
- `advance_auto_compact_window`：开新 context window，老 window 落盘
- `InitialContextInjection::BeforeLastUserMessage`：mid-turn 时把 initial context 重新插到最后一条真实 user message 之前（为了训练时模型见过的格式）
- 替换 `sess.replace_compacted_history(...)`，recompute token usage

**b. 五层指令系统**

`core/src/session/mod.rs:3012-3010` 的 `build_initial_context` 是核心入口。它构造 `Vec<ResponseItem>` 注入到对话开头，分三类：
- `developer_sections`：聚合进一条 developer message
- `contextual_user_sections`：聚合进一条 contextual user message
- `separate_developer_sections`：独立 developer message（guardian policy 走这条）

注入顺序（按代码顺序）：
1. **base_instructions**（session.rs:583）：模型自带或 personality 烘焙的 system prompt，作为 `Prompt.base_instructions` 字段（turn.rs:1079-1095），不进 `build_initial_context`
2. **initial_context**（mod.rs:3012-3199）：包含 model_switch_instructions、permissions_instructions、developer_instructions、collaboration_mode_instructions、realtime_update、personality_spec_instructions、apps_instructions、available_skills_instructions、plugin_instructions、recommended_plugins_instructions 等
3. **skill injections**（turn.rs:599-614）：`build_skill_injections` 产出，作为 `ContextualUserFragment` 注入
4. **plugin injections**（turn.rs:622-624）：`build_plugin_injections`
5. **developer messages**（mod.rs:3000-3008）：聚合后的 developer message
6. **user messages**：用户原始输入

context_manager 模块（`core/src/context_manager/`）有 `history.rs` / `normalize.rs` / `updates.rs`，负责历史归一化和上下文更新，但不直接参与五层注入——注入由 `build_initial_context` 统一管理。

**c. message-history 角色**：Codex 没有 `message-history` crate。历史管理直接在 `Session::state.history`（`core/src/session/session.rs:70`）+ `state` crate 的 sqlite 落盘。`thread-store` crate 提供 `LiveThread`（`thread-store/src/live_thread.rs`）做线程级活跃会话存储。

## 7. 错误处理 & 降级

**a. sandbox denial → 升级 retry**

`orchestrator.rs:297-494`：首 attempt 拿到 `SandboxErr::Denied` 后：
- 检查 `tool.escalate_on_failure()`（默认 true，`sandboxing.rs:374-379`）
- 检查 `unsandboxed_execution_allowed`（无 denied-read 限制）
- 检查 `tool.wants_no_sandbox_approval(policy)`（`OnFailure` / `UnlessTrusted` 允许，`Never` / `OnRequest` 不允许）
- 若允许，构造 `SandboxType::None` 的 `retry_attempt` 再跑一次；二次审批靠 `should_bypass_approval(already_approved)` 跳过

**b. guardian 拒绝**

`guardian/mod.rs:47-58` 定义关键常量：
- `GUARDIAN_REVIEW_TIMEOUT: Duration = 90s`
- `MAX_CONSECUTIVE_GUARDIAN_DENIALS_PER_TURN: u32 = 3`
- `MAX_RECENT_AUTO_REVIEW_DENIALS_PER_TURN: u32 = 10`（50 窗口内）
- `AUTO_REVIEW_DENIAL_WINDOW_SIZE: usize = 50`

`GuardianRejectionCircuitBreaker`（mod.rs:78-134）：每次 guardian 否决记录 `record_denial`，连续 3 次或 50 窗口内 10 次否决就 `InterruptTurn`，发 `TurnAbortReason::Interrupted` 终止 turn。这是防"guardian vs agent 死循环"的熔断。

guardian 自己的失败模式（`guardian/review.rs:96-116`）：`PromptBuild` / `Session` / `Parse` / `Timeout` / `Cancelled`，全部"fail closed"——超时 90s 或解析失败都按否决处理，向 agent 返回 `GUARDIAN_TIMEOUT_INSTRUCTIONS`（review.rs:59-63）。

**c. 网络失败**

`run_attempt`（orchestrator.rs:61-132）中 `NetworkApprovalMode::Deferred` 若工具运行失败，调 `finish_deferred_network_approval` 收尾；流式采样错误走 `handle_retryable_response_stream_error`（turn.rs:1189-1198）做指数退避，`max_retries` 来自 `provider.info().stream_max_retries()`。

**d. 工具失败**

`parallel.rs:62-79`：`handle_tool_call` 把 `FunctionCallError::Fatal(message)` 升级为 `CodexErr::Fatal`，其它 `FunctionCallError` 转为 `failure_response`（不中断 turn，让模型看到失败信息自己决定下一步）。`drain_in_flight`（turn.rs:1884-1908）遇到 err 用 `error_or_panic` 记录但继续 drain。

**e. context window exceeded**

`run_sampling_request`（turn.rs:1167-1170）：`CodexErr::ContextWindowExceeded` 直接 `sess.set_total_tokens_full` 并向上抛错，由 `run_turn` 外层 loop 触发 auto-compact 后 continue 重试。

## 8. 循环终止条件

`run_turn` 外层 loop（turn.rs:214-451）的退出条件：

- **正常结束**（turn.rs:366-410）：`!needs_follow_up`（模型不再要工具调用 + 无 pending input）→ 进入 `run_turn_stop_hooks`，若 `stop_outcome.should_stop` 为 true 就 `break`
- **stop hook 阻塞续跑**（turn.rs:375-395）：`should_block` 时把 `continuation_fragments` 转成 hook prompt message 追加到历史，`stop_hook_active = true; continue`
- **TurnAborted**（turn.rs:413-415）：cancellation_token 被取消，直接返回 `Err(CodexErr::TurnAborted)`
- **InvalidImageRequest**（turn.ts:416-438）：替换历史中无效图片，发错误事件，`break`
- **其它错误**（turn.rs:439-449）：发 ErrorEvent，`break`（让用户继续对话）
- **auto-compact 后续跑**（turn.rs:336-364）：`token_limit_reached && needs_follow_up` 时 compact 然后 `continue`
- **新 context window**（turn.rs:327-334）：`maybe_start_new_context_window` 返回 Some 且 `needs_follow_up`，`continue`

`run_sampling_request` 内层 loop（turn.rs:1137-1200）的退出：
- Ok：直接返回 `SamplingRequestResult`
- `ContextWindowExceeded`：抛给外层
- `UsageLimitReached`：抛给外层
- 可重试错误：`handle_retryable_response_stream_error` 退避后重试，超过 `max_retries` 抛错

`SessionTask`（`tasks/mod.rs:214-254`）层还有更外层循环：`RegularTask::run`（`tasks/regular.rs:73-88`）在 `run_turn` 返回后检查 `has_pending_input`，有就再开一轮 `run_turn`。

## 9. 多 Agent 协作

**a. guardian sub-agent 隔离**

`guardian/review_session.rs:1-80` 是核心。`GuardianReviewSessionParams`（review_session.rs:73-80）携带 `parent_session` + `parent_turn` + `spawn_config` + `request`。关键设计：

- **独立 Config**：guardian clone 父 session 的 config 但覆盖 `session_source = SubAgent(SubAgentSource::Other("guardian"))`（review.rs:183-191 的 `is_guardian_reviewer_source`），使 `build_initial_context` 走 separate developer message 分支
- **不继承 caller policy**：guardian 的审批策略独立，父 turn 的 `on-request` 不影响 guardian 内部；guardian 只输出 `GuardianAssessment { risk_level, user_authorization, outcome, rationale }`（mod.rs:64-69）
- **prompt 隔离**：`build_guardian_prompt_items_with_parent_turn`（prompt.rs:92+）把父 transcript 作为 untrusted evidence 注入，但 guardian 自己的 policy 在独立 developer message；`build_skills_and_plugins`（turn.rs:504-665）见 `is_guardian_reviewer_source` 直接返回空，跳过所有 skill/plugin 注入
- **超时与熔断**：`GUARDIAN_REVIEW_TIMEOUT = 90s`（mod.rs:47），超时 fail closed；`GuardianRejectionCircuitBreaker`（mod.rs:78-134）累计 3 次连续否决或 50 窗口 10 次否决就 `InterruptTurn`
- **review_id 与 call_id 分离**（sandboxing.rs:125-133）：`guardian_review_id` 是 review 本身的 ID，`call_id` 是被审查的工具调用 ID，两者解耦让 denial/override/app-server 通知都能用 review_id 而不污染 call_id

**b. agent-registry / thread spawn**

`core/src/agent/registry.rs` 是 in-process 多 agent 注册表：
- `AgentRegistry`（registry.rs:23-26）：`active_agents: Mutex<ActiveUsers>` + `total_count: AtomicUsize`
- `reserve_spawn_slot`（registry.rs:80-97）：超过 `max_threads` 就返 `CodexErr::AgentLimitReached`
- `next_thread_spawn_depth` / `exceeds_thread_spawn_depth_limit`（registry.rs:71-77）：限制子 agent 嵌套深度
- `AgentMetadata`（registry.rs:35-42）：`agent_id` / `agent_path` / `agent_nickname` / `agent_role` / `last_task_message`

**c. agent-graph-store / agent-identity**

`Cargo.toml:5-6,140-141` 声明了 `codex-agent-graph-store` 和 `codex-agent-identity` 两个 workspace 成员 crate，但当前本地 clone 不包含它们的源码——可能在外部 path 或暂未同步。从 `core/src/session/multi_agents.rs` 和 `core/src/tools/handlers/multi_agents/` 推断，这两个 crate 负责：
- agent-graph-store：跨线程的 agent 关系图（spawn tree、message passing 路由）
- agent-identity：agent 唯一标识与角色定义

`core/src/agent/agent_names.txt` + `core/src/agent/role.rs` + `core/src/agent/control.rs` 是 in-core 的轻量配套，管理 agent 昵称池和角色状态。

## 10. 关键设计取舍

**a. sandbox-first 哲学**

Codex 把"先沙箱跑，失败再升级"作为默认路径（orchestrator.rs:223-296）。`SandboxOverride::BypassSandboxFirstAttempt`（sandboxing.rs:242-277）只在"策略显式信任 + 工具要求升级权限"时才生效。这与 Q-agent 的"永不沙箱"原则正相反——Codex 默认不信任 LLM 输出。

**b. guardian 隔离 vs 用户审批**

guardian 是"独立 sub-agent 替用户做审批决策"，避免每次工具调用都打断用户。隔离机制（review_session.rs:73-80）让 guardian 不继承 caller policy，避免"自己批准自己"。代价是 90s 超时 + 熔断 + extra LLM 调用，对单人桌面应用是过度设计。

**c. Rust 强类型 vs 灵活性**

`ToolRuntime<Rq, Out>` trait（sandboxing.rs:394-409）+ `Approvable<Req>` trait（sandboxing.rs:318-372）把"审批 key 类型"和"工具请求类型"做成关联类型（`type ApprovalKey`），编译期保证 key 类型与 tool 匹配。`ExecApprovalRequirement` 是三态枚举而非 bool，让"禁止"和"需要审批"语义分明。代价是新增工具时要 impl 多个 trait。

**d. 泛型 run_attempt vs 动态分发**

`ToolOrchestrator::run_attempt<Rq, Out, T>` 单态化（orchestrator.rs:61-132），每个 tool 实例生成独立代码。这比动态 trait object 快但编译时间增加。

**e. FuturesOrdered 并行工具**

`in_flight: FuturesOrdered`（turn.rs:1958）让多个工具并行执行但按 LLM 输出顺序回填历史，保证对话可读性。`RwLock` 区分并行/串行工具（parallel.rs:115-119）。

**f. InitialContextInjection 双模式**

`BeforeLastUserMessage`（mid-turn）vs `DoNotInject`（pre-turn/manual）（compact.rs:63-67）反映了模型训练时的 format 期望——mid-turn compact 后必须保留"最后一条是 user message"的格式。

## 11. 可借鉴要点

以下设计对 Q-agent 编排层有参考价值：

**a. ToolOrchestrator 的"approval → sandbox → attempt → retry"四段式**

虽然 Q-agent 永不沙箱，但"approval → attempt → 失败升级"的模式仍适用。Q-agent 可改造为："approval（用户确认）→ attempt → 失败重试（带降级）"。`ToolOrchestrator::run` 的泛型签名（orchestrator.rs:134-141）值得参考——把 tool 当 type 参数，orchestrator 不关心具体工具。

**b. ExecApprovalRequirement 三态枚举**

Q-agent 的"危险命令黑名单 + 项目根目录保护"可以借鉴这个模式：`Skip`（白名单）/ `NeedsApproval`（灰名单要问用户）/ `Forbidden`（黑名单直接拒），而不是简单的 allow/deny bool。

**c. ApprovalStore 缓存**

`sandboxing.rs:41-64` 的 `ApprovalStore` 用 `HashMap<String, ReviewDecision>` + `serde_json::to_string` 做序列化缓存。Q-agent 单人桌面应用中"本次会话不再问"的语义可直接复用——用户批准过的命令前缀缓存下来，下次自动放行。

**d. run_turn 外层 loop 的状态机思维**

turn.rs:214-451 的 loop 把"采样 / compact / pending_input / stop_hook"几个终止条件用 `needs_follow_up` + `token_limit_reached` + `has_pending_input` 三个 bool 组合表达，清晰且可扩展。Q-agent 的 turn loop 可参考这种"用 bool 组合而不是 enum 状态机"的风格。

**e. ProposedPlanItemState 流式计划**

turn.rs:1435-1490 的 `ProposedPlanItemState` + `PlanModeStreamState` 让"计划"和"叙述"在同一条流式响应里分流。Q-agent 若做 plan mode 可以直接复用这套"流式段切分"思路。

**f. ResponseEvent → ToolCall → tool_future → drain_in_flight 的流水线**

turn.rs:2018-2370 把流式事件 → 工具调用 → 并行执行 → 顺序回填的流水线表达得很清楚。Q-agent 用 Python `asyncio` 可对应：`asyncio.Queue` + `asyncio.gather` + `async for event in stream`。

**g. CompactionPhase + CompactionReason 分离**

compact.rs:140-141 的 `CompactionPhase`（PreTurn / MidTurn / StandaloneTurn）+ `CompactionReason`（ContextLimit / CompHashChanged / ModelDownshift / UserRequested）正交分离，便于 telemetry 和条件分支。Q-agent 自动 compaction 可照搬这个分类。

**h. SessionTask trait 的统一抽象**

`tasks/mod.rs:214-254` 的 `SessionTask` trait 把 RegularTask / CompactTask / ReviewTask / UserShellCommandTask 统一成"可 spawn / 可 abort / 有 kind / 有 span_name"的接口。Q-agent 可抽象类似"TaskBase"类，让不同类型的 turn 复用调度框架。

## 12. 不适合 Q-agent 借鉴的部分

**a. 整套 sandboxing crate（不适用）**

Q-agent 永不沙箱（CLAUDE.md 项目规则第十九节）。Codex 的 `SandboxManager` / `SandboxType::MacosSeatbelt` / `LinuxSeccomp` / `WindowsRestrictedToken` / `seatbelt_base_policy.sbpl` / `landlock.rs` / `bwrap.rs` 全部不适用。`SandboxAttempt` 的 14 个字段（sandboxing.rs:411-427）大多是沙箱相关，Q-agent 编排层不需要。`policy_transforms.rs` 的 `effective_permission_profile` 也以沙箱策略为核心，不适用。

**b. guardian sub-agent 机制（过度设计）**

Q-agent 是单人桌面应用（CLAUDE.md 项目概况），用户就在屏幕前，不需要 90s 超时的 LLM-as-reviewer 替用户做审批决策。guardian 的 `GuardianReviewSessionManager` / `GuardianRejectionCircuitBreaker` / `GuardianTranscriptCursor` / `GuardianPromptMode::Delta`（增量 review）等复杂机制服务于"无人值守的远程 coding"场景，对 Q-agent 是负价值——直接弹个 QMessageBox 让用户点"允许/拒绝"更合适。

**c. execpolicy 规则引擎（过度复杂）**

`execpolicy/src/policy.rs` + `rule.rs` + `parser.rs` + `amend.rs` 是一套完整的命令前缀 DSL 解析器，支持 `PrefixPattern` / `PrefixRule` / `NetworkRuleProtocol` 等。Q-agent 的"危险命令黑名单 + 项目根目录保护"（CLAUDE.md 第五节）用 Python `shlex` + 字符串匹配即可，不需要独立 crate。

**d. managed network proxy + network_approval（不适用）**

`core/src/tools/network_approval.rs` 的 `ActiveNetworkApproval` / `DeferredNetworkApproval` / `NetworkApprovalMode` 配合 `codex-network-proxy` crate 做企业级网络审计。Q-agent 本地 LLM 优先（项目规则第十节），不需要 MITM 代理审计。

**e. exec-server 远程执行（不适用）**

`codex-rs/exec-server/` 是为远程沙箱执行设计的 client-server 架构。Q-agent 所有工具调用在本地进程内完成（CLAUDE.md 第二节"零第三方依赖起步"），不需要 RPC。

**f. rollout / state_db / sqlite migrations（暂不需要）**

`rollout/src/state_db.rs` + `state/src/migrations.rs` 用 sqlite 做会话持久化。Q-agent 当前阶段用 JSON 文件记忆系统（CLAUDE.md 记忆系统规则），引入 sqlite 会增加 PyInstaller 打包复杂度（CLAUDE.md 第二十节"零外部依赖硬规则"）。后期若需持久化对话可考虑，但要先验证 sqlite3 能否被 PyInstaller `--onefile` 打包。

**g. Cargo workspace 多 crate 拆分（语言差异）**

Rust 的 workspace 模式在 Python 没有直接对应。Q-agent 应该用单包 + 多模块（`q_agent/orchestrator/`、`q_agent/tools/`、`q_agent/memory/`）而不是多包。Python 的 `import` 比 Rust 的 crate 依赖灵活得多，不需要提前做严格边界。

**h. ThreadSpawn depth limit + agent nickname pool（不适用）**

`agent/registry.rs:71-77` 的 `next_thread_spawn_depth` + `format_agent_nickname` 的 `nickname_reset_count` 机制服务于多 agent 协作场景。Q-agent 当前阶段没有多 agent 协作需求（项目当前节点 v0.0.17 是单 agent）。

**i. CompactionReason::CompHashChanged / ModelDownshift（暂不适用）**

compact.rs:879-958 的"模型切换时按 comp_hash 决定是否 compact"和"模型切到更小 context window 时 compact"在 Q-agent 本地 LLM 场景下意义不大——本地模型切换不频繁，且 Q-agent 切换模型时直接清空上下文（CLAUDE.md 当前阶段"切换模型清空上下文"）。

**j. PermissionRequestDecision hooks（暂不适用）**

`core/src/hook_runtime.rs` 的 `run_permission_request_hooks` 允许扩展点拦截审批。Q-agent 没有插件系统（CLAUDE.md "零第三方依赖起步"），不需要 hook 机制。
