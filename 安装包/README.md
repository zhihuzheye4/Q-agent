# 安装包

本目录存放 Q-agent 当前里程碑的可执行 `.exe` 文件。

## 规则

- **每完成一个可运行里程碑，必须生成一个 .exe 放到本目录**
- 子目录按版本号命名：`v0.0.5/`、`v0.0.6/` …
- 每个子目录内含 PyInstaller 打包产物（`Q-agent.exe`）
- `.exe` 二进制不入 git（已在 `.gitignore` 忽略），目录结构靠 `.gitkeep` + 本 README 保留
- **只保留最新一代**：每次打新版本时，删掉旧版本子目录，只留当前最新版本（2026-06-20 用户明确修改，避免冗余历史 .exe 占空间；版本演进历史靠下方"版本历史"表 + git log 即可）

## 打包命令（F 盘 venv 内执行）

**强制规则（CLAUDE.md 第十七节）**：每次打包必须严格从下方标准模板复制粘贴，不得手敲删参数。如需新增/修改参数，先更新本模板再复制执行。

```bash
F:/EnglishWenJian/claude-CeShi/claude-data/venv-qagent/Scripts/pyinstaller.exe \
  --distpath 安装包 \
  --workpath build \
  --name Q-agent \
  --onefile \
  --windowed \
  --clean --noconfirm \
  --add-data "q_agent/assets;q_agent/assets" \
  --hidden-import pynvml \
  --collect-all pynvml \
  --collect-all psutil \
  q_agent/cli.py
# 打包后把 安装包/Q-agent.exe 移到 安装包/v{版本}/Q-agent.exe
# 同时删除上一版子目录，只留当前最新
```

约束：
- `--onefile` 单文件 .exe，零外部依赖安装（CLAUDE.md 第二十节）
- `--windowed` 隐藏控制台窗口（GUI 应用）
- `--add-data "q_agent/assets;q_agent/assets"` 把 q_agent/assets/ 资源打包进 .exe（SVG 图标 + manifest.json）——**漏此参数会导致运行时 importlib.resources 找不到 SVG，tab 图标全部消失**（v0.0.12 教训）
- `--hidden-import pynvml` 显式声明 pynvml（nvidia-ml-py 包名 vs pynvml 模块名不一致，PyInstaller 自动检测可能漏）
- `--collect-all pynvml` + `--collect-all psutil` 把运行时依赖整体打包（含子模块/数据文件，符合 ADR-015 零外部依赖安装硬规则）
- 入口脚本 `q_agent/cli.py` 必须含 `if __name__ == "__main__":` 守护，否则 .exe 启动后不调 main()
- .exe 体积约 47MB（含 PySide6 + Qt 全套运行时 + psutil + pynvml）

## 版本历史

> 表保留所有版本的演进记录（commit + 说明），但 `.exe` 二进制只留当前最新。

| 版本 | 日期 | 对应 commit | 说明 |
|------|------|-------------|------|
| v0.0.1 | 2026-06-19 | e0d059b | UI 界面空壳版本：4 tab 切换 + 输入框/发送按钮 + 设置面板 + 工具栏 + 菜单栏。活的 UI 无实际功能。 |
| v0.0.2 | 2026-06-19 | 681b992 | UI 改进：tooltip 透明背景 + 气泡宽度 0.7→0.92 + Feather 齿轮 + 输入框 QLineEdit→QTextEdit 多行。 |
| v0.0.3 | 2026-06-19 | 7880653 | UI 改进：输入框动态高度（documentSizeChanged + [44,200] 钳制 setFixedHeight）。 |
| v0.0.4 | 2026-06-20 | 54abe5f | 第一个填充实际功能：模型下拉框 + 启动检测本地 Ollama（urllib + QThread 异步 + 失败占位项 + 刷新按钮）。 |
| v0.0.5 | 2026-06-20 | 1acc615 | UI 两项改进：下拉框本地/云端分组（QStandardItemModel disabled 分组头 + 3 家云端预置）+ AI 气泡模型名小标签。 |
| v0.0.6 | 2026-06-20 | 5cff4c3 | 架构补齐：llm 层对称骨架——OllamaClient(LLMClient) 子类 + cloud/{openai,anthropic,gemini}.py 三个 stub；安装包规则改为只留最新版本。 |
| v0.0.7 | 2026-06-20 | 6d631bf | 修复分类 bug：list_models() 返回 ModelEntry（含 is_remote），通过 Ollama /api/tags 的 remote_model/remote_host 字段区分真正本地模型 vs Ollama Cloud 转发模型；UI 下拉框改三组（本地 + Ollama Cloud + 云端预置）。 |
| v0.0.8 | 2026-06-20 | 10ae75e | 通过 Ollama 唤醒模型 + 流式批量刷新：填充 OllamaClient.chat_stream（POST /api/chat stream=true NDJSON 解析）+ ChatWorker QThread 后台跑流式（500字/500ms 混合批量刷新阈值，避免一秒一字崩溃）+ chat_page 接入真实调用（loading 状态 + pending AI 气泡 + 错误红色气泡）+ toolbar 暴露 model_group_changed 信号供云端预置禁用发送按钮。 |
| v0.0.9 | 2026-06-20 | 38dc057 | 内存释放 + 切换模型清空上下文 + 模型名颜色：release_model POST /api/generate keep_alive=0 卸载模型出 Ollama RAM + toolbar release_btn + ModelReleaseWorker + 确认弹窗；切换模型清空对话 + 居中灰色斜体系统提示气泡"模型已切换为 XXX，上下文已清空"（首次自动选择抑制保留初始问候）；8 色调色板按模型名 zlib.crc32 hash 取色（同一模型每次同色），新增 release-active.svg 图标。 |
| v0.0.10 | 2026-06-20 | _pending_ | 加载指示器：pending AI 气泡内嵌入 LoadingDots 自定义 QWidget，三个圆点依次上下跳动（iMessage 打字气泡风格），HSV 色相随时间流动 + 每点偏移 60 度形成流动彩虹渐变，alpha=180（~70% 透明度）与背景融合不刺眼；首个 chunk 到达时移除 LoadingDots，回复文本开始流入；QTimer 80ms tick，phase 1.6s 一周期。 |
| v0.0.11 | 2026-06-20 | _pending_ | release_model 卸载验证：调 POST /api/generate keep_alive=0 后轮询 GET /api/ps（默认 3 次，间隔 300ms）确认模型确实从加载列表移除，未卸载时抛 OllamaError 让 UI 给明确反馈；新增 _is_model_loaded 辅助函数；状态栏文案明确说明"API 验证通过，VRAM 已归还，任务管理器进程级 GPU 内存可能延迟显示"（解决用户疑惑"已释放但 GPU 占用还在"=Ollama 进程级 CUDA context 不立即归还 OS 的已知行为）。 |
| v0.0.12 | 2026-06-20 | c1d185f | 硬件监控曲线：sidebar 底部常驻 HardwareMonitor（QWidget 自绘），4 条折线 60s 历史实时显示 CPU%（蓝）/GPU 利用率%（绿）/VRAM%（紫）/RAM%（橙），1s 采样一次；引入 psutil + pynvml（nvidia-ml-py）两个运行时依赖（PyInstaller --collect-all 打包进 .exe，符合 ADR-015 零外部依赖安装硬规则）；HardwareMonitorWorker(QThread) 后台采集，sample_collected 信号回主线程触发重绘；无 NVIDIA 显卡时 GPU/VRAM 折线画灰色 N/A 占位横线（None 段断开不连线）；closeEvent 优雅停止 worker 避免线程悬挂；sidebar 从 QListWidget 改为 QFrame 容器（含 tab 列表 + HardwareMonitor），保留 tab_changed 信号；新增 ADR-026。 |
| v0.0.13 | 2026-06-20 | _未 commit，被 v0.0.14 覆盖_ | 治标不治本的尝试：修复 v0.0.12 sidebar 容器化改造遗留的 QSS 选择器失配（theme.py 4 处 `QListWidget#Sidebar` → `QListWidget#SidebarList` + 新增 `QFrame#Sidebar` 背景样式）。用户验证后 tab 大小恢复但**图标仍未出现 + tooltip 消失**——根因是 v0.0.12 打包命令漏 `--add-data` 导致 SVG 没进 .exe（独立低级错误）+ sidebar 容器化结构本身违反模块化原则。用户提出"模块化开发"哲学批评后，v0.0.13 治标方案被废弃，v0.0.14 治本回退。v0.0.13 的 QSS 选择器改动被 v0.0.14 反向覆盖（改回 `#Sidebar`），未单独 commit，仅作版本历史留痕。 |
| v0.0.14 | 2026-06-20 | _pending_ | **模块化重构治本回退**：① sidebar.py 恢复 v0.0.9 QListWidget 子类原貌（`class Sidebar(QListWidget)` + objectName="Sidebar" + 4 tab + 图标 + tooltip + tab_changed 信号，零内嵌 HardwareMonitor）；② main_window.py 新建 left panel（QWidget + QVBoxLayout：sidebar stretch=1 + hardware_monitor 底部固定 160px，整体 fixed 200px 宽放进水平布局左侧）——HardwareMonitor 改由 MainWindow 一行 `addWidget` 模块化挂载，sidebar 完全不碰；③ theme.py 4 处 QSS 选择器改回 `QListWidget#Sidebar`，删除 v0.0.13 新增的 `QFrame#Sidebar` 和 `QListWidget#SidebarList`；④ 打包命令严格按 README.md 标准模板（含 `--add-data "q_agent/assets;q_agent/assets"` + `--hidden-import pynvml` + `--collect-all pynvml/psutil`）——修复 v0.0.12 漏 `--add-data` 导致 SVG 图标消失的低级错误；⑤ CLAUDE.md 新增第二十一节"模块化开发原则"（既有模块永不动 + 新功能独立 widget + 父容器一行挂载 + 改既有类继承/objectName/公开接口 = 架构级改动触发第十九节先展示）+ 第十七节补充"打包命令必须严格从 README.md 复制粘贴，不得手敲删参数"；⑥ ADR-027 模块化开发原则 + ADR-028 v0.0.12 sidebar 容器化回退决策。测试 144 通过，84.25% 覆盖率，ruff/mypy strict 全绿。 |
| v0.0.15 | 2026-06-20 | _pending_ | **硬件监控独立窗口 + menu_bar 回调模式**：① 硬件监控从 left panel 底部常驻迁出 → 独立窗口（新文件 `q_agent/ui/hardware_monitor_window.py`：`HardwareMonitorWindow(QWidget)` + `MonitorCell(QWidget)` 2×3 网格 6 指标折线图），由 menu_bar "监控"菜单 triggered 弹出；② menu_bar.py 扩展公开接口：`__init__` 新增 `monitor_callback: Callable[[], None] | None` 参数（类比 Toolbar `status_callback` 注入模式）+ 新增 `_build_monitor_menu()` 方法（"打开监控"QAction Ctrl+M），不侵入既有 file/help 菜单；③ main_window.py 移除 left panel 中的 HardwareMonitor 挂载，left panel 仅剩 sidebar；新增 `_open_hardware_monitor()`（实例化 + show + raise，避免重复实例化）+ 持有 `_hw_window` 引用，closeEvent 优雅关闭；④ hardware_monitor.py 拆分：只保留 Worker + 常量 + METRICS + `collect_sample_sync`，HardwareMonitorWindow + MonitorCell 独立到新文件（符合模块化"独立 widget 文件"原则）；⑤ 指标扩展为 6 个：METRICS 增加 `cpu_temp`（Windows psutil 不支持 sensors_temperatures，永远 None，灰色 N/A 占位横线）+ `gpu_temp`（pynvml `nvmlDeviceGetTemperature(handle, 0)` 原生支持），温度与百分比数值范围 0-100 巧合一致可共用 y 轴；MonitorCell 按 unit 字段切换数值显示格式（`f"{last:.0f}%"` vs `f"{last:.0f}°C"`）；⑥ ADR-029 硬件监控独立窗口 + menu_bar 回调模式（取代 ADR-026 中"sidebar 底部常驻挂载"部分，ADR-026 其余指标/数据源/采样/容错决策保留）。测试 148 通过，84.39% 覆盖率，ruff/mypy strict 全绿。落实 ADR-027 模块化原则的第二个执行案例。 |
| v0.0.15 修订 | 2026-06-20 | _pending_ | 监控窗口三处修复：① 独立顶级窗口（`Qt.WindowType.Window` flag + 实例化时不传 parent），Windows 任务栏独立条目 + 自带标题栏 X 关闭按钮，不再依附主窗口；② 加关闭方式：菜单"监控"加"关闭监控"项（Ctrl+W）+ closeEvent emit `closed` 信号让 MainWindow 清空 `_hw_window` 引用，下次"打开监控"重新实例化；③ METRICS label 中文化（CPU 占用率 / GPU 利用率 / 显存占用率 / 内存占用率 / CPU 温度 / GPU 温度）+ 加 y 轴（左侧 28px 刻度标签 0/25/50/75/100 + 单位 ° 或 % + 竖线）+ plot 坐标系背景改用 `#1E293B`（与 cell 整体背景 `#0F172A` 区分）+ 网格线加深为 `#334155`（5 条 0/25/50/75/100，原 3 条）。测试 150 通过，84.37% 覆盖率。 |
| v0.0.16 | 2026-06-20 | _pending_ | **新建对话/清空按钮接通实际行为**：用户审查三候选（取消按钮/QSettings/新建清空）是否回退到 v0.0.12 状态——AI 实际审查代码后确认三候选都是扩展公开接口非侵入式（v0.0.12 错误是改 Sidebar 类继承+改 objectName+塞 HardwareMonitor 进 Sidebar 内部，三候选是 Toolbar/ChatWorker 仅扩展信号+MainWindow 一行 connect+chat_page 内部已有方法复用，性质完全不同）。用户要求"存 git + 分支修改 + 测试方法 + 任何不对马上回滚"，AI 开 `feat/clear-new-chat-buttons` 分支做候选 3（最安全）：① toolbar.py 扩展 `new_chat_requested` + `clear_requested` 两个 Signal（不改类继承/objectName/既有信号）+ `_build_actions` 改 triggered 从 `_status_callback("活 UI 空壳...")` 占位改为 emit 信号；② main_window.py 加 2 行 connect（`toolbar.new_chat_requested.connect(chat_page._clear_messages)` + `toolbar.clear_requested.connect(chat_page._clear_messages)`）；③ chat_page._clear_messages 零修改复用（v0.0.9 已实现）。打 v0.0.16-test .exe 让用户验证通过 → 合并 main + 升版本 0.0.15 → 0.0.16 + 重新打包到 v0.0.16/（删 v0.0.15 + v0.0.16-test）。测试 152 通过（+2 新增信号 emit 验证），84.52% 覆盖率，ruff/mypy strict 全绿。ADR-030 追加。落实 ADR-027 模块化原则的第三个执行案例。接口预留型待办首例落地（v0.0.8 status_callback 占位 → v0.0.16 接通实际行为）。 |
| v0.0.17 | 2026-06-21 | a6fad06 | **取消按钮接通 ChatWorker.stop()（候选 1 已转正）**：v0.0.16 验证通过合并 main 后用户选择执行候选 1。AI 开 `feat/cancel-button` 分支做首版：toolbar 加 cancel_requested 信号 + ChatWorker 加 chat_aborted 信号 + chat_page 加 _cancel_chat/_on_chat_aborted + MainWindow 1 行 connect + stop-active.svg 图标。用户验证 v0.0.17-test.exe 后反馈 3 个问题：① 唤醒/思考阶段点取消无反应需第二次点击 ② 取消按钮样式（外圈圆形轮廓 + 内部红色方块）+ 位置（模型下拉框右侧）③ 流式中点停止气泡无 [已取消] 后缀。AI 在分支完成 3 项修订：① _cancel_chat 同步立即调 _on_chat_aborted 清理 UI（不等后台信号，处理唤醒阶段阻塞）+ _on_chat_aborted 幂等保护 ② 重新生成 stop-active.svg（外圈 circle(12,12,10) + 内部 rect 红色方块 #EF4444）+ 把 cancel-action 从 _build_actions 移到 _build_model_group 里 model_combo 之后 ③ _on_chat_aborted 加 setText 同步刷新气泡显示后缀。测试 156 通过（+4 新增），84.55% 覆盖率，ruff/mypy strict 全绿。打 v0.0.17-test .exe 用户验证通过 → 合并 main + 转正 v0.0.17.exe（删 v0.0.16/ + v0.0.17-test/ 重命名 v0.0.17/）。ADR-031 追加。落实 ADR-027 模块化原则的第四个执行案例 + 接口预留型待办第二例落地（v0.0.8 ChatWorker.stop 占位 → v0.0.17 接通）。 |
| v0.0.18 | 2026-06-23 | _pending_ | **编排层骨架（v0.0.18 骨架版，UI 看不到变化）**：编排层 7 模块新建独立挂载（不动既有 core.py/planner.py，作 LegacyOrchestrator 向后兼容）：① `types.py` 纯 dataclass——Role/ToolCall/ToolResult/Message/TerminationReason/TurnState/TurnResult/SessionData/CompactionRecord；② `turn.py` Turn 状态机——check_termination 优先级（user_cancel > context_overflow > llm_failed > llm_stopped > doom_loop > consecutive_errors > max_steps）+ tool_signature md5 hash 检测重复调用 + dataclasses.replace 整体覆写；③ `persistence.py` sqlite3 持久化层（零第三方依赖）——sessions/messages/compaction_records 三表 + 两索引 + threading.Lock 保护连接 + load_messages(limit) 用 `SELECT rowid, ...` 显式取 rowid 避免同秒排序不稳；④ `dispatcher.py` LLM 输出解析 + 工具调度——parse_response 解析 ` ```json ... ``` ` 块（支持 OpenAI function 格式 + 自动生成 call_xxx id）+ execute_tool_calls 捕获 PermissionError 单独回喂 + tool_signature 用于 doom_loop 检测；⑤ `context.py` ContextManager 4 级压缩——L1 工具结果预算（>2000 字符落盘到 tool_results_dir + 占位回喂）+ L2 旧消息截断（保留 keep_recent=20 条，旧消息内容截断到 200 字符 + is_compacted=True）+ L3 异步真摘要（SummaryWorker QThread + qwen2.5:3b 独立小摘要模型 + SUMMARY_SYSTEM_PROMPT 强制保留文件路径/任务 ID/工具调用 ID/URL/哈希/模型名/函数名/错误码）+ L4 硬溢出终止；修复 threading.Lock 不可重入死锁（apply_level2_truncate 传 msgs 参数避免嵌套加锁）；⑥ `summary_worker.py` SummaryWorker QThread 骨架——summary_completed/summary_failed 信号 + set_chunks/stop/run/_summarize_block/_merge_summaries，v0.0.18 骨架版返回 "[骨架占位摘要]" + 前 200 字符（v0.0.19 实化真调 Ollama）；⑦ `loop.py` Orchestrator 主循环 10 步——初始化/终止判定/LLM 调用/assistant 入历史/LLM 自然停止 break 前调 on_step/工具执行/tool_result 入历史/doom_loop 检测/压缩触发检查/状态整体覆写；异步摘要合流 + 失败降级到 L2。测试 251 通过（+95 新增），87% 覆盖率，ruff/mypy strict 全绿。ADR-033 追加。落实 ADR-027 模块化原则的第五个执行案例——编排层完全独立挂载，旧 core.py/planner.py 不动。下一步 v0.0.19 工具层实化 + v0.0.20 UI 接通。 |