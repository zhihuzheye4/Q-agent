# OpenClaw 编排调度层拆解报告

## 1. 项目概况

OpenClaw（github.com/openclaw/openclaw）是一个 TypeScript 实现的个人 AI 助手，定位不是纯 coding agent，而是覆盖 WhatsApp / Telegram / Slack / WebChat / iOS / Tailscale 等多通道、多 agent、多 backend 的通用助手。仓库根目录的 `README.md`/`VISION.md` 显示它同时支持 CLI 模式、守护进程模式、网关服务器模式，并通过插件机制把 LLM 后端、上下文引擎、工具、技能都做成可注册的槽位。

整体模块划分（只列与编排相关的）：
- `src/agents/` —— 编排层核心，约 1000+ 个 `.ts` 文件，是项目最大的目录
- `src/context-engine/` —— 可插拔上下文引擎接口与注册表
- `src/gateway/` —— 网关服务器（HTTP/WebSocket + 多通道路由 + session 持久化）
- `src/flows/` —— 一次性流程（doctor 健康检查、provider flow、channel setup、search setup），不是 agentic loop
- `src/interactive/` —— 便携 UI payload 类型定义（按钮 / 选项 / 文本块），与编排无关
- `src/cron/`、`src/daemon/` —— 定时任务与守护进程
- `src/llm/`、`src/memory/`、`src/commands/` —— LLM 抽象、记忆、命令

架构风格上 OpenClaw 是典型"插件驱动 + 多 backend 抽象 + 大量 retry/fallback 包裹"的工业级实现：核心 agent loop 被层层 wrapper（stream wrappers、harness plugins、context engine plugins、auth profile rotation、model fallback、compaction safety timeout、idle-timeout breaker、post-compaction loop guard）包成"洋葱式"调度器。

## 2. 编排调度层定位

OpenClaw 没有单一名为 "Planner" 或 "Orchestrator" 的类，编排调度分散在多个层次，自顶向下依赖关系如下：

```
agent-command.ts              顶层入口：选 model / agent / delivery / 创建 runId
  └─ command/attempt-execution.ts   runAgentAttempt：选 embedded / CLI / ACP runtime
       ├─ embedded-agent-runner/run.ts     外层 run loop（fallback / compaction / retry）
       │    └─ embedded-agent-runner/run/attempt.ts   单次 attempt（5780 行）
       │         └─ embedded-agent-runner/run/backend.ts  → harness/selection.ts → runAgentHarnessAttempt
       │              └─ harness/builtin-openclaw.ts → runEmbeddedAttempt
       │                   └─ embedded-agent-subscribe.ts   订阅 agent-core 事件流
       │                        └─ runtime/index.ts → packages/agent-core Agent
       │                             └─ agent.streamFn（被多层 wrap）
       ├─ cli-runner/execute.ts            CLI backend（Claude CLI / Gemini CLI 子进程）
       └─ ACP runtime（acp-spawn.ts 等外部 agent 协议）
```

关键目录/文件职责：
- `src/agents/agent-command.ts:1-2471` —— 顶层 `agentCommand` 函数，负责 session 解析、model selection、delivery plan、attempt lifecycle；调度 `runAgentAttempt`
- `src/agents/command/attempt-execution.ts:463-835` —— `runAgentAttempt`：根据 provider 判断走 `runCliAgent` 还是 `runEmbeddedAgent`，是 OpenClaw 区别于其它 agent 工具的"多 backend 路由"入口
- `src/agents/embedded-agent-runner/run.ts:597-615` —— `runEmbeddedAgent`，embedded runtime 外层入口
- `src/agents/embedded-agent-runner/run.ts:1872-4180` —— `while (true)` 主循环（这是 OpenClaw 真正的 Orchestrator）
- `src/agents/embedded-agent-runner/run/attempt.ts:1-5780` —— `runEmbeddedAttempt`：单次 attempt 的全部细节（prompt 构建、stream wrappers、tool 装配、subscription、compaction 触发）
- `src/agents/embedded-agent-subscribe.ts:162-200` —— `subscribeEmbeddedAgentSession`：把 agent-core 事件流转换成 OpenClaw 的 reply/tool/agent event
- `src/agents/sessions/agent-session.ts:1-3282` —— `AgentSession` 类，更高层抽象，绑定 extension runner、session manager、bash executor、compaction，是 interactive / print / rpc 三种模式共享的 session 主体
- `src/context-engine/types.ts:298-460` —— `ContextEngine` 接口，定义 `bootstrap/maintain/ingest/afterTurn/assemble/compact` 生命周期
- `src/context-engine/registry.ts:1-1029` —— 引擎注册表 + 兼容性代理（legacy 兼容包装 + quarantine 健康检查）
- `src/agents/agent-tools.ts:427-1264` —— `createOpenClawCodingTools`：组装全部工具（core / shell / channel / openclaw / plugin / tool-search），再过 sandbox/profile/provider/sender/group/subagent policy

依赖关系（从下到上）：`packages/agent-core` 提供 `Agent` 类 → `runtime/index.ts` 桥接到 OpenClaw 环境 → `embedded-agent-subscribe` 把事件流转成 reply → `run/attempt.ts` 单次执行 → `run.ts` 重试循环 → `attempt-execution.ts` backend 路由 → `agent-command.ts` 顶层调度。

## 3. Planner 实现

OpenClaw 没有"LLM 输出被解析成结构化意图"的独立 Planner——LLM 直接通过 OpenAI/Anthropic tool-calling 协议输出 `tool_calls`，由 agent-core 与 stream wrappers 解析。结构化意图只有几个特例：

- `src/agents/embedded-agent-runner/run/attempt.ts:3060-3096` 把 `streamFn` 用 `wrapStreamFnSanitizeMalformedToolCalls` / `wrapStreamFnRepairMalformedToolCallArguments` / `wrapStreamFnTrimToolCallNames` / `wrapStreamFnDecodeXaiToolCallArguments` 等多层 wrapper 包起来——这些 wrapper 负责"修整 LLM 不合规的 tool_call 参数"（xAi 把参数编码成奇怪字符串、模型把 tool 名加前缀等）。这是 OpenClaw 在"非标准 LLM 输出解析"上做的关键工程：不指望 LLM 一定规范，每一条 stream 都过清洗管道。
- `src/agents/agent-tools.ts:427` `createOpenClawCodingTools` 组装最终给 LLM 看的 tool schemas，但参数 JSON Schema → tool 调用参数的解码由 stream wrappers 与 `agent-tool-definition-adapter.ts` 处理。
- `src/agents/replay-turn-classification.ts`、`embedded-agent-utils.ts` 负责"LLM 输出是不是只有 reasoning / 是否是空 turn / 是否需要重试"的结构化判定，决定是 retry 还是 finalize。

Planner 在 OpenClaw 中等价于"LLM tool-calling 协议 + stream wrappers 兜底清洗 + replay 分类器"——没有显式 Planner 抽象，所有"意图结构化"都靠 LLM 自己的 function calling + 后处理清洗。这跟 Claude Code 的"靠 LLM 输出 tool_call"思路一致，但 OpenClaw 多了"清洗 + 修复 + 重新解码"多层防御。

## 4. Orchestrator 实现

OpenClaw 的 Orchestrator 是 `src/agents/embedded-agent-runner/run.ts:1872` 起的 `while (true)` 循环，每次循环：

1. **构建 prompt**（`run.ts:1917-1931`）：基础 prompt + retry instruction（reasoningOnlyRetryInstruction / emptyResponseRetryInstruction / compactionContinuationRetryInstruction / beforeAgentFinalizeRevisionReason）拼接。
2. **构建 runtimePlan**（`run.ts:1940-1968`）：`buildAgentRuntimePlan` 把 provider/model/harnessId/authProfileId/thinkLevel/extraParams 合并成单次 attempt 的运行计划。
3. **调度 attempt**（`run.ts:2031`）：`runEmbeddedAttemptWithBackend` → `run/attempt.ts` 的 `runEmbeddedAttempt`，里面会装配 tools、subscribe agent-core 事件、调用 `contextEngine.assemble` 组装上下文、调用 `agent.prompt` 启动 stream。
4. **判定结果分支**（`run.ts:2219-2406`）：检查 `aborted / timedOut / promptError / assistantErrorText / preflightRecovery / requestedSelection`，再分流到：
   - **timeout-triggered compaction**（`run.ts:2407-2546`）：LLM 超时且 prompt token > 65% 时，先 compact 再 retry
   - **context overflow**（`run.ts:2548-2700+`）：检测 overflow 错误 → compact → retry，最多 `MAX_OVERFLOW_COMPACTION_ATTEMPTS = 3`
   - **auth profile rotation**（`run.ts:1486`）：rate_limit / overloaded → 轮换 auth profile
   - **model fallback**（`run.ts:1064-1095`）：fallbackConfigured 且当前 profile 用尽 → 切换到 fallback provider/model
   - **incomplete turn retry**（`run.ts:3900-3985`）：stopReason=error 但无 assistant 文本 → 注入 retry instruction 继续
   - **beforeAgentFinalize revision**（`run.ts:3987-4010`）：hook 要求 revise final answer → 注入 revision prompt 继续
   - **terminal**（`run.ts:4051-4120`）：所有检查通过 → 返回 `EmbeddedAgentRunResult`

CLI backend 的 Orchestrator 在 `src/agents/cli-runner/execute.ts` 里，逻辑等价但目标是外部 CLI 子进程（Claude CLI / Gemini CLI），通过 JSONL streaming 解析子进程输出、抓 mcp loopback tool 调用、提取 messaging tool delivery evidence——本质是"把外部 CLI 当成 LLM"的适配层。

agent-core 层的 inner loop（驱动 LLM → 工具 → 结果回喂）藏在 `packages/agent-core/src/agent.ts`（未在仓库中可见，但被 `runtime/index.ts:19` 引用）：`Agent.prompt()` 调用 `streamFn` 拿 LLM 流，遇到 `tool_calls` 自动调用 `agent.executeToolCall`，把结果作为 `tool_result` 消息追加到 state.messages，再 `continue()` 调用 LLM，直到 LLM 给出 `end_turn` 或 `stop`。OpenClaw 的 `AgentSession.handlePostAgentRun`（`sessions/agent-session.ts:1100-1122`）在 agent-core 跑完后做 retry 决策与 compaction 检查。

## 5. 工具调用循环

从 LLM 输出到工具执行结果回喂的完整流程（embedded 模式）：

1. **streamFn 调用**：`run/attempt.ts:2849` 设置 `activeSession.agent.streamFn = resolveEmbeddedAgentStreamFn(...)`，再用多层 wrapper 包裹（`wrapStreamFnTextTransforms`、`createCodexNativeWebSearchWrapper`、`wrapStreamFnWithMessageTransform`、`wrapAnthropicStreamWithRecovery`、`wrapStreamFnSanitizeMalformedToolCalls`、`wrapStreamFnRepairMalformedToolCallArguments`、`wrapStreamFnTrimToolCallNames`、`wrapStreamFnDecodeXaiToolCallArguments`、`anthropicPayloadLogger.wrapStreamFn`）。
2. **agent.prompt 调用**：`run/attempt.ts:3537` `subscribeEmbeddedAgentSession(...)` 启动订阅；agent-core 内部调用 streamFn 拿 LLM 流，遇到 `tool_call` content block 就 emit `tool_execution_start` 事件。
3. **事件 → handler**：`src/agents/embedded-agent-subscribe.handlers.ts` / `embedded-agent-subscribe.handlers.tools.ts:handleToolExecutionStart` 接到事件，构造 `toolMeta`，发 `onToolStreamBoundary` / `onPartialReply`。
4. **tool 执行**：agent-core 调用 `agent.tools[name].execute(toolCallId, args, signal, onUpdate)`，OpenClaw 在 `agent-tools.ts:427` 的 `createOpenClawCodingTools` 里把每个 tool 用 `wrapToolWithBeforeToolCallHook`（`agent-tools.before-tool-call.ts`）包了一层 hook，再过 `tool-policy-pipeline.ts` 的 allowlist/denylist 过滤，最后调用真实工具函数。
5. **tool 结果回喂**：tool 执行完 → agent-core 自动把结果包成 `tool_result` 消息追加到 `state.messages` → 下次 streamFn 调用时把整个 messages 数组喂给 LLM。这是 agent-core 的内置行为，OpenClaw 不需要手动驱动。
6. **OpenClaw 层观测**：`embedded-agent-subscribe.ts:handleToolExecutionEnd` 提取 tool 输出文本 / media URLs，通过 `onToolResult` 回调传给外层；`run.ts:1600-1616` 的 `observeToolOutcome` 把每次 tool 结果喂给 `postCompactionGuard`（防止 compaction 后无限重跑相同 tool）。
7. **loop 终止**：agent-core 在 LLM 输出 `end_turn` 或 `stop` 且没有 pending tool_call 时停止 inner loop，OpenClaw 的 `subscribeEmbeddedAgentSession` 在 `message_end` 事件后返回 attempt 结果，外层 `run.ts:1872` 的 `while (true)` 再决定是否 retry。

CLI backend 的 tool 执行路径（`cli-runner/execute.ts`）不一样：Claude CLI / Gemini CLI 子进程内部自己执行 tool，OpenClaw 只通过 JSONL stream 解析 + MCP loopback capture（`beginMcpLoopbackToolCallCapture`）抓 OpenClaw-owned tool 调用，结果由 CLI 子进程内部回喂，OpenClaw 不参与 inner loop。

## 6. 上下文管理

`src/context-engine/types.ts:298-460` 定义 `ContextEngine` 接口：

```typescript
interface ContextEngine {
  readonly info: ContextEngineInfo;
  bootstrap?(params): Promise<BootstrapResult>;       // 初始化 session
  maintain?(params): Promise<ContextEngineMaintenanceResult>;  // transcript 维护
  ingest(params): Promise<IngestResult>;               // 单条消息入库
  ingestBatch?(params): Promise<IngestBatchResult>;    // 批量入库
  afterTurn?(params): Promise<void>;                   // turn 完成后
  assemble(params): Promise<AssembleResult>;           // 组装 model context
  compact(params): Promise<CompactResult>;            // 压缩
  prepareSubagentSpawn?(params): ...;                   // subagent 准备
  onSubagentEnded?(params): ...;
  dispose?(): Promise<void>;
}
```

`AssembleResult.messages` 是最终喂给 LLM 的 messages 数组，`AssembleResult.promptAuthority` 控制外层 overflow precheck 用哪个 token 估计（`types.ts:18-37`）。

`src/context-engine/registry.ts` 管理引擎注册：
- `resolveContextEngine(config, ctx)` 按 config 选取已注册引擎，默认 fallback 到 `legacy`（`registry.ts` 后半段）
- `ContextEngineFactoryContext` 让引擎工厂拿到 config/agentDir/workspaceDir
- 引擎可以声明 `hostRequirements`（要求 host 支持 `bootstrap` / `assemble-before-prompt` / `after-turn` / `maintain` / `compact` / `runtime-llm-complete` / `thread-bootstrap-projection` 能力），不满足则降级（`types.ts:62-77`）
- 引擎可被 quarantine（`quarantine-health.ts`）——出错后标记不可用，下次自动回退到 legacy

`src/context-engine/legacy.ts` 是默认实现：
- `ingest`：no-op（SessionManager 自己管持久化）
- `assemble`：pass-through（直接返回传入 messages，让外层 attempt.ts 的 sanitize/validate/limit 管道处理）
- `compact`：`delegateCompactionToRuntime` 委托给 `compaction.ts` 的 `compactEmbeddedAgentSessionDirect`
- `afterTurn`：no-op

真正的 compaction 实现在 `src/agents/compaction.ts`：
- `chunkMessagesByMaxTokens` / `splitMessagesByTokenShare` / `buildSummaryChunksWithWorker` 把历史分块（`compaction-planning.ts` + `compaction-planning-worker.ts`，用 worker thread 避免阻塞主循环）
- 每块调 `generateSummary`（`sessions/compaction/compaction.ts`）让 LLM 总结
- 多块 summary 再 merge（`MERGE_SUMMARIES_INSTRUCTIONS`，`compaction.ts:50-63`），保留 active tasks / batch progress / 最后用户请求 / decisions / TODOs
- `retryAsync` 包了 3 次 retry，每次 500-5000ms jitter backoff
- `IDENTIFIER_PRESERVATION_INSTRUCTIONS`（`compaction.ts:64-66`）强制保留 UUID / hash / IP / URL 等不透明标识符

Compaction 触发点（`run.ts`）：
- **timeout compaction**（`run.ts:2407-2546`）：LLM 超时且 prompt token / context token > 0.65 → 强制 compact，最多 `MAX_TIMEOUT_COMPACTION_ATTEMPTS = 2`
- **overflow compaction**（`run.ts:2548-2700+`）：LLM 报 overflow 错误 → compact，最多 `MAX_OVERFLOW_COMPACTION_ATTEMPTS = 3`
- **threshold compaction**（`sessions/agent-session.ts:checkCompaction`）：`shouldCompact(messages, model)` 阈值触发
- **manual compaction**：用户 `/compact` 命令
- 所有 compaction 调用都用 `compactContextEngineWithSafetyTimeout`（`embedded-agent-runner/compaction-safety-timeout.ts`）包一层超时保护，防止插件引擎 hang

`context-engine-maintenance.ts` 提供 `runContextEngineMaintenance` / `waitForDeferredTurnMaintenanceForSession`，让引擎在 turn 后异步做 transcript 重写（`rewriteTranscriptEntries`，`types.ts:280-283`）——引擎可以请求"把这些旧消息替换成新内容"。

## 7. 错误处理 & 降级

OpenClaw 的错误处理是"洋葱式"层层兜底：

**LLM 失败**（`embedded-agent-helpers.ts` + `failover-error.ts`）：
- `classifyFailoverReason(err)` 把错误归类成 `rate_limit / overloaded / context_overflow / auth / timeout / incomplete_turn / abort / unknown`
- `FailoverError` 携带 `reason / provider / model / profileId / sessionId / lane / status`
- `run/assistant-failover.ts:445` 的 `handleAssistantFailover` 决定是同模型重试、profile rotation 还是 model fallback

**Profile rotation**（`run.ts:1486`）：
- `while (nextIndex < profileCandidates.length)` 依次尝试 auth profile
- `MAX_SAME_MODEL_RATE_LIMIT_RETRIES`（`run/helpers.ts`）限制同模型 rate_limit 重试次数
- `maybeMarkAuthProfileFailure` 把失败 profile 写入 cooldown（`auth-profiles.ts`）
- `maybeEscalateRateLimitProfileFallback`（`run.ts:1670-1696`）：profile rotation 用完 → 升级到 model fallback

**Model fallback**（`runWithModelFallback` + `model-fallback.ts`）：
- `run.ts:1882` 的 `resolveRunFailoverDecision` 决定是否切到 fallback provider/model
- `classifyEmbeddedAgentRunResultForModelFallback` 判断错误是否 `fallbackSafe`（不重复 side effect）
- `mergeEmbeddedAgentRunResultForModelFallbackExhaustion` 处理 fallback 用尽

**Tool 失败**：
- `tool-error-summary.ts` 汇总
- `session-tool-result-guard.ts` 包装持久化 hook，防止 tool result 写入失败把 session 搞坏
- `Last tool error` 记录在 attempt，用于决定 `canRestartForLiveSwitch`（有 tool error 时不允许 live switch）

**多通道消息失败**：
- `gateway/chat-abort.ts` 处理 chat 中断
- `channel-health-monitor.ts` + `channel-health-policy.ts` 监控通道健康
- `pendingFinalDelivery` 字段（`agent-command.ts:419-432`）记录未送达的最终回复，下次 run 时 retry delivery
- `restartRecoveryDeliveryRunId` 机制让 daemon 重启后恢复未完成的 delivery

**降级路径**：
- context engine 不支持 host capability → `assertContextEngineHostSupport` 抛错，回退到 legacy
- context engine 被 quarantine → registry 自动切到 fallback engine
- CLI backend session 失效 → `clearCliSessionInStore` 清掉 binding 重跑
- LLM 给空回复 → `emptyResponseRetryInstruction` 注入再跑，最多 `MAX_EMPTY_RESPONSE_RETRIES = 3`
- LLM 只有 reasoning → `reasoningOnlyRetryInstruction` 注入再跑，最多 `DEFAULT_REASONING_ONLY_RETRY_LIMIT`
- LLM stopReason=error 零 token → `emptyErrorRetries` 重试
- LLM 不完整 turn → `incompleteTurnText` + `resolveRunLivenessState` 决定是否 surface 给用户

## 8. 循环终止条件

OpenClaw 的 outer loop（`run.ts:1872 while (true)`）有非常多退出条件，全部在 `run.ts` 中：

- **MAX_RUN_LOOP_ITERATIONS**（`run.ts:1549, 1873`）：`resolveMaxRunRetryIterations(profileCandidates.length, config, agentId)`，超过 → `handleRetryLimitExhaustion`
- **MAX_TIMEOUT_COMPACTION_ATTEMPTS = 2**（`run.ts:1547`）：timeout 触发的 compaction 用尽
- **MAX_OVERFLOW_COMPACTION_ATTEMPTS = 3**（`run.ts:1548`）：overflow 触发的 compaction 用尽
- **MAX_BEFORE_AGENT_FINALIZE_REVISIONS = 3**（`run.ts:256`）：hook 要求 revise final answer 的次数
- **MAX_EMPTY_ERROR_RETRIES = 3**（`run.ts:1630`）：stopReason=error 零输出重试
- **MAX_MISSING_ASSISTANT_RETRIES = 1**（`run.ts:1632`）：完全没有 assistant message 的重试
- **DEFAULT_REASONING_ONLY_RETRY_LIMIT**（`run.ts:1544`，来自 `run/incomplete-turn.ts`）：只有 reasoning 没有 visible answer 的重试
- **DEFAULT_EMPTY_RESPONSE_RETRY_LIMIT**（`run.ts:1545`）：空回复重试
- **MAX_CONSECUTIVE_IDLE_TIMEOUTS_BEFORE_OUTPUT**（`run.ts:2266-2311`，来自 `run/idle-timeout-breaker.ts`）：cost-runaway breaker，连续 idle timeout 且无 model progress → 退
- **MAX_SAME_MODEL_RATE_LIMIT_RETRIES**（`run.ts:1754`）：同模型 rate_limit 重试
- **resolveOverloadProfileRotationLimit / resolveRateLimitProfileRotationLimit**（`run.ts:1635-1636`）：profile rotation 上限
- **Post-compaction loop guard**（`run.ts:1586-1589, 1610-1615`）：`createPostCompactionLoopGuard` 观察 tool outcome，检测到 compaction 后无限循环相同 tool → abort
- **Tool loop detection**（`tool-loop-detection.ts`）：`TOOL_CALL_HISTORY_SIZE = 30`，`WARNING_THRESHOLD = 10`，`CRITICAL_THRESHOLD = 20`，`GLOBAL_CIRCUIT_BREAKER_THRESHOLD = 30`，检测 `generic_repeat / unknown_tool_repeat / known_poll_no_progress / ping_pong / global_circuit_breaker` 五种模式
- **abort signal**（`run.ts:655-669`）：外部 abort → 抛 `AbortError`
- **lane task timeout**（`run.ts:347-363`）：`EMBEDDED_RUN_LANE_TIMEOUT_GRACE_MS = 30_000`，超时 abort
- **terminal path**（`run.ts:4051`）：所有检查通过 → `return { payloads, meta }`
- **incomplete turn surface**（`run.ts:3944`）：retry 用尽 → 把 incompleteTurnText 当 error payload 返回

**正常退出**：LLM 输出 `end_turn` 且无 pending tool_call 且无 retry 触发条件 → `run.ts:4012-4120` 走 terminal path，返回 `EmbeddedAgentRunResult`，包含 `payloads / meta.agentMeta / meta.stopReason / meta.executionTrace / meta.toolSummary / meta.contextManagement`。

## 9. 多 Agent 协作

OpenClaw 支持"多 agent"，但不是"多 agent 协作完成同一任务"，而是"不同 session key 路由到不同 agent 配置 + subagent spawn"。

**Agent 路由**（`agent-scope.ts` + `agent-scope-config.ts`）：
- `resolveAgentIdFromSessionKey(sessionKey)` 从 session key 解析 agent id
- `resolveDefaultAgentId(cfg)` 拿默认 agent
- `resolveAgentConfig(cfg, agentId)` 拿 agent-specific 配置（system prompt / tools / sandbox / model defaults）
- `listAgentIds(cfg)` 列所有配置过的 agent
- session key 格式：`agentId:sessionId` 或 `sessionId`（implicit default agent），由 `routing/session-key.ts` 解析

**Subagent spawn**（`subagent-spawn.ts:1-1780`）：
- `subagent-spawn.ts` 的 `spawnSubagent` 函数：validate 请求 → 准备 child session（`forkSessionFromParent`）→ stage attachments → bind delivery context → register run
- `subagent-registry.ts` 管理子 agent 生命周期（注册 / 列表 / 清理 / archive / persistence）
- `subagent-depth.ts` 限制嵌套深度（`DEFAULT_SUBAGENT_MAX_SPAWN_DEPTH`）
- `subagent-capabilities.ts` 解析子 agent 能力（tool allowlist 继承）
- `subagent-target-policy.ts` 限制子 agent 能 spawn 到哪些 target
- `agent-steering-queue.ts` 让父 agent 可以 steer 子 agent（注入中间指令）
- 子 agent 在独立 lane（`AGENT_LANE_SUBAGENT`，`lanes.ts`），避免与父 lane 死锁
- `context-engine/types.ts:430-440` 的 `prepareSubagentSpawn` / `onSubagentEnded` 让引擎自己管理 fork context

**多通道路由到 agent**：
- `gateway/agent-list.ts` 列出 gateway 可用的 agent
- `gateway/agent-prompt.ts` 解析 agent-specific prompt
- session 创建时按 channel + agent id 绑定，不同通道的对话可以路由到不同 agent（比如 WhatsApp 用 agent A，Slack 用 agent B）
- `agent-command.ts:595-700` 的 `resolveExplicitAgentCommandSessionKey` 处理 session key 与 agent id 的绑定

**Lane 隔离**（`lanes.ts` + `process/command-queue.ts`）：
- `resolveSessionLane(sessionKey)` 给每个 session 一个独立 command lane（`session:xxx`）
- `resolveGlobalLane(lane)` 处理 cron / main / nested 区分
- 同一 session 的命令串行（防止并发污染 state），不同 session 并行
- `EMBEDDED_RUN_LANE_TIMEOUT_GRACE_MS` 让 lane task 有 30s grace 防止误判超时

## 10. 关键设计取舍

**取舍 1：插件驱动而非硬编码**
OpenClaw 把 LLM 后端（harness）、上下文引擎（context engine）、工具（tools）、技能（skills）、auth profile、delivery channel 全部做成可注册的插件槽位。`harness/selection.ts:590` 的 `selectAgentHarness` 根据 provider/model 选 harness plugin；`context-engine/registry.ts` 让 context engine 可插拔；`plugins/tools.ts` 让 plugin 注册 tool。代价是大量间接调用 + 元数据传递，单文件 5000+ 行的"调度中心"成为常态。

**取舍 2：多 backend 抽象**
`attempt-execution.ts:463-835` 的 `runAgentAttempt` 同时支持 embedded runtime（自己跑 LLM stream）、CLI backend（Claude CLI / Gemini CLI 子进程）、ACP runtime（外部 agent 协议）。同一个 `agentCommand` 入口可以路由到三种执行后端，但代价是 CLI backend 的 tool 循环不由 OpenClaw 控制，需要 MCP loopback capture 抓 tool 调用。

**取舍 3：重试/降级优先于简洁**
`run.ts:1872` 的 outer loop 有 14+ 种 retry 触发条件（timeout compaction / overflow compaction / profile rotation / model fallback / empty response / reasoning only / incomplete turn / missing assistant / silent error / before-agent-finalize revision / codex-app-server recovery / mid-turn precheck continuation / compaction continuation / post-compaction guard）。这是工业级 AI 助手在真实环境的产物——LLM 不稳定、provider rate limit、auth 过期、context overflow 都是常态。代价是代码可读性极差，单 `run.ts` 4202 行。

**取舍 4：Context engine 与 agent loop 解耦**
`ContextEngine` 接口把"消息历史管理 + token 控制 + 压缩"从 agent loop 中抽出来，让第三方可以替换（比如用向量检索引擎、用 SQLite 持久化、用 LLM-as-memory）。代价是 legacy 引擎只是 pass-through，真实逻辑还在 `compaction.ts` + `agent-session.ts`，要换引擎得自己重新实现完整 lifecycle。

**取舍 5：流式 + 事件订阅而非阻塞调用**
`subscribeEmbeddedAgentSession`（`embedded-agent-subscribe.ts:162`）用事件订阅模式（onPartialReply / onBlockReply / onReasoningStream / onAgentEvent / onToolResult）把 LLM stream 投射到 UI / channel / persistence。这跟 Claude Code 的"流式 + 事件"思路一致，但 OpenClaw 多了 `EmbeddedBlockChunker`（按 markdown block 边界切分流式输出）和 `deferBlockReplyDelivery`（在 terminal delivery 前让 hook 改写）。

**取舍 6：sandbox 可选但严格**
`sandbox.ts` + `sandbox-tool-policy.ts` 让 agent 可选在 Docker container 里跑 tool（`workspaceAccess: "none" | "ro" | "rw"`），但 OpenClaw 本身不做沙箱——通过 `bash-tools.exec-host-gateway.ts` 等委托给外部 CLI / Docker。这跟 Q-agent"永不沙箱"理念不同。

## 11. 可借鉴要点

对 Q-agent 设计编排层的参考价值：

1. **ContextEngine 接口抽象**（`context-engine/types.ts:298-460`）：`bootstrap / maintain / ingest / ingestBatch / afterTurn / assemble / compact / dispose` 八个生命周期方法，把上下文管理从 agent loop 完全解耦。Q-agent 早期可以只实现 legacy pass-through，但接口留好，后期换 RAG / 向量检索引擎不用动 agent loop。

2. **多层 stream wrapper 清洗 tool_call**（`run/attempt.ts:3060-3096`）：本地 LLM（Qwen / GLM / DeepSeek）的 tool_call 参数经常不合规，OpenClaw 的 `wrapStreamFnSanitizeMalformedToolCalls` / `wrapStreamFnRepairMalformedToolCallArguments` / `wrapStreamFnTrimToolCallNames` / `wrapStreamFnDecodeXaiToolCallArguments` 是直接可抄的工程模式——用 wrapper 函数包 streamFn，每层修一种问题。

3. **Loop 终止条件的精细化分级**（`run.ts:1547-1636`）：`MAX_TIMEOUT_COMPACTION_ATTEMPTS` / `MAX_OVERFLOW_COMPACTION_ATTEMPTS` / `MAX_EMPTY_ERROR_RETRIES` / `MAX_MISSING_ASSISTANT_RETRIES` / `DEFAULT_REASONING_ONLY_RETRY_LIMIT` / `MAX_CONSECUTIVE_IDLE_TIMEOUTS_BEFORE_OUTPUT`，每种 retry 触发条件独立计数，避免一种失败吃掉所有 retry budget。Q-agent 应该照抄这个分级思路。

4. **Idle-timeout cost-runaway breaker**（`run/idle-timeout-breaker.ts`）：连续 idle timeout 且无 model progress → 熔断，防止本地 LLM 卡死烧钱。Q-agent 接本地 LLM 特别需要这个。

5. **Post-compaction loop guard**（`run.ts:1586-1616`）：compaction 后 LLM 容易重复跑相同 tool（因为历史被压缩看不见自己做过），guard 观察 tool outcome 序列，检测重复 → abort。这是 OpenClaw 在生产环境踩坑后加的防御，Q-agent 一定要抄。

6. **Tool loop detection**（`tool-loop-detection.ts`）：`generic_repeat / unknown_tool_repeat / known_poll_no_progress / ping_pong / global_circuit_breaker` 五种模式 + 30 历史 / 10 warn / 20 critical / 30 breaker 阈值。Q-agent 可以直接移植这套检测逻辑。

7. **Compaction 分块 + summary merge**（`compaction.ts:131-200` + `compaction-planning-worker.ts`）：大对话分块 → 每块单独 LLM 总结 → 多块 summary 再 merge，用 worker thread 避免阻塞主循环；`IDENTIFIER_PRESERVATION_INSTRUCTIONS` 强制保留 UUID/IP/URL；`MERGE_SUMMARIES_INSTRUCTIONS` 保留 active tasks / batch progress / 最后用户请求 / decisions。这套 prompt + 流程是直接可抄的。

8. **Session lane 命令队列**（`lanes.ts` + `process/command-queue.ts`）：每个 session 独立 lane 串行执行，不同 session 并行，`EMBEDDED_RUN_LANE_TIMEOUT_GRACE_MS = 30_000` 给 grace。Q-agent 单用户单 session 用不上，但如果做多 session 切换需要这个隔离。

9. **subscribeEmbeddedAgentSession 事件流模式**（`embedded-agent-subscribe.ts:162-400`）：把 LLM stream 转成 `onPartialReply / onBlockReply / onReasoningStream / onAgentEvent / onToolResult` 回调，UI / persistence / channel 各自订阅。Q-agent 的 PySide6 UI 应该用同模式（Qt signal slot 订阅 agent event 流）。

10. **AgentSession 类的分层**（`sessions/agent-session.ts`）：`AgentSession` 持有 `Agent`（agent-core）+ `SessionManager` + `SettingsManager` + `ModelRegistry` + `ExtensionRunner`，把"agent 状态访问 / 事件订阅 / model 管理 / compaction / bash 执行 / session 切换"封装在一层，interactive / print / rpc 三种模式共享。Q-agent 可以参考这个分层（MainWindow 持有 AgentSession，AgentSession 持有 LLMClient + ToolRegistry + ContextEngine + SessionStore）。

11. **harness 抽象**（`harness/selection.ts:590` + `harness/builtin-openclaw.ts`）：`AgentHarness` 接口（`id / label / supports / runAttempt / contextEngineHostCapabilities`）让"哪个 backend 跑 agent"变成可选——OpenClaw 内置自己跑，也可以让 Claude CLI 跑、Codex 跑。Q-agent 早期只用本地 LLM backend，但接口留好，后期接 Claude API / OpenAI API 不用改 agent loop。

12. **failover 分类**（`embedded-agent-helpers.ts:classifyFailoverReason`）：把 LLM 错误明确分类成 `rate_limit / overloaded / context_overflow / auth / timeout / incomplete_turn / abort / unknown`，每类不同处理策略。Q-agent 接本地 LLM 也会有这些错误（Ollama 503 / timeout / context overflow），分类器值得抄。

## 12. 不适合 Q-agent 借鉴的部分

考虑 Q-agent 是 Python + 本地 LLM + 单人桌面应用（不需要多通道/守护进程/多用户），以下设计不适用：

1. **多通道 messaging 系统**（`src/gateway/` + `src/agents/embedded-agent-messaging.ts` + `channel-tools.ts`）：WhatsApp/Telegram/Slack/iOS/Tailscale/WebChat 多通道路由、message tool send / source reply / delivery plan / pendingFinalDelivery 字段，Q-agent 单人桌面不需要任何这些。

2. **Gateway server**（`src/gateway/server.ts:1-1500+` + `server-chat.ts:1455` + `server-methods.ts` 等）：HTTP/WebSocket 服务器、control-ui、device pairing、auth tokens、rate limiting、CSP——Q-agent 是桌面应用，不需要 HTTP 服务器。

3. **ACP（Agent Control Protocol）**（`src/acp/` 整个目录 + `agents/acp-spawn.ts` / `acp-runtime-overlay.ts`）：外部 agent 协议、外部 agent 服务器、binding 架构——Q-agent 内嵌 LLM 调用即可。

4. **Daemon / launchd / systemd**（`src/daemon/`）：守护进程、launchd plist、restart handoff、node service——Q-agent 是用户主动启动的桌面应用。

5. **Cron 定时任务**（`src/cron/`）：cron job 调度、heartbeat-triggered background runs、isolated agent、delivery-aware cron——Q-agent 单人桌面不需要后台定时任务。

6. **Subagent 多 agent 协作**（`subagent-spawn.ts:1780` + `subagent-registry.ts` + `subagent-depth.ts` 等）：subagent spawn、depth limit、capabilities inheritance、orphan recovery、announce registry——Q-agent 单 agent 单用户用不上。

7. **多 auth profile rotation**（`auth-profiles.ts` + `auth-profiles/` 整个子目录）：多 credential 轮换、cooldown、api-key-rotation、oauth flow、chutes-oauth、copilot-routing、live-auth-keys——Q-agent 本地 LLM 不需要 auth profile。

8. **CLI backend**（`cli-runner/` 整个目录）：Claude CLI / Gemini CLI 子进程启动、JSONL streaming 解析、MCP loopback capture、live session routing、cwd hash、mcp config hash、resume hash——Q-agent 自己跑 LLM stream，不需要外部 CLI 子进程。

9. **Plugin SDK 复杂度**（`src/plugins/` + `plugin-sdk/` + `extensionAPI.ts`）：plugin metadata snapshot、hook runner、provider runtime plugin、text transforms、tool registration via plugin——Q-agent 早期零第三方依赖起步，不需要 plugin SDK。

10. **Sandbox 模式**（`src/agents/sandbox.ts` + `sandbox/` 子目录）：Docker container 隔离、workspace mount、agent workspace mount、read-only mounts、media paths——Q-agent 明确"永不沙箱"，这部分完全跳过。

11. **Code mode / Skill workshop / Browser plugin / Camera plugin / Media generation**（`code-mode.ts` + `skill-workshop-prompt.ts` + `openclaw-tools.browser-plugin` + `openclaw-tools.camera` + `image-generation-task-status.ts` + `video-generation-task-status.ts` + `music-generation-task-status.ts`）：独立的 code mode 命名空间、skill workshop 提示、浏览器插件集成、摄像头工具、图片/视频/音乐生成——Q-agent 是 coding agent 风格的桌面助手，不需要这些扩展。

12. **Heartbeat 系统**（`heartbeat-system-prompt.ts` + `auto-reply/heartbeat-tool-response.ts` + `infra/heartbeat-wake.js`）：后台心跳唤醒、heartbeat tool response、heartbeat filter、heartbeat visibility——Q-agent 没有后台进程，不需要心跳。

13. **Trajectory 记录**（`trajectory/runtime.ts` + `trajectory/metadata.ts`）：把 agent run 的 prompt/tool/answer 完整录制成 trajectory 文件——Q-agent 简化版只需 chat history 持久化。

14. **大量 test 文件**（仓库约一半文件是 `.test.ts`）：OpenClaw 有 84%+ 测试覆盖率要求，每个特性都配 4-10 个测试文件（`run.overflow-compaction.loop.test.ts` 等）——Q-agent 起步 30% 覆盖率即可，不需要这种测试密度。

15. **bootstrap budget / bootstrap cache / bootstrap files / bootstrap hooks / bootstrap prompt warning signatures**（`bootstrap-budget.ts` + `bootstrap-cache.ts` + `bootstrap-files.ts` + `bootstrap-hooks.ts` + `bootstrap-prompt.ts`）：启动阶段把 workspace 文件注入 prompt 的复杂机制——Q-agent 简化为"启动时加载 CLAUDE.md + 项目指导文件"即可。

16. **strict-agentic execution contract**（`execution-contract.ts`）：区分"strict-agentic"模式与默认模式的 tool 执行契约——Q-agent 单一执行模式即可。

总结：OpenClaw 的核心可借鉴价值在 **ContextEngine 接口**、**stream wrapper 清洗**、**loop 终止分级**、**post-compaction guard**、**tool loop detection**、**compaction 分块流程**、**failover 分类** 这七项工程模式上；其多通道/多 agent/多 backend/多 plugin/多 cron 的"工业级助手"外壳完全不适合 Q-agent 的单用户桌面定位。