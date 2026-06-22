# Claude Code 编排调度层拆解报告

## 1. 项目概况

Claude Code 是 Anthropic 官方的 CLI 工具，本仓库 `github.com/NonSmiIe/claude-code-source-code-full` 是社区反编译镜像。TypeScript 实现，Bun 打包。

架构风格属于**单进程多生成器嵌套的 agentic loop**——核心是一个 `while (true)` 循环驱动 "LLM 流式响应 → 工具调用批次执行 → 结果回喂 → 下一轮 LLM 调用"，所有控制流用 async generator 串联，上层 `QueryEngine` 持有会话状态，下层 `query()` 是无状态循环。

模块划分（src/ 下）：
- **会话层**：`QueryEngine.ts`（1297 行）——每会话一个实例，持有 mutableMessages / abortController / usage / 文件缓存
- **循环层**：`query.ts`（1730 行）——`queryLoop()` 是 agentic 主循环
- **工具层**：`Tool.ts` 定义 `Tool` 接口与 `ToolUseContext`；`services/tools/` 三件套（`toolOrchestration.ts` 分批/并发调度、`StreamingToolExecutor.ts` 流式执行器、`toolExecution.ts` 单工具执行）
- **任务层**：`Task.ts` 定义 `TaskType`（local_bash / local_agent / remote_agent / in_process_teammate / local_workflow / monitor_mcp / dream）；`tasks/` 目录每个子目录一个具体任务实现
- **编排层**：`coordinator/coordinatorMode.ts`——多 agent 协作模式开关
- **压缩层**：`services/compact/`——autoCompact / microCompact / compact / snipCompact / sessionMemoryCompact / reactiveCompact 多策略
- **上下文层**：`context.ts`（gitStatus / claudeMd / currentDate）、`history.ts`（命令历史持久化）
- **子 agent**：`tools/AgentTool/`——子 agent 通过 `runAgent.ts` 递归调用 `query()`

## 2. 编排调度层定位

编排层由三块构成，依赖关系自上而下：

```
QueryEngine (会话级，持有状态)
   └─ submitMessage() 入口
       └─ query() / queryLoop() (单轮循环)
           ├─ deps.callModel → services/api/claude.ts queryModelWithStreaming
           ├─ deps.microcompact / deps.autocompact → services/compact/*
           ├─ StreamingToolExecutor (流式工具执行)
           │   └─ runToolUse → services/tools/toolExecution.ts
           │       └─ checkPermissionsAndCallTool → tool.call()
           ├─ handleStopHooks → query/stopHooks.ts
           └─ getAttachmentMessages → utils/attachments.ts (memory prefetch, skills)
       └─ coordinator 模式（可选）→ AgentTool → runAgent → query() 递归
```

关键文件清单：
- `src/QueryEngine.ts:184` `class QueryEngine` —— 会话级状态机
- `src/query.ts:241` `queryLoop()` —— 主循环
- `src/services/tools/toolOrchestration.ts:19` `runTools()` —— 工具批次调度
- `src/services/tools/toolExecution.ts:337` `runToolUse()` —— 单工具执行入口
- `src/coordinator/coordinatorMode.ts:36` `isCoordinatorMode()` + `getCoordinatorSystemPrompt()`
- `src/tools/AgentTool/runAgent.ts:248` `runAgent()` —— 子 agent 递归
- `src/services/compact/autoCompact.ts:241` `autoCompactIfNeeded()`

`query.ts` 是绝对的编排中枢：模型调用、压缩、工具执行、stop hooks、附件注入、token budget 续写、max_turns 检查都在它的 `while (true)` 内完成。

## 3. Planner 实现

Claude Code **没有显式的 Planner 模块**。意图解析完全依赖 LLM 输出的结构化 `tool_use` 块——这与其他框架（如 LangChain Agent）"先规划后执行"不同，是"模型即规划器"路线。

LLM 输出在 `query.ts:659` 通过 `deps.callModel` 流式返回 `Message`，其中 `assistant` 类型消息的 `message.content` 数组里可能混合三类块：
- `text` —— 普通回复
- `thinking` —— 思考块（受 `thinkingConfig` 控制，`QueryEngine.ts:278`）
- `tool_use` —— 工具调用意图（含 `id` / `name` / `input`）

`query.ts:826-836` 是意图分流的关键：
```ts
if (message.type === 'assistant') {
  assistantMessages.push(message)
  const msgToolUseBlocks = message.message.content.filter(
    content => content.type === 'tool_use',
  ) as ToolUseBlock[]
  if (msgToolUseBlocks.length > 0) {
    toolUseBlocks.push(...msgToolUseBlocks)
    needsFollowUp = true  // 唯一的循环继续信号
  }
}
```

`needsFollowUp` 是整个循环的唯一续跑信号——只要本批 assistant 消息里有任何 `tool_use` 块，下一轮就要把工具结果回喂。没有 `tool_use` 块即视为 LLM 给出了最终回答（或进入 stop hook 评估流程）。

Slash 命令（如 `/compact`、`/force-snip`）在 `QueryEngine.ts:416` 通过 `processUserInput()` 在进入 query 前处理，会修改 `mutableMessages` 或直接产出本地命令输出——这条路径走 `shouldQuery === false` 分支（`QueryEngine.ts:556`），不进入 LLM 循环。

## 4. Orchestrator 实现

`QueryEngine.submitMessage()`（`QueryEngine.ts:209`）是会话入口，负责：
1. 拼装 `systemPrompt`（`fetchSystemPromptParts` + `getCoordinatorUserContext` + `appendSystemPrompt`，`QueryEngine.ts:288-325`）
2. 构造 `ProcessUserInputContext`（含 tools / mcpClients / agents / abortController / 文件缓存等，`QueryEngine.ts:335-395`）
3. 调 `processUserInput` 处理 slash 命令、提取附件（`QueryEngine.ts:416`）
4. 持久化用户消息到 transcript（`QueryEngine.ts:450-463`）
5. 进入 `query()` 主循环（`QueryEngine.ts:675`）
6. 流式 yield 出 assistant / user / progress / attachment / system / stream_event 等 SDK 消息
7. 循环结束后判定 `isResultSuccessful`，yield 最终 `result` 消息（`QueryEngine.ts:1135`）

`query.ts` 的 `queryLoop()` 是真正的 Orchestrator。每轮迭代做的事（`query.ts:307-1728`）：

```
[1] 读取上一轮的 state（messages / tracking / pendingToolUseSummary …）
[2] 启动 skill 发现与 memory 预取（不阻塞主流程）
[3] yield stream_request_start
[4] 计算 queryTracking.chainId / depth（嵌套调用追踪）
[5] getMessagesAfterCompactBoundary → applyToolResultBudget → snip → microcompact → contextCollapse → autocompact（五级压缩流水线，按顺序尝试）
[6] 计算 currentModel（含 plan 模式 200k 升级，query.ts:572-578）
[7] blocking limit 检查（token 超阈则直接 yield API error 并 return）
[8] callModel 流式拉取 → 边拉边把 tool_use 块塞给 StreamingToolExecutor 执行
[9] 流结束后：abort 检查 / max_output_tokens 恢复 / prompt_too_long 恢复 / stop hooks
[10] if needsFollowUp：执行剩余工具 → 收集 toolResults → 注入 attachments → 拼新 messages → state = next → continue
[11] else：yield result / return Terminal
```

`State` 类型在 `query.ts:204-217` 集中声明，每轮通过 `state = { ...next }` 覆写（共 7 个 continue 站点，每个站点字段完整重写而非零散赋值），避免跨迭代状态泄漏。`transition` 字段记录上次 continue 的原因（`tool_use` / `reactive_compact_retry` / `max_output_tokens_recovery` / `collapse_drain_retry` / `stop_hook_blocking` / `token_budget_continuation` / `queued_command` / `next_turn`），用于防重入（如 collapse drain 只触发一次）。

`query/deps.ts:21` 用 `QueryDeps` 注入 `callModel / microcompact / autocompact / uuid`，便于测试替换。

## 5. 工具调用循环

完整流程（单条 tool_use 块）：

**a. 流式识别**（`query.ts:826-845`）：每收到 assistant 消息就 push 到 `assistantMessages`；同时把 `tool_use` 块 push 到 `toolUseBlocks` 与 `StreamingToolExecutor.addTool()`——后者立即开始并发执行（不等流结束）。

**b. 流式执行**（`StreamingToolExecutor.ts`）：`addTool()` 加入 `TrackedTool` 队列；并发安全的工具直接并行 `runToolUse`，非并发安全工具排队等待。`getCompletedResults()`（`query.ts:851-862`）边执行边 yield 已完成结果，让用户实时看到进度。

**c. 批次调度**（`toolOrchestration.ts:91` `partitionToolCalls`）：把 `toolUseBlocks` 按相邻合并分批——连续的并发安全工具合成一批并行，非并发安全工具单独成批串行。`runToolsConcurrently`（`toolOrchestration.ts:152`）用 `all()` 工具控制并发上限 `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY`（默认 10）。

**d. 单工具执行**（`toolExecution.ts:337` `runToolUse`）：
1. `findToolByName` 查工具（支持 alias 回退到 deprecated 名）
2. 检查 `abortController.signal.aborted` → 取消并 yield `CANCEL_MESSAGE`
3. 调 `streamedCheckPermissionsAndCallTool`（`toolExecution.ts:492`）→ 内部用 `Stream<MessageUpdateLazy>` 把进度事件和最终结果合成一个 async iterable
4. `checkPermissionsAndCallTool` 依次跑：`validateInput` → `canUseTool`（权限）→ `tool.checkPermissions` → `tool.call()` → 包装结果为 `ToolResultBlockParam`
5. try/catch 兜底：未知工具 yield `<tool_use_error>No such tool available`，执行异常 yield `<tool_use_error>Error calling tool: ...</tool_use_error>`——**错误不抛出，永远作为 tool_result 块回喂**，让 LLM 自己决定要不要重试

**e. 结果回喂**（`query.ts:1380-1408`）：流式执行器的 `getRemainingResults()` 或 `runTools()` 的 yield 结果被收集到 `toolResults` 数组；同时通过 `normalizeMessagesForAPI` 过滤出 `user` 类型消息（tool_result 块装在 user 消息里）。

**f. 下一轮**（`query.ts:1715`）：`state = { messages: [...messagesForQuery, ...assistantMessages, ...toolResults], ... turnCount: nextTurnCount, transition: { reason: 'next_turn' } }` → continue → 下一轮 `callModel` 拿到的就是带 tool_result 的新 messages。

工具接口契约（`Tool.ts:362`）关键字段：
- `call(args, context, canUseTool, parentMessage, onProgress)` —— 核心执行
- `isConcurrencySafe(input)` —— 决定并行/串行（默认 false，保守）
- `isReadOnly(input)` / `isDestructive(input)` —— 权限与 UI 提示
- `checkPermissions(input, context)` —— 工具自决权限
- `maxResultSizeChars` —— 超过就落盘，只把预览回喂模型
- `backfillObservableInput(input)` —— 在 yield 前给 input 补字段（如展开 file_path），不污染原 input（保 prompt cache 字节对齐）
- `interruptBehavior()` —— `'cancel'` 或 `'block'`，决定用户发新消息时此工具怎么办

## 6. 上下文管理

**消息存储**：`QueryEngine.mutableMessages: Message[]`（`QueryEngine.ts:186`）是会话唯一真源；每轮 query 内部用 `messagesForQuery` 副本（`query.ts:365`）做压缩/操作，循环结束才合并回。会话外用 `recordTranscript()`（`utils/sessionStorage.ts`）异步落盘到 transcript 文件，支持 `--resume`。

**Token 预算**：`utils/tokens.ts` 的 `tokenCountWithEstimation` 基于 API 返回的 `usage.input_tokens` + 估算估算当前消息列表的 token 数。`autoCompact.ts:72` `getAutoCompactThreshold()` 算出阈值 = `effectiveContextWindow - 13000`（`AUTOCOMPACT_BUFFER_TOKENS`）。`calculateTokenWarningState` 给出四档：warning / error / autocompact / blocking（`autoCompact.ts:93`）。

**多级压缩流水线**（`query.ts:400-468`，按顺序执行）：
1. **applyToolResultBudget**（`utils/toolResultStorage.ts`）——按字符预算裁剪超大的 tool_result 内容（替换为"content cleared"占位）
2. **snip**（feature `HISTORY_SNIP`，`services/compact/snipCompact.ts`）——按规则移除僵尸消息与失效标记
3. **microcompact**（`services/compact/microCompact.ts`）——只压缩 `COMPACTABLE_TOOLS` 集合（Read / Bash / Grep / Glob / WebSearch / WebFetch / Edit / Write）的旧 tool_result，用 `[Old tool result content cleared]` 占位
4. **contextCollapse**（feature `CONTEXT_COLLAPSE`）——按提交日志折叠段，保留 granular context 而非整体摘要
5. **autocompact**（`services/compact/autoCompact.ts:241`）——以上都无法压到阈值才触发，调 `compactConversation`（LLM 总结整个对话历史，`compact.ts`），产出 `CompactionResult` + `compact_boundary` 消息。`sessionMemoryCompaction` 是优先尝试的分支（`autoCompact.ts:288`），失败才走 LLM 总结

**Reactive compact**（`services/compact/reactiveCompact.ts`）：当 API 直接返回 prompt-too-long（413）时触发——`query.ts:1119` `tryReactiveCompact`。与 proactive autocompact 互斥，由 `hasAttemptedReactiveCompact` 标志防螺旋。

**任务级 budget**：`taskBudget: { total, remaining }`（`query.ts:191`、`query.ts:508-515`）——API 端的 task-budgets beta，每次 compact 时扣减 `finalContextTokensFromLastResponse`，告诉服务端剩余预算。

**Tool result budget**：`applyToolResultBudget`（`query.ts:379`）按工具的 `maxResultSizeChars` 字段控制；超出部分写盘，只回喂预览 + 文件路径，避免一个 Bash 输出把整个 context 撑爆。

**File state cache**：`readFileState: FileStateCache`（`Tool.ts:181`）记录每个 Read 过的文件的 mtime/hash，让后续 Edit 校验文件未被外部修改；`cloneFileStateCache`（`QueryEngine.ts:1259`）在 `ask()` 一次性使用时克隆，避免污染父会话。

**Memory prefetch**：`startRelevantMemoryPrefetch`（`query.ts:301`）在循环入口启动异步预取；`query.ts:1599-1614` 在工具执行后的某个迭代消费已 settled 的预取结果（零等待，未 settled 就跳过本轮）。

## 7. 错误处理与降级

**LLM / API 错误**：
- `try { callModel } catch (error)`（`query.ts:955-997`）：记录 `tengu_query_error` → `yieldMissingToolResultBlocks` 给未匹配的 tool_use 块补错误 result → yield `createAssistantAPIErrorMessage` → `return { reason: 'model_error' }`——**不让异常逃出循环**，总是给 SDK 一个干净的结果消息
- `FallbackTriggeredError`（`query.ts:894`）：主模型过载时切 fallbackModel 重试整个请求；先给已 yield 的 assistant 消息发 tombstone（让 UI 删除无效块），清空 `assistantMessages / toolResults / toolUseBlocks`，重建 `StreamingToolExecutor`（防 orphan tool_result 泄漏到重试）
- `ImageSizeError` / `ImageResizeError`（`query.ts:970-978`）：友好消息 + `return { reason: 'image_error' }`

**Prompt too long（413）**：`query.ts:1070-1183`—— withheld 机制：流式时检测到 413 不立即 yield，先尝试 `contextCollapse.recoverFromOverflow`（drain 已暂存的 collapses），再尝试 `reactiveCompact.tryReactiveCompact`；都不行才 surface 错误并 `executeStopFailureHooks`，**绝不 fall through 到 stop hooks**（否则死循环：hook 阻塞 → 重试 → 413 → hook 阻塞 …）

**Max output tokens**：`query.ts:1188-1256`——先尝试一次性升级到 64k（`ESCALATED_MAX_TOKENS`，`maxOutputTokensOverride`），升级仍失败则注入 meta 消息"Resume directly — no apology, no recap..."触发续写，最多 3 次（`MAX_OUTPUT_TOKENS_RECOVERY_LIMIT`）；3 次还失败才 surface 错误

**工具失败**：`toolExecution.ts:469-489`——所有异常都被 catch，转成 `<tool_use_error>` 块作为 tool_result 回喂；工具不存在（`runToolUse:369`）同样回喂错误 result；不中断循环，LLM 自己决定重试 / 放弃 / 换工具

**工具中断**：`query.ts:1015-1052` + `query.ts:1485-1516`——abort 信号检查点：流式后 / 工具执行后 / 工具执行中。检测到 abort：`StreamingToolExecutor.getRemainingResults()` 给未完成工具合成 synthetic tool_result（`'Interrupted by user'`），`yield createUserInterruptionMessage`，`return { reason: 'aborted_streaming' | 'aborted_tools' }`

**Autocompact 熔断**：`autoCompact.ts:70` `MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3`——连续失败 3 次后整会话内不再尝试 autocompact，避免 250K API 调用/天浪费的死亡螺旋（注释提到真实 BQ 数据）

**Budget 超限**：`query.ts:972-1001`——`maxBudgetUsd` 达到即 yield `error_max_budget_usd` 终止；structured output 重试超 5 次（`query.ts:1011` `MAX_STRUCTURED_OUTPUT_RETRIES`）也终止

## 8. 循环终止条件

`query/transitions.ts:9` `Terminal` 集中枚举所有退出原因：

- `completed` —— 正常结束（`needsFollowUp === false` 且 `isResultSuccessful`，`query.ts:1357`）
- `blocking_limit` —— token 超硬上限且 autocompact 关闭（`query.ts:646`）
- `image_error` —— 图片尺寸/resize 错（`query.ts:977`）
- `model_error` —— callModel 抛异常（`query.ts:996`）
- `aborted_streaming` —— 流式阶段 abort（`query.ts:1051`）
- `aborted_tools` —— 工具阶段 abort（`query.ts:1515`）
- `prompt_too_long` —— 413 且 reactive compact 也救不回（`query.ts:1175`、`query.ts:1182`）
- `stop_hook_prevented` —— stop hook 明确阻止继续（`query.ts:1279`）
- `hook_stopped` —— PostToolUse hook 返回 `hook_stopped_continuation` 附件（`query.ts:1519-1521`）
- `max_turns` —— `nextTurnCount > maxTurns`（`query.ts:1705-1712`），先 yield `max_turns_reached` attachment
- 以及 `isResultSuccessful(result, lastStopReason)` 判 false 时进入 `error_during_execution`（`QueryEngine.ts:1082-1116`）

正常完成的判定（`utils/queryHelpers.ts` `isResultSuccessful`）：最后一条 assistant 消息有 text / thinking 块且 stop_reason === `end_turn`，或者最后一条是带 tool_result 的 user 消息——都算成功。

## 9. 多 Agent 协作

Claude Code 的多 agent 模式分两种：

**a. Coordinator 模式**（`coordinator/coordinatorMode.ts:36`）：env `CLAUDE_CODE_COORDINATOR_MODE=1` 开启。系统 prompt 切换为 `getCoordinatorSystemPrompt()`（`coordinatorMode.ts:111`）——明确定义主 agent 为 "coordinator"，负责拆任务、派 worker、综合结果；worker 是无状态执行单元，通过 `AgentTool` 派生、通过 `SendMessageTool` 续派、通过 `TaskStopTool` 终止。`getCoordinatorUserContext`（`coordinatorMode.ts:80`）注入 worker 可用工具清单到 system prompt，让主 agent 知道派出去的 worker 能干什么。

**b. AgentTool 委派**（`tools/AgentTool/`）：不进 coordinator 模式也能用，主 agent 直接调 `AgentTool` 派子 agent。子 agent 类型由 `subagent_type` 指定（worker / researcher / verifier 等自定义类型，通过 `loadAgentsDir.ts` 加载）。

子 agent 执行流程（`tools/AgentTool/runAgent.ts:248` `runAgent`）：
1. `createAgentId()` 生成 `a` 前缀的 agentId（`Task.ts:98` `TASK_ID_PREFIXES`）
2. `createSubagentContext`（`utils/forkedAgent.ts`）——克隆父 context 但隔离 `setAppState`（async 子 agent 的 setAppState 是 no-op，改用 `setAppStateForTasks` 走根 store）、`readFileState`、`contentReplacementState`
3. `resolveAgentTools`（`agentToolUtils.ts`）——按 worker 权限模式重组工具池；coordinator 模式下用 `ASYNC_AGENT_ALLOWED_TOOLS` 白名单（`coordinatorMode.ts:92`）
4. **递归调 `query()`**（`runAgent.ts` 内）——子 agent 跑自己的 agentic loop，独立 messages、独立 queryTracking.depth + 1
5. 子 agent 消息通过 `recordSidechainTranscript`（`utils/sessionStorage.ts`）写入 sidechain 文件，主线程看不到子 agent 的中间消息，只在结束时 yield `AgentToolResult`
6. 子 agent 结果以 `<task-notification>` XML 包装的 user 消息注入主线程（`coordinatorMode.ts:144-160`），主 agent 看到后综合

**Task 状态机**（`Task.ts:15`）：pending / running / completed / failed / killed；`isTerminalTaskStatus`（`Task.ts:27`）防向死 task 注消息。具体 task 类型在 `tasks/` 下：`LocalShellTask`（bash 子进程）、`LocalAgentTask`（异步子 agent）、`RemoteAgentTask`（远端 agent）、`InProcessTeammateTask`（同进程队友，用 `AsyncLocalStorage` 隔离）、`DreamTask`、`LocalWorkflowTask`、`MonitorMcpTask`。

**In-process teammate**（`tasks/InProcessTeammateTask/`）：与子 agent 最大区别是**同进程**，共享 Node.js 事件循环但用 `AsyncLocalStorage` 隔离上下文，可 idle 等待新工作，支持 `injectUserMessageToTeammate` 续派（`InProcessTeammateTask.tsx:68`）——适合长时多轮协作。子 agent 是一次性任务。

**消息队列**（`utils/messageQueueManager.ts`）：`query.ts:1570` `getCommandsByMaxPriority('next' | 'later')` 按优先级取出排队的用户消息或 task notification；主线程只 drain `agentId === undefined` 的，子 agent 只 drain 自己 agentId 的 task-notification——队列是进程级单例，靠 agentId 分流。

## 10. 关键设计取舍

**a. 无显式 Planner，靠 LLM 的 tool_use 块当意图**——省了一个模块，但要求模型强（Claude 系列够强）；Q-agent 用本地 LLM 可能需要更明确的 planning 阶段。

**b. 状态机用 `state = { ...next }` 整体覆写而非零散赋值**（`query.ts:268-279` + 7 个 continue 站点）——避免跨迭代状态泄漏，每轮开头 destructure 一份新 state。

**c. 生成器 + yield 串联所有控制流**——`query()` 是 `AsyncGenerator`，所有中间消息（progress / attachment / stream_event / compact_boundary）都通过 yield 传出去；上层 `QueryEngine.submitMessage` 也是 generator，SDK 消费者按需读。好处是流式天然，坏处是错误处理复杂（要靠 return value 传 Terminal 而非 throw）。

**d. 多级压缩流水线**（snip → microcompact → collapse → autocompact → reactive）——每级都 feature flag 门控，按代价由低到高尝试，最贵的 LLM 总结放最后。microcompact 只动 `COMPACTABLE_TOOLS` 的旧 result，保留近期与新写的文件内容，平衡信息保留与 token 节省。

**e. Streaming tool execution**——流式拉到 tool_use 块就开始执行，不等整条 assistant 消息结束；`toolUseBlocks.push` 与 `streamingToolExecutor.addTool` 并行进行（`query.ts:838-845`）。代价是 fallback 时要发 tombstone + 重建 executor（`query.ts:712-741`）。

**f. Tool 接口的 `maxResultSizeChars` + 落盘**——超阈值的结果写文件，只回喂预览（`Tool.ts:466`）。避免单次 Bash 输出 200K 字符撑爆 context。

**g. `backfillObservableInput` 不污染原 input**——为保 prompt cache 字节对齐，原始 `tool_use.input` 永不修改；只在 yield 给 SDK/hooks 看的副本上补字段（`query.ts:748-787`）。这是对 Anthropic prompt caching 的硬性优化。

**h. `transition` 字段防重入**——如 `collapse_drain_retry` 只触发一次（`query.ts:1092` 检查 `state.transition?.reason !== 'collapse_drain_retry'`）；`hasAttemptedReactiveCompact` 防 compact 死循环（`query.ts:1296`）。

**i. Dead code elimination 用 `feature('FLAG')`**（`bun:bundle`）——大量实验功能用 `feature()` 包裹，build 时 tree-shake 掉，让 query.ts 主体保持稳定可测。

## 11. 可借鉴要点

**对 Q-agent 编排层直接可借鉴**：

1. **`while(true)` + `state = {...next}` 整体覆写**的循环骨架——简洁且防状态泄漏；Q-agent 用 Python `async generator` + `dataclass(state)` 完全可以复刻
2. **`needsFollowUp` 单一续跑信号**——只要本轮有 tool_use 就 continue，否则进入收尾流程；比状态机简单
3. **工具批次分区**（`partitionToolCalls`）——连续并发安全工具合批并行，非并发安全单独串行；Q-agent 的 Bash/Edit 等可设 `is_concurrency_safe` 标志
4. **错误作为 tool_result 回喂而非抛出**——`<tool_use_error>` XML 块，LLM 自己决定重试，不中断循环
5. **多级压缩流水线**（按代价升级）——Q-agent 本地 LLM context 窗口小，microcompact（只清旧 tool_result）特别有用
6. **`maxResultSizeChars` + 落盘预览**——本地 LLM 尤其受不了大输出，必须裁剪
7. **流式工具执行**（边流式边执行）——减少"模型说完再执行"的串行等待
8. **Terminal 枚举集中定义**（`query/transitions.ts`）——所有退出原因一处声明，便于测试断言与日志分析
9. **`transition` 字段记录上次 continue 原因**——防重入死循环，Q-agent 用 Python Enum 可直接复刻
10. **`QueryDeps` 依赖注入**——测试时换 fake model / fake autocompact 极方便
11. **`canUseTool` 钩子 + `checkPermissions` 双层权限**——通用规则 + 工具自决，Q-agent 的 safety 模块可对应
12. **Memory prefetch 异步启动 + 零等待消费**——预取与主循环并行，settled 才用，未 settled 跳过

## 12. 不适合 Q-agent 借鉴的

1. **Coordinator 模式 + AgentTool 委派多 agent**——Q-agent 定位是单人桌面应用，本地 LLM 单卡跑一个 agent 都吃力，多 agent 并发会爆显存。`InProcessTeammateTask`、`RemoteAgentTask`、`DreamTask`、`LocalWorkflowTask` 整个体系都不需要
2. **Feature flag 矩阵**（`HISTORY_SNIP` / `REACTIVE_COMPACT` / `CONTEXT_COLLAPSE` / `CACHED_MICROCOMPACT` / `TOKEN_BUDGET` / `BG_SESSIONS` …）——这是 Anthropic 做 A/B 实验的产物，Q-agent 单人开发不需要这么多实验通道
3. **`task_budget` API beta**——依赖 Anthropic 服务端预算控制，本地 LLM 无此 API
4. **prompt cache 字节对齐**（`backfillObservableInput` 不污染原 input）——Anthropic API 才有 prompt caching，本地 LLM 没有缓存命中优化需求
5. **`StreamingToolExecutor` 的复杂性**（discard / siblingAbortController / tombstone）——为 fallback 模型切换设计，Q-agent 单模型不需要；用简单的"收集 tool_use 块 → 批次执行"即可
6. **`reactiveCompact` / `contextCollapse`**——都是为 Claude 200K context 窗口优化的高级策略，Q-agent 本地 LLM 窗口通常 8K-32K，microcompact + autocompact 两级足够
7. **sidechain transcript + `--resume` 子 agent**——多 agent 才需要，Q-agent 单 agent 直接主 transcript
8. **`coordinator/coordinatorMode.ts` 的 worker tool 白名单机制**——基于多 agent 委派，Q-agent 不适用
9. **`processUserInput` 处理 slash 命令的复杂分支**（local_command_stdout / compact_boundary / queued_command 多种 attachment 类型）——Q-agent 的 slash 命令可以走更简单的"预处理 → 修改 messages → 进入 loop"两步流程
10. **大量 analytics 事件埋点**（`tengu_*` 系列 logEvent）——Anthropic 内部数据驱动，Q-agent 不需要这层
11. **`InProcessTeammateTask` 的 `AsyncLocalStorage` 隔离**——Node.js 特性，Python 用 `contextvars` 可模拟但 Q-agent 不需要多 teammate
12. **`fileHistoryMakeSnapshot` / `commitAttribution`**——为 git 工作流设计，Q-agent 不强依赖 git

---

**核心结论**：Claude Code 的编排层本质是"一个 `while(true)` 循环 + LLM 输出的 tool_use 块驱动 + 多级压缩兜底 + 严格的不抛异常原则"。Q-agent 应借鉴其**循环骨架 + 错误回喂 + 多级压缩 + 工具批次调度**，砍掉**多 agent 协作 + feature flag 矩阵 + prompt cache 优化**。