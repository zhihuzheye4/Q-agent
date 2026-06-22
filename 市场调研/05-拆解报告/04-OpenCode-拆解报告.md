# OpenCode 编排调度层拆解报告

## 1. 项目概况

OpenCode（github.com/sst/opencode）是 TypeScript 实现的开源 AI coding agent，定位为可对接多家 LLM provider（Anthropic / OpenAI / Google / Copilot / Kimi / Trinity / GitLab Workflow 等）的交互式 CLI 工具，可由 TUI / HTTP server / MCP / ACP 多种前端驱动。

- 语言构成：TypeScript 68% + MDX 27%，MIT 协议
- 架构风格：完全构建在 [Effect](https://effect.website) 框架之上——服务定义用 `Context.Service` / `Layer.effect` / `Layer.provide`，依赖通过 `yield* SomeService` 注入；所有副作用（LLM 调用、数据库、文件、子进程、事件总线）都被 Effect 的 Stream / Effect / Layer / Scope 包裹。这带来三个直接结果：
  1. 服务组合是核心解耦手段——每个能力（`Permission` / `Session` / `LLM` / `Agent` / `Plugin` / `Provider` / `SessionCompaction` / `SessionProcessor` / `SessionRunState`）都是一个 Service，在 `defaultLayer` 中显式声明依赖图（见 `packages/opencode/src/session/prompt.ts:1540-1573`）。
  2. 中断语义由 Effect 内建——`Effect.onInterrupt` / `Effect.retry` / `Deferred` / `Latch` 等天然用于取消、超时、并发控制。
  3. 持久化用 SQLite（drizzle-orm），消息流即事件流，`Session.updatePart`/`updateMessage` 写库，前端通过 `EventV2Bridge` 订阅。
- 整体模块划分（`packages/opencode/src/`）：
  - `agent/` — 8 个内置 agent 定义、subagent 权限派生
  - `session/` — 编排调度核心：`prompt.ts` 主循环、`processor.ts` 流处理、`compaction.ts` 上下文裁剪、`llm.ts` provider 路由、`message-v2.ts` 数据模型、`tools.ts` 工具装配、`run-state.ts` 运行状态机、`retry.ts` 重试策略、`reminders.ts` 提醒注入、`system.ts` 系统提示词、`instruction.ts` / `summary.ts` / `title.ts` / `revert.ts` 等辅助
  - `provider/` — provider 抽象（auth/error/model-status/transform）
  - `tool/` — 工具定义（shell/edit/read/write/glob/grep/task/webfetch/...）+ `registry.ts`
  - `permission/` — glob 模式 + allow/ask/deny 三态权限
  - `bus/` — 全局 EventEmitter（`bus/global.ts`，仅 22 行，事件主线实际由 `EventV2Bridge` 承担）
  - `command/` / `skill/` / `plugin/` / `mcp/` / `lsp/` / `server/` / `cli/` / `config/` / `question/` / `snapshot/` / `background/` / `worktree/` / `sync/` / `share/` / `acp/` 等支撑模块

## 2. 编排调度层定位

OpenCode 的编排调度层集中在 `packages/opencode/src/session/`，并由 `agent/` + `provider/` + `permission/` + `tool/` 作为四翼支撑。其中：

- **`session/prompt.ts`** — 编排调度层的入口和总指挥。1707 行，定义 `SessionPrompt.Service`（接口在 `prompt.ts:86-93`），对外暴露 `prompt` / `loop` / `shell` / `command` / `cancel` / `resolvePromptParts` 六个能力。`SessionPrompt.loop`（`prompt.ts:1389-1393`）是主 agentic 循环的外层入口，它把工作委托给 `state.ensureRunning` + `runLoop`。
- **`session/processor.ts`** — 单步 LLM 流处理引擎。1084 行，定义 `SessionProcessor.Service`（`processor.ts:90`），每轮 LLM 调用创建一个 `Handle`（`processor.ts:38-54`），消费 `LLMEvent` 流，把文本增量 / reasoning / tool-call / tool-result / step-finish 写入数据库并发布事件。
- **`session/llm.ts`** — provider 路由与运行时选择。415 行，`LLM.Service`（`llm.ts:58`）对外只暴露一个 `stream(input)` 方法，内部根据 `flags.experimentalNativeLlm` 在 `LLMNativeRuntime` 与 `LLMAISDK`（默认）之间切换（`llm.ts:226-281`），并处理 GitLab Workflow 等需要 WebSocket 工具回传的 provider。
- **`session/compaction.ts`** — 上下文裁剪。620 行，`SessionCompaction.Service`（`compaction.ts:162`）提供 `isOverflow` / `prune` / `process` / `create` 四个方法。
- **`session/run-state.ts`** — 运行状态机。157 行，`SessionRunState.Service`（`run-state.ts:27`）维护每个 session 的 `Runner`，提供 `ensureRunning` / `startShell` / `cancel` / `assertNotBusy`，是中断与并发控制的中枢。
- **`session/tools.ts`** — 工具装配。207 行，`SessionTools.resolve`（`tools.ts:24`）把 `ToolRegistry` 中的内置工具 + MCP 工具 + 当前 agent 的权限 + processor handle 的更新回调，统一打包成 AI SDK 的 `AITool` 字典。
- **`session/message-v2.ts`** — 数据模型与消息流。747 行，定义 `MessageV2` / `filterCompacted` / `latest` / `parts` / `fromError` 等，是 session 状态的单一事实源。
- **`agent/agent.ts`** — 8 个内置 agent 的定义和权限默认值（`agent.ts:138-263`）。
- **`provider/provider.ts`** — 1975 行的 provider 大本营，封装每家 LLM 的差异。
- **`permission/index.ts`** — 230 行的 glob 权限引擎。

`SessionPrompt` 在其中的角色：**编排调度层的总指挥**。它不直接实现 LLM 流处理、工具执行、上下文裁剪、权限决策等细节，而是通过 25 个注入的 Service（`prompt.ts:100-126`）把这些能力组合起来，由它决定"这一步该做什么"——是 subtask 委派、还是 compaction、还是发起一轮新的 LLM 流、还是退出循环。

## 3. Planner 实现

OpenCode **没有显式的 Planner 模块**。Planner 的职责被三件事共同承担：

1. **LLM 自己决定工具调用**——默认 agent 是 `build`，工具集由 `SessionTools.resolve` 动态装配（`prompt.ts:1279-1293`），LLM 通过 AI SDK 的 tool-calling 协议直接产出 `tool-call` 事件，没有中间结构化意图层。
2. **`plan` agent + plan-mode prompt**——只读规划模式（`agent.ts:154-179`）通过禁止 edit/write 工具 + 注入 `PROMPT_PLAN`（`reminders.ts:28-36`）实现。`plan` agent 的 `permission` 显式 `edit: { "*": "deny" }`，并允许写入 `.opencode/plans/*.md`。规划结果是一份 markdown 计划文件，不是结构化意图。
3. **`MAX_STEPS_PROMPT` 软截止**——当 `step >= agent.steps`（`prompt.ts:1231-1232`），向 messages 追加一条 assistant 预填充 `MAX_STEPS_PROMPT`（`prompt.ts:1327`），提示模型该收尾了。这是用 prompt 而非硬终止来实现的"步数规划"。

`SessionPrompt.runLoop` 在每轮循环开始时根据 `MessageV2.latest(msgs)` 返回的 `tasks`（`message-v2.ts:599-614`）派发：
- `task.type === "subtask"` → `handleSubtask`（`prompt.ts:1197-1200`）委派给子 agent
- `task.type === "compaction"` → `compaction.process`（`prompt.ts:1202-1212`）
- 否则走 LLM 流（`prompt.ts:1266-1376`）

`tasks` 的来源是 user message 上挂的 `SubtaskPart` / `CompactionPart`——即"待执行的编排动作"以 part 形式存在消息流里，由 `MessageV2.latest` 从未被最新 finished assistant 处理过的 part 中提取。这是 OpenCode 编排层的"轻量 Planner"：意图不是独立模块产出的，而是用户消息 / LLM 工具调用 / 自动 overflow 检测共同往消息流里塞 part，`runLoop` 在每轮消费。

## 4. Orchestrator 实现

`SessionPrompt.runLoop`（`prompt.ts:1134-1387`）就是 Orchestrator，一个 `while (true)` 循环，每轮做 6 件事：

1. **加载消息流**：`MessageV2.filterCompactedEffect(sessionID)`（`prompt.ts:1145-1147`）从 SQLite 读出全部消息，按 compaction 重排（`message-v2.ts:588-590` 的 `filterCompacted`），返回 `SessionV1.WithParts[]`。
2. **计算最新状态**：`MessageV2.latest(msgs)`（`prompt.ts:1149`）返回 `{ user, assistant, finished, tasks }`。
3. **判断循环终止**（见第 8 节）：`lastAssistant.finish` 非 tool-calls/unknown 且没有未完成的 tool calls 且 `lastUser.id < lastAssistant.id` → `break`（`prompt.ts:1164-1183`）。
4. **派发 task**（`prompt.ts:1195-1221`）：subtask → `handleSubtask`；compaction → `compaction.process`（result === "stop" 则 break）；自动 overflow 检测（`compaction.isOverflow`）→ `compaction.create` + continue。
5. **组装工具 + 发起 LLM 流**：`SessionTools.resolve(...)` 装配 `tools` 字典（`prompt.ts:1279-1293`），`SystemPrompt.environment` / `skills` + `Instruction.system` 拼系统提示（`prompt.ts:1309-1317`），`handle.process(...)`（`prompt.ts:1318-1332`）启动 `SessionProcessor.process`。
6. **根据 `result` 决定下一步**（`prompt.ts:1334-1381`）：structured output 已捕获 → break；`finish === "content-filter"` → 报错 break；`result === "stop"` → break；`result === "compact"` → 触发 compaction；`result === "continue"` → 进入下一轮。

`SessionProcessor.process`（`processor.ts:960-1034`）是单步 Orchestrator：它 `Stream.tap(handleEvent)` 把 LLM 事件分流到 `text-start` / `text-delta` / `text-end` / `reasoning-*` / `tool-input-*` / `tool-call` / `tool-result` / `tool-error` / `step-start` / `step-finish` / `finish` 处理器（`processor.ts:371-844`），并在 `Stream.takeUntil(() => ctx.needsCompaction)` 处提前中断（`processor.ts:978`），最后 `Effect.retry(SessionRetry.policy(...))` 包装重试策略（`processor.ts:994-1025`），`Effect.catch(halt)` 处理致命错误（`processor.ts:1026`），`Effect.ensuring(cleanup())` 保证资源回收（`processor.ts:1027`）。

`runLoop` 的"步调度"由 `step` 计数器驱动（`prompt.ts:1138, 1185`），`step === 1` 时异步 fork 出 `title` 生成和 `summary.summarize`（`prompt.ts:1186-1192, 1304-1305`），不阻塞主循环。

## 5. 工具调用循环

完整流程（一个 step 内部）：

1. **LLM 流产出 tool-input-start**：`SessionProcessor.handleEvent` 的 `tool-input-start` 分支（`processor.ts:427-432`）调用 `ensureToolCall`（`processor.ts:295-346`），在 SQLite 中创建一个 `status: "pending"` 的 `ToolPart`，并记录 `callID` 到 `ctx.toolcalls`。
2. **LLM 增量产出工具参数**：`tool-input-delta`（`processor.ts:434-449`）累积 `raw` 字符串，并通过 `events.publish(SessionEvent.Tool.Input.Delta, ...)` 推到前端。
3. **LLM 结束工具输入**：`tool-input-end`（`processor.ts:451-466`）标记 `inputEnded = true`。
4. **LLM 发出 tool-call**：`tool-call` 分支（`processor.ts:468-547`）——`ensureToolCall` 拿到 part，`updateToolCall` 把 part 状态从 pending 改为 running 并写入 `input`（`processor.ts:503-517`）；同时做 **doom loop 检测**（`processor.ts:519-546`）——如果最近 `DOOM_LOOP_THRESHOLD = 3` 个 part 都是同一个工具 + 同一输入，向 `permission.ask` 抛 `doom_loop` 权限请求，强制人工确认。
5. **AI SDK 执行工具**：工具实际执行不在 `processor.ts` 中，而是在 `SessionTools.resolve` 装配的 `tool({ execute(args, options) { return run.promise(Effect.gen(...)) } })` 里（`tools.ts:80-115`）。AI SDK 在收到 `tool-call` 后异步调用 `execute`，效果流回灌为 `tool-result` 事件。
6. **工具执行体**（`tools.ts:83-112`）：
   - 触发 `plugin.trigger("tool.execute.before", ...)`（`tools.ts:87-91`）
   - 调用 `item.execute(args, ctx)`——`ctx` 由 `tools.ts:41-72` 构造，包含 `sessionID` / `abort` / `messageID` / `callID` / `agent` / `messages` / `metadata` 回调 / `ask` 权限回调
   - 触发 `plugin.trigger("tool.execute.after", ...)`（`tools.ts:102-106`）
   - 若 `abortSignal.aborted` 则 `completeToolCall`（`tools.ts:107-109`）
   - 返回 `output`（含 `title` / `metadata` / `output` / `attachments`）
7. **LLM 流产出 tool-result**：`tool-result` 分支（`processor.ts:549-647`）——若 `result.type === "error"` 则 `failToolCall`（`processor.ts:569`）；否则 `toolResultOutput` 提取 `output/metadata/title/attachments`，对 image attachments 调 `image.normalize`（`processor.ts:573-583`），最后 `completeToolCall`（`processor.ts:645`）把 part 状态改为 completed 并写入 SQLite。
8. **结果回喂给 LLM**：下一轮 `runLoop` 时 `MessageV2.filterCompactedEffect` 重新读 SQLite，tool part 已是 completed 状态，`MessageV2.toModelMessagesEffect` 把 tool result 转成 AI SDK 的 `tool-result` role message，LLM 在下一轮看到工具结果继续生成。

关键细节：**工具执行与 LLM 流并发**。AI SDK 在 `streamText` 内部异步执行工具，opencode 的 `Stream.tap(handleEvent)` 在事件到达时处理——tool-call 事件先到（登记 part 为 running），tool-result 事件后到（登记 part 为 completed），LLM 边接收边继续生成。这就是为什么 `ctx.toolcalls[callID].done` 是 `Deferred`（`processor.ts:338`）——`cleanup` 时 `Deferred.await` 等待 250ms（`processor.ts:879-883`）让在飞工具完成。

## 6. 上下文管理

`SessionCompaction`（`compaction.ts`）承担上下文管理，触发时机有三：

1. **自动 overflow**：每轮 `step-finish` 后 `processor.ts:750-755` 检查 `isOverflow({ cfg, tokens: usage.tokens, model })`（`overflow.ts:22-34`）——`tokens.total >= usable(model, cfg)` 时 `ctx.needsCompaction = true`，`Stream.takeUntil` 让流提前结束（`processor.ts:978`），`process` 返回 `"compact"`（`processor.ts:1030`）。`runLoop` 收到后 `compaction.create({ auto: true, overflow: !handle.message.finish })`（`prompt.ts:1366-1374`），continue 下一轮。下一轮 `latest.tasks` 弹出 compaction task → `compaction.process`（`prompt.ts:1202-1212`）。
2. **手动 /compaction**：用户命令直接调 `compaction.create({ auto: false })`。
3. **历史过大首次进入**：`runLoop` 主动检测 `lastFinished` 且 `compaction.isOverflow` → `compaction.create({ auto: true })`（`prompt.ts:1214-1221`）。

**压缩流程**（`compaction.ts:299-552`）：
- `select`（`compaction.ts:198-249`）：把消息按 user 消息切成 `turns`，保留最后 `tail_turns`（默认 2，`compaction.ts:42`）轮作为"tail"——这部分不进 compaction summary，原样回放给 LLM。`preserveRecentBudget`（`compaction.ts:90-95`）按 `min(8000, max(2000, usable*0.25))` 计算保留预算，`splitTurn`（`compaction.ts:115-138`）在 budget 不够时切分单轮。
- `buildPrompt` + `plugin.trigger("experimental.session.compacting", ...)`（`compaction.ts:353-358`）构造请求 prompt。
- 用 `compaction` agent（hidden，`agent.ts:217-231`）调 `processor.process` 生成 summary（`compaction.ts:404-424`）。
- 失败时（`result === "compact"`）抛 `ContextOverflowError`（`compaction.ts:426-435`）。
- 成功时若 `auto` 且有 `replay`（overflow 场景下被截掉的最后一条 user message），把原 user message 重新写入（`compaction.ts:445-471`），让用户请求不丢失。
- 若 auto 但无 replay，经 `experimental.compaction.autocontinue` plugin 决定是否注入"Continue if you have next steps"的 synthetic user part（`compaction.ts:473-525`）。

**恢复流程**：`MessageV2.filterCompacted`（`message-v2.ts:588-590`）在每轮 `runLoop` 开始时被调用，它把消息重排为 `[compaction-user, summary, ...retained tail, continue-user]`——compaction summary 当作 user 角色注入，后续 tail 原样保留，让 LLM 既看到历史摘要又不丢失最近上下文。

**Prune 机制**（`compaction.ts:253-297`）：`PRUNE_MINIMUM = 20000` / `PRUNE_PROTECT = 40000` token 阈值，倒序扫描消息，保留最近 40K token 的 tool 输出，更老的 tool 输出把 `state.time.compacted = Date.now()` 标记为已压缩（不删除，只是 LLM 消费时被 strip）。`skill` 工具受 `PRUNE_PROTECTED_TOOLS` 保护不裁剪。

## 7. 错误处理 & 降级

错误处理分四层：

1. **LLM 流错误**：`SessionProcessor.process` 用 `Effect.retry(SessionRetry.policy(...))`（`processor.ts:994-1025`）。`SessionRetry.policy`（`retry.ts:176-199`）通过 `Schedule.fromStepWithMetadata` 判断每次错误是否可重试：`retryable(error, provider)`（`retry.ts:68-152`）识别 5xx / rate limit / `FreeUsageLimitError` / `GoUsageLimitError` / `Overloaded` / `too_many_requests` 等模式；`delay(attempt, error)`（`retry.ts:35-66`）支持 `retry-after-ms` / `retry-after` HTTP 头，指数退避 `2000 * 2^(attempt-1)`，上限 30s（无 headers）或 2^31 ms（有 headers）。`ContextOverflowError` 显式不重试（`retry.ts:70`）。重试时通过 `set` 回调把状态推到 `SessionStatus`（`processor.ts:1001-1023`），前端可见"正在重试"。
2. **致命错误**：`Effect.catch(halt)`（`processor.ts:1026`）调到 `halt`（`processor.ts:917-958`）：`ContextOverflowError` + auto compaction 开启 → `ctx.needsCompaction = true`，事件层报错但不终止；其他错误 → `ctx.assistantMessage.error = parse(e)` 写库，发 `Session.Event.Error`，`status.set(idle)`。
3. **工具错误**：`tool-result` type=error（`processor.ts:549-571`）或 `tool-error`（`processor.ts:649-671`）都走 `failToolCall`（`processor.ts:229-246`）——把 part 状态改为 `error`，写 `errorMessage(error)`，`PermissionV1.RejectedError` / `Question.RejectedError` 额外设 `ctx.blocked = ctx.shouldBreak`。工具失败不终止循环，LLM 下一轮看到 tool-result(error) 自己决定要不要重试或换路。`experimental_repairToolCall`（`llm.ts:296-312`）让 AI SDK 在工具名大小写错误时改写为小写重试，否则改写 input 为 `{ tool, error }` 喂给 `invalid` 工具。
4. **provider 切换**：`LLM.run` 根据 `flags.experimentalNativeLlm` 选择 native runtime 或 ai-sdk runtime（`llm.ts:226-281`）。Native 不可用时打印日志并 fallback 到 ai-sdk，不抛错。模型不存在时 `SessionPrompt.getModel`（`prompt.ts:595-613`）捕获 `Provider.ModelNotFoundError` 并发 `Session.Event.Error` 提示建议模型名。
5. **网络失败**：依赖 `SessionRetry.policy` 的 HTTP 错误识别 + `maxRetries: input.retries ?? 0`（`llm.ts:323`）双层保护。AbortController 在 `Stream.scoped` 中获取（`llm.ts:361-364`），scope 释放时自动 `ctrl.abort()`，保证中断立即生效。

`doom_loop` 防护（`processor.ts:519-546`）是 OpenCode 独特设计——连续 3 次相同工具相同输入就强制 `permission.ask`，让用户决定是否继续。`Permission.Service.ask` 通过 `Deferred.await` 阻塞 LLM 流，等用户 `Permission.reply` 后才放行（`permission/index.ts:78-118`）。

## 8. 循环终止条件

`SessionPrompt.runLoop` 的 `while (true)` 在以下情况 `break`（`prompt.ts:1141-1382`）：

1. **LLM 自然终止**：`lastAssistant.finish` 非 `"tool-calls"` / `"unknown"` 且没有未完成 tool calls 且 `lastUser.id < lastAssistant.id`（`prompt.ts:1164-1183`）。`finish` 值由 `processor.ts:693-757` 的 `step-finish` 事件设置——AI SDK 的 `value.reason` 直接传过来（`stop` / `length` / `content-filter` / `tool-calls` / `error` / `unknown` 等）。
2. **Structured output 已捕获**：`structured !== undefined` 时 break（`prompt.ts:1334-1339`）。`StructuredOutput` 工具（`prompt.ts:1645-1671`）的 `onSuccess` 回调设值。
3. **content-filter**：`finish === "content-filter"` 写错并 break（`prompt.ts:1347-1354`）。
4. **Structured 输出失败**：模型没调 StructuredOutput 工具但 format 是 json_schema → 抛 `StructuredOutputError` 并 break（`prompt.ts:1355-1363`）。
5. **Processor 返回 stop**：`result === "stop"`（`processor.ts:1031-1032`）由 `ctx.blocked`（permission rejected）或 `ctx.assistantMessage.error` 触发，`prompt.ts:1365` 处 break。
6. **Compaction 返回 stop**：`compaction.process` 返回 `"stop"`（`compaction.ts:428-434`，ContextOverflowError 无救）时 `prompt.ts:1210` 处 break。
7. **Max steps 软终止**：`step >= agent.steps` 时 `isLastStep = true`，向 LLM messages 追加 assistant 预填充 `MAX_STEPS_PROMPT`（`prompt.ts:1231-1232, 1327`）提示模型收尾，但不硬 break——模型若仍调 tool-call 则继续，若 `finish === "stop"` 则走自然终止路径。
8. **用户取消**：`SessionPrompt.cancel`（`prompt.ts:136-139`）调 `state.cancel(sessionID)`，`SessionRunState.cancel`（`run-state.ts:77-86`）取消 `Runner`，触发 `Effect.onInterrupt`（`processor.ts:982-989`）→ `halt(new DOMException("Aborted", "AbortError"))` → `ctx.assistantMessage.error` 写入 `aborted: true` → `process` 返回 stop → `runLoop` break。`finalizeInterruptedAssistant`（`prompt.ts:1256-1264`）确保中断后 message 写入 `time.completed`。

`step` 计数无硬上限——`agent.steps ?? Infinity`（`prompt.ts:1231`）默认无限。`build` / `general` / `explore` 等都没设 steps，只有用户在 config 里给特定 agent 配 `steps` 才生效。

循环结束后 `compaction.prune` 异步 fork（`prompt.ts:1384`），最终 `lastAssistant(sessionID)` 返回最新 assistant message 作为 loop 结果。

## 9. 多 Agent 协作

OpenCode 内置 8 个 agent（`agent.ts:138-263`）：

- **`build`**（primary, native）：默认 agent，可执行所有工具，`question` / `plan_enter` 默认 allow。
- **`plan`**（primary, native）：只读规划模式，`edit: { "*": "deny" }` 只允许写 `.opencode/plans/*.md`，`task: { general: "deny" }` 禁止委派给 general subagent。
- **`general`**（subagent, native）：通用研究 + 多步执行 agent，`todowrite: "deny"`。
- **`explore`**（subagent, native）：代码库探索专家，`*: "deny"` 只开 grep/glob/list/bash/webfetch/websearch/read + 只读 external_directory。
- **`compaction`**（primary, native, hidden）：上下文压缩专用 agent，`*: "deny"` 没有任何工具，只生成 summary 文本。
- **`title`**（primary, native, hidden）：生成会话标题，`temperature: 0.5`，`*: "deny"`。
- **`summary`**（primary, native, hidden）：生成 session summary。

agent 配置可在 `opencode.json` 的 `agent` 字段覆盖（`agent.ts:265-292`）——禁用、改 model / prompt / mode / temperature / steps / permission。

**subagent 委派机制**：

1. **触发方式**：用户在 prompt 里 `@explore 帮我找...`（`prompt.ts:957-973` 的 `resolvePart` 把 `agent` part 转成"Use the above message and context to generate a prompt and call the task tool with subagent: explore"的 synthetic text part）；或 LLM 主动调 `task` 工具（`tool/task.ts:81-346`）传入 `subagent_type`。
2. **权限校验**：`Permission.evaluate("task", part.name, ag.permission)`（`prompt.ts:958`）——只有 agent 的 permission 里 `task` 规则有 `allow`/`ask` 才能委派。`build` 默认 `task: "allow"`，`plan` 默认 `task: { general: "deny" }`（只禁 general）。
3. **子 session 创建**：`TaskTool.execute`（`task.ts:92-334`）调 `sessions.create({ parentID: ctx.sessionID, agent: next.name, permission: childPermission })`（`task.ts:142-158`），`childPermission = deriveSubagentSessionPermission({ parentSessionPermission, subagent })`（`task.ts:125-128` + `agent/subagent-permissions.ts:14-27`）——继承 parent 的 deny + external_directory 规则，并默认禁 `todowrite` / `task`（除非 subagent 自己开）。
4. **执行**：`ops.prompt({ sessionID: nextSession.id, agent: next.name, parts })`（`task.ts:186-200`）——这是关键设计：子 agent 通过调用父 session 的 `SessionPrompt.prompt` 走自己的 `runLoop`，因此 subagent 也有完整的循环 / 工具 / compaction 能力。
5. **结果回传**：子 session 的最后一条 text part 作为 task tool 的 `output`（`task.ts:199`），以 `<task id="..." state="completed"><task_result>...</task_result></task>` 格式（`task.ts:64-79`）回灌给父 LLM。
6. **前台 / 后台**：`params.background === true` 时（`task.ts:97-101, 291-294`）走 `BackgroundJob.start` 异步执行，立即返回"Background task started"，完成时通过 `background.wait` + `inject` 把结果作为新的 user message 注入父 session（`task.ts:202-240, 259-289`）。前台则 `background.wait` 阻塞等结果（`task.ts:303-322`）。
7. **取消传播**：父 session cancel 时 `cancelBackgroundJobs`（`run-state.ts:116-148`）递归取消所有子 background job——通过 `metadata.sessionId` / `metadata.parentSessionId` 匹配。

**`permission.task` glob 控制**：`Permission.evaluate`（`permission/index.ts:39-49`）按 `rule.permission` 和 `rule.pattern` 双 glob 匹配，`findLast` 取最后一条匹配规则——agent 配置里 `task: { general: "deny", "*": "allow" }` 表示禁 general 但允许其他 subagent。`permission.ruleset` 是 `Rule[]`，规则顺序就是优先级（后覆盖前）。`Permission.merge(...rulesets)` 直接 flat 拼接（`permission/index.ts:211-213`），所以 `defaults` + `agent.config` + `user.config` 三层规则拼起来，靠 `findLast` 决定最终 action。

## 10. 关键设计取舍

1. **Effect 框架 + 服务组合**：所有副作用统一为 `Effect`，服务通过 `Context.Service` + `Layer.effect` 声明，依赖图在 `defaultLayer` 显式拼装（`prompt.ts:1540-1573`）。优点是依赖注入显式、中断语义内建、类型推导强；代价是学习曲线陡峭，每个 Service 都要写 `Layer.provide` 链。
2. **SQLite 持久化 + 事件流双写**：消息和 part 全部写 SQLite（`Session.updateMessage` / `updatePart`），同时通过 `EventV2Bridge` 发事件给前端。`experimentalEventSystem` flag 控制"双写"——旧 v1 模型 + 新 v2 事件并存，迁移期靠 `if (flags.experimentalEventSystem)` 分流（如 `prompt.ts:1077-1099`）。代价是代码冗余、状态分散。
3. **AI SDK 优先 + Native runtime 抽象**：默认走 `streamText` from `ai` 包，`LLMAISDK.toLLMEvents` 把 `fullStream` parts 转成统一 `LLMEvent`（`llm.ts:372-378`）。`experimentalNativeLlm` flag 启用 `LLMNativeRuntime`（`llm.ts:226-268`）直接走 `@opencode-ai/llm` 的 `LLMClient`，跳过 AI SDK，用于 GitLab Workflow 等 WebSocket-based provider。这是 OpenCode 抽象 provider 差异的核心取舍——保留 AI SDK 的工具调用 / 修复 / streaming 协议作为基线，但允许特殊 provider 完全旁路。
4. **Glob 权限引擎**：`Permission` 用 `Wildcard.match` + `findLast` 实现"后规则覆盖前规则"，三层规则（defaults + agent config + user config）flat merge。简单但表达力强——`read: { "*.env": "ask", "*.env.example": "allow" }` 这种细粒度模式天然支持。代价是规则数量随配置增长，匹配 O(n)。
5. **Subagent = 子 session**：subagent 不复用父 session，而是 `sessions.create({ parentID })` 起独立 session。好处是子 agent 有自己的消息流 / compaction / 权限 / cancel 作用域；代价是跨 session 上下文不共享，结果只能通过 task tool output 文本回传（结构化数据要靠 LLM 自己从文本里解析）。
6. **Compaction = 独立 agent + 消息重排**：compaction 不是隐藏机制，而是一个 hidden agent 跑一次普通 LLM 流，产出 summary assistant message。`MessageV2.filterCompacted` 在每轮读取时把消息重排为 `[compaction-user, summary, tail, continue-user]`，让 LLM 把 summary 当作历史。这是把"上下文管理"降维成"特殊 agent + 消息变换"的优雅做法，代价是重排逻辑分散在 `filterCompacted` / `latest` / `select` 三处，理解成本高。
7. **MDX 文档即系统提示**：`packages/opencode/src/session/prompt/*.txt` 是 14 份针对不同 provider 的系统提示（anthropic / beast / codex / copilot-gpt-5 / default / gemini / gpt / kimi / trinity / plan-mode 等），`SystemPrompt.provider(model)` 按 `model.api.id` 字符串匹配选择（`system.ts:25-39`）。简单粗暴但意味着每加一家 provider 要加一份 .txt。
8. **Plugin 钩子贯穿全链**：`plugin.trigger("tool.execute.before", ...)` / `"experimental.chat.messages.transform"` / `"experimental.session.compacting"` / `"experimental.text.complete"` / `"shell.env"` 等钩子散布在 prompt / processor / compaction / llm 各处，是 OpenCode 扩展性的主要出口。

## 11. 可借鉴要点

对 Q-agent 编排层设计有直接参考价值的部分：

1. **`runLoop` 单循环 + `latest(msgs)` 派发**（`prompt.ts:1141-1382`）：用一个 `while (true)` 循环 + 消息流状态派发 subtask / compaction / LLM step，比状态机更灵活，比递归更可控。Q-agent 的 Planner + Orchestrator 可以借鉴这种"每轮根据消息流最新状态决定下一步动作"的模式。
2. **`SessionProcessor.process` 单步处理 + `Stream.tap(handleEvent)`**（`processor.ts:960-1034`）：把 LLM 流的多种事件（text / reasoning / tool-input / tool-call / tool-result / step-finish）分流处理，是 Python 侧 `LLMClient.stream()` + `for event in stream` 的天然映射。Q-agent 可直接复用这个模式——`handleEvent(event)` 就是个大 switch，每个事件类型一个 handler。
3. **`MessageV2.latest(msgs)` 返回 `{ user, assistant, finished, tasks }`**（`message-v2.ts:599-614`）：把"待处理任务"定义为"在最新 finished assistant 之后的 compaction/subtask parts"——这是 OpenCode 编排层的关键洞察：**编排动作以 part 形式存在消息流里，由消息流状态决定下一步**。Q-agent 可以用类似设计把 planner 决策嵌入消息流，而非维护独立的任务队列。
4. **`SessionCompaction` 的 tail 保留策略**（`compaction.ts:198-249`）：保留最后 N 轮原样 + 较老历史压缩成 summary，避免"压缩完丢失最近上下文"的问题。`preserveRecentBudget` 按模型 context 25% 自适应（2000-8000 token），比硬编码 token 数更鲁棒。
5. **`SessionRetry.policy` 的 provider 感知重试**（`retry.ts:176-199`）：识别 5xx / rate limit / `retry-after` header，指数退避 + 上限。Q-agent 接本地 LLM 时可简化（基本无 rate limit），但接云端 provider 时这套策略直接可用。
6. **`doom_loop` 检测**（`processor.ts:519-546`）：连续 3 次相同工具相同输入强制人工确认，是 LLM agent 自循环防护的简单有效手段。
7. **`Permission.evaluate` 的双 glob + findLast + 三层 merge**（`permission/index.ts:39-49, 211-213`）：Q-agent 的"危险命令黑名单 + 项目根保护"可以升级为这种 glob 规则引擎——`bash: { "rm -rf *": "ask", "git push --force*": "ask" }` 比硬编码 if-else 灵活得多。
8. **`MAX_STEPS_PROMPT` 软截止**（`prompt.ts:1231-1232, 1327`）：用 assistant 预填充提示模型收尾，而非硬中断。Q-agent 本地 LLM 容易陷入循环，这种"prompt 收尾"比硬步数限制更优雅。
9. **`SessionRunState.Runner` 单 session 单 runner**（`run-state.ts:52-69`）：每个 session 一个 Runner，busy 时拒绝新请求，cancel 时统一杀——Q-agent 单人桌面应用可以简化为"一个会话一个 worker thread"，避免并发问题。
10. **`Agent.steps` 可配置**（`agent.ts:54`）：每个 agent 可独立配 `steps` 上限，`Infinity` 默认。Q-agent 可以让用户在配置里给特定 agent 设步数预算。
11. **subagent 通过 `@mention` 触发**（`prompt.ts:957-973`）：用户输入 `@explore ...` 自动转成 task tool 调用，是简洁的人机协作入口。
12. **`tool.execute.before/after` plugin 钩子**（`tools.ts:87-106`）：Q-agent 可用类似机制支持用户自定义工具前置 / 后置处理（如日志、审计、模拟）。

## 12. 不适合 Q-agent 借鉴的

1. **Effect 框架**：Q-agent 是 Python + PySide6，没有对应物。Effect 的 `Layer` / `Context.Service` / `Effect.gen` / `yield*` 风格强类型依赖注入，在 Python 侧用 `dataclass` + `__init__` 依赖注入或 `contextvars` 就够。强行移植 Effect 模式会让 Python 代码变得不 Pythonic。
2. **SQLite 持久化 + 事件流双写**：Q-agent 单人桌面应用，单会话单用户，无需 SQLite 持久化消息——内存里维护消息列表 + JSON/Markdown 落盘存档即可。事件总线（`EventV2Bridge`）可简化为 Qt 信号槽。
3. **HTTP server / ACP / sync / share**：Q-agent 是本地桌面工具，不需要多用户协同 / 远程同步 / 会话分享。OpenCode 的 `server/` / `acp/` / `sync/` / `share/` / `account/` / `auth/` / `installation/` 等模块应全部跳过。
4. **多 provider 抽象层**：Q-agent 本地 LLM 优先，云端按需启用且不硬编码云端 key。OpenCode 1975 行的 `provider/provider.ts` + `provider/transform.ts` + `provider/auth.ts` + `provider/model-status.ts` 大部分是为 20+ 家云端 provider 的差异填坑，Q-agent 只需一个 `LLMClient` 抽象（local / openai-compatible / anthropic 三种足够）。
5. **`EventV2Bridge` + 双写迁移**：v1/v2 双写是历史包袱，Q-agent 全新项目无需复制。
6. **`Plugin.Service` 全链钩子**：Q-agent 不需要插件系统——贴纸式开发原则下，扩展靠新增 widget 文件 + 一行挂载，不需要运行时插件加载。OpenCode 的 `plugin.trigger(...)` 散布在几十处，是高度可扩展但也是高度复杂的设计。
7. **BackgroundJob 后台 subagent**：Q-agent 单人桌面，subagent 后台执行意义有限（用户就一个，等结果就好）。OpenCode 的 `experimentalBackgroundSubagents` flag + `BackgroundJob` + WebSocket 通知机制对 Q-agent 过度设计。
8. **GitLab Workflow / DWS / WebSocket executor**：企业级特化逻辑，Q-agent 完全用不到。
9. **`permission` glob 引擎的 `ask` 三态**：Q-agent 用户不认识英文，"ask" 三态对单用户桌面应用是多余交互——直接 allow / deny + 危险命令黑名单 + 项目根保护就够（参考 CLAUDE.md 第五节基本安全规则）。OpenCode 的 230 行 `permission` 模块可压缩到 50 行 Python。
10. **`MCP.Service` + `LSP.Service`**：Q-agent 起步阶段零第三方依赖，MCP 协议接入可后期再加；LSP 集成属于 IDE 功能，与 Q-agent 定位（指令执行型 agent）不重叠。
11. **`compaction` agent + 消息重排**：Q-agent 本地 LLM 上下文窗口通常较小（8K-32K），compaction 是必要的，但 OpenCode 的"独立 hidden agent + filterCompacted 重排 + tail_turns 保留 + splitTurn + preserveRecentBudget"复杂组合对 Q-agent 过度。Q-agent 可以用更简单的"超过阈值就调本地 LLM 总结前 N 轮，拼接成一条 system message + 保留最近 K 轮"。
12. **8 个内置 agent**：Q-agent 起步只需要 1 个主 agent + 1 个 compaction agent + 1 个 title/summary agent（可选），不需要 plan / explore / scout / general 四种 subagent——这些细分对单人桌面工具是过度规划，用户分不清该用哪个。