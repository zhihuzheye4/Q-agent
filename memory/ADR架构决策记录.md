<!--
权限：L1 可写不可读
说明：架构决策记录（Architecture Decision Record）。
       AI 只追加新决策条目，从不修改旧条目；人类查阅用。
       新决策若取代旧决策，新条目内标注"取代 ADR-XXX"，旧条目保留不变。
       纯 append-only，决策不可丢。
-->

# Q-agent ADR 架构决策记录

格式：每条决策一个 ADR-编号，含：时间、状态、背景、决策、后果、取代关系。

---

## ADR-001 记忆系统权限三原则

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：Claude Code 的 Edit 工具在文件内追加内容时，有概率误判 old_string 而删除本不该删的内容。珍贵记忆若被覆盖式修改，会导致项目历史丢失。
- **决策**：本项目所有记忆文件按重要性分三级权限：
  - L1 可写不可读：append-only，AI 不读不改，最安全
  - L2 可写可删改不可读：AI 可改可删但 AI 不读
  - L3 完全权限：AI 可读可写可改可删
- **后果**：L1 文件永不被 Edit 误删；L3 文件承担 Edit 风险但靠编年史/git/数据源兜底。
- **取代**：无

## ADR-002 编年史作为临时记忆安全网

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：临时记忆（L3）需 AI 启动时读取，必须可覆盖；但直接覆盖会丢历史进度。
- **决策**：临时记忆每次整体覆写前，旧版本完整快照追加到 `编年史记忆.md`（L1）。
- **后果**：临时记忆保持简洁的"当前态"，历史进度永久留档于编年史。
- **取代**：无

## ADR-003 思维导图脚本化

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：思维导图作为可视化进度条给用户看，若 AI 直接 Edit md 会浪费 token 且有误删风险。
- **决策**：思维导图采用数据源 + 渲染脚本分离架构：
  - 数据源 `memory/思维导图数据.jsonl`（L1 append-only）
  - 渲染脚本 `scripts/update_mindmap.py`（读 jsonl 生成 md）
  - 输出 `memory/思维导图.md`（脚本生成，AI 不直接 Edit）
- **后果**：AI 只追加 jsonl 一行节点事件，调脚本即完成更新；token 消耗最小化；md 文件由脚本确定性生成，避免 Edit 误删。
- **取代**：无

## ADR-004 项目记忆体系为 Q-agent 专属

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：用户最初表述"跨会话"引发评审建议区分开发期/运行期，但用户纠正为本项目专属。
- **决策**：本记忆体系只服务 Q-agent 一个项目的开发与演进，不分开发期/运行期，未来 Q-agent 框架自身的运行期记忆由框架代码实现，与本项目协作记忆物理隔离。
- **后果**：避免元层次混淆；Q-agent 运行期记忆设计留待框架代码阶段单独处理。
- **取代**：无

## ADR-005 项目框架搭建策略

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：项目从零开始，需要决定框架阶段做什么。用户明确"搭建框架=项目开始前把准备工作做好"。
- **决策**：框架阶段一次性配齐工具链（ruff/mypy/pytest）+ 核心模块骨架（cli/orchestrator/llm/tools/skills/memory 全 stub）+ 项目指导文件 + 方案文件夹机制 + 开发执行规则。
- **后果**：骨架阶段所有模块 stub 就位能跑通最小循环，后续功能增量添加。
- **取代**：无

## ADR-006 永不沙箱

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：项目定位为类似 Claude Code 的桌面端 AI 工具，不是给开发者的 Agent 框架。LLM 指令应直接执行，不需要权限分级沙箱。
- **决策**：本项目永不引入沙箱模块。LLM 指令通过工具调用层（`q_agent/tools/`）直接执行，仅保留基本输入校验（危险命令黑名单 + 项目根目录保护）作为安全底线。
- **后果**：删除沙箱模块设计；工具调用层负责 @tool 注册 + 执行器 + 基本安全；用户提"代码执行"等需求时可加单独的执行工具（不是项目级沙箱）。
- **取代**：无

## ADR-007 增量开发哲学

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：用户提出"一砖一瓦盖房子"的开发哲学，反对瀑布式一次性完整方案。
- **决策**：框架阶段一次性做好准备工作；功能开发阶段增量添加——用户提需求 → 讨论 → 生成方案文件 → 执行 → 更新项目指导文件。每个具体功能由用户主动提出，不主动设计。
- **后果**：项目指导文件标注"准备好但目前用不上的"方向，等用户提需求时再调用。
- **取代**：无

## ADR-008 方案文件夹机制

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：每次讨论后需要留档具体执行方案，但 AI 不应回读旧方案避免被锚定。
- **决策**：新建 `memory/方案/` 文件夹（L1 可写不可读）。每次讨论达成共识后，AI 生成具体方案写入 `方案_YYYY-MM-DD_HHmm_主题.md`。AI 执行时不回读，基于当前会话上下文。执行完毕归档到 `memory/方案/已执行/`。
- **后果**：方案文件作为人类审计/历史档案；AI 每次基于当前讨论生成新方案，不被旧方案锁死。
- **取代**：无

## ADR-009 项目指导文件机制

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：增量开发需要导航图，让 Claude Code 在每次启动时知道项目当前节点和可能方向。之前叫"项目开发方案"或"思维导图"都不准确。
- **决策**：新建 `memory/项目指导文件.md`（L3 完全权限，AI 启动可读）。内容：项目最终形态 + 关键约束 + 技术栈 + 核心模块状态 + 准备好但目前用不上的方向 + 开发流程 + 当前节点 + 已完成节点。每个里程碑完成后更新当前节点和已完成节点。
- **后果**：Claude Code 启动时读 CLAUDE.md + 临时记忆 + 项目指导文件，掌握项目全貌。
- **取代**：无

## ADR-010 可执行安装包机制

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：用户要求"工作每完成一部分都必须形成可执行 .exe"，让每个里程碑可分发。
- **决策**：新建 `安装包/` 文件夹长期存 .exe，子目录按版本号命名 `v{版本}/`。打包工具 PyInstaller（dev 依赖，装 F 盘 venv，不违反"零第三方运行时依赖"原则）。`.exe` 不入 git（.gitignore 例外保留 .gitkeep + README），历史版本长期保留不删。
- **后果**：每个 commit 同步打 .exe；`安装包/README.md` 维护版本历史表；PyInstaller --onefile 模式生成单文件 .exe，--distpath 指向 `安装包/`。
- **取代**：无

## ADR-011 UI 矢量图资源隔离

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：用户要求 UI 界面矢量图存单独文件夹，只存 UI 调用的矢量图，不混其他资源。
- **决策**：新建 `q_agent/assets/icons/` 作为包内资源目录。只存 SVG 矢量图，命名 `图标名-状态.svg`。禁止存位图/字体/音频/配置/开发文档图。开发文档图放 `memory/` 或根目录，物理隔离。包内资源会被 PyInstaller 一起打包进 .exe，UI 代码用 `importlib.resources` 访问。
- **后果**：UI 资源与开发文档资源物理分离；打包时自动随包分发，无需额外配置。
- **取代**：无

## ADR-012 指令执行自由度规则

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：用户明确"除非有明确指令，否则我下达的指令都是有自由选择空间的，非强制执行"。
- **决策**：用户指令默认非强制按字面执行，AI 在执行时带判断力（路径/工具/命名等细节可自定并说明）。大决策仍需先展示方案让用户否决。用户用"必须/一定/严格按/不许"等明确措辞 = 强制字面执行。规则写入全局记忆 + CLAUDE.md 第十九节。
- **后果**：AI 执行时有判断空间，遇到更优方案可提出；机械执行限于明确措辞的指令。
- **取代**：无

## ADR-013 UI 技术栈选 PySide6

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：进入 UI 界面开发阶段，需选 GUI 框架。候选有 PyQt5（第三方 GPL，商用付费）/ PySide6（Qt 6 官方 LGPL，商用免费）/ Tkinter（标准库但控件原始）。
- **决策**：选 **PySide6**——Qt 6 官方 Python 绑定，LGPL 商用免费，QtSvg 模块内置（无需额外依赖即可渲染 SVG）。
- **后果**：开发期依赖 PySide6 装 F 盘 venv，运行时通过 PyInstaller `--onefile` 打包进 .exe（见 ADR-015）。QtSvg 内置意味着矢量图调用零额外依赖。
- **取代**：无

## ADR-014 矢量图脚本预制策略

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：UI 界面需要矢量图标。两条路：(A) 实时渲染 SVG（运行时算力开销）/ (B) 预制矢量图文件供 UI 调用（节省运行时算力）。生成图标方式：(A) 调 /ui-ux-pro-max skill 烧 token 多（几万到十几万）/ (B) 调脚本生成烧 token 少（几千）。
- **决策**：
  1. UI 界面**不实时渲染图形**，**调用预制矢量图文件**——节省运行时计算资源（用户核心哲学：预制调用 vs 实时渲染）
  2. **脚本预制省 AI token**：skill 出规范，脚本按规范批量生成项目调用的图标文件
  3. 图标调用方案选**方案 C：SVG sprite + QtSvg 首次缓存**——脚本生成单文件 SVG sprite（含多个 `<symbol id="xxx">`），UI 启动时 `QSvgRenderer` 加载 sprite 按 id 渲染到 `QPixmap` 缓存（首次渲染一次），UI 显示时调缓存。优势：矢量源不丢 / 单文件管理减 IO / 首次缓存后接近位图速度 / 任意缩放无失真 / 零额外依赖（QtSvg 内置）
  4. **放弃"SVG→PNG→UI 调 PNG"位图思维**：固定分辨率丢失矢量优势
- **后果**：脚本 `scripts/generate_icons.py` 在开发期一次性生成 SVG sprite，UI 运行时只读文件 + 首次渲染缓存。PySide6.QtSvg 转 PNG 能力按需使用（`--png` 显式开关，默认关闭），不强制每次跑。
- **取代**：无

## ADR-015 分发零外部依赖硬规则

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：用户强调"1G 软件调用 20G 外部依赖，跟普通人想买手机得先买光刻机一样离谱"。某些 AI 工具要求用户先在 `requirements.txt` 装 100+ 依赖才能用某功能，此类设计在本项目被禁止。Python 自带解释器 + PyInstaller `--onefile` 可把解释器 + 所有依赖 + 代码 + 资源打包进单个 `.exe`，用户双击即跑。
- **决策**：
  1. 最终用户拿到 `.exe` 双击即跑，**禁止让用户装任何外部依赖**
  2. 所有运行时依赖（Python 解释器 + 第三方库 + 资源）必须由 PyInstaller `--onefile` 打包进单个 `.exe`
  3. 开发期依赖（PySide6/PyInstaller/ruff/mypy 等）装 F 盘 venv，仅供开发者使用，**不进入分发包**
  4. 依赖选择原则：优先选**能被 PyInstaller 打包**的库；避免引入**动态加载/外部子进程依赖**的库
  5. .exe 体积是优化目标（避免 1G+20G 荒谬），但**零外部依赖安装**是硬规则，体积可以大但不能让用户装东西
- **后果**：引入新运行时依赖前必须验证 PyInstaller 打包可行性 + 用户机器零外部依赖运行。规则写入 CLAUDE.md 第二十节。
- **取代**：无

## ADR-016 图标调用方案改为方案 D（取代 ADR-014 的方案 C 部分）

- **时间**：2026-06-19
- **状态**：采纳
- **背景**：ADR-014 选择方案 C（SVG sprite + QtSvg 首次预渲染位图缓存）。盲审 3 个子 agent 独立审查后暴露两问题：
  1. **方案 C 本质是位图思维**：QPixmap 是内存位图，首次预渲染后存位图，与"放弃位图思维"原则矛盾
  2. **高 DPI 失真归因错误**：之前把高 DPI 失真归因为"C 的本质缺陷"，但 QPixmap 支持 setDevicePixelRatio，按物理像素渲染不会失真——这是"偷懒实现"问题，不是方案本质缺陷
  3. **论证存在偏向**：盲审指出我之前给的 11:1 比分过激，真实约 6:2~7:3 偏向 D；措辞含绝对化（"零开销"/"完美"/"整体崩"）；漏列 C 的优势维度（统一管理 / 多状态切换 / 主题切换 / 平台渲染一致性 / 内存峰值可控）
- **决策**：
  1. 图标调用方案改用**方案 D：QIcon 直接接受 SVG + Qt 内部按 size 智能缓存**
     - 每个 SVG 文件离散存放（不用 sprite 聚合）
     - UI 代码 `QIcon(svg_path)` 直接接受 SVG 文件，Qt 内部 QIconEngine（QSvgIconEngine）按渲染 size 智能缓存
     - 显示到哪个图标哪个尺寸才首次渲染——按需渲染而非全量预热
     - 任意缩放/主题切换/动态着色 tint 由 Qt 自行处理
  2. 补漏维度承认：
     - **统一管理**：方案 C 的 sprite 单文件聚合是优势（脚本输出集中），方案 D 是离散文件但靠 manifest.json 索引
     - **多状态/主题切换**：方案 C 全量预热后切换快；方案 D 首次切换有渲染开销，后续同尺寸走缓存
     - **平台渲染一致性**：方案 C 全量预渲染统一一致；方案 D 依赖 Qt 各平台 QIconEngine 一致性
     - **内存峰值**：方案 C 启动期一次性占满；方案 D 按需渐进，峰值低但随显示增长
     - **资源访问方式**：方案 C 一次性加载 sprite；方案 D `importlib.resources` 逐文件读
  3. 真实结论：方案 D 偏向 6:2~7:3，**优势在按需渲染与真正矢量思维**；方案 C 优势在统一管理与启动期确定性。选 D 的核心理由是**与"放弃位图思维"原则一致** + **峰值内存更友好**
- **后果**：
  - 脚本 `scripts/generate_icons.py` 仍生成离散 SVG 文件 + manifest.json，不再生成 sprite
  - UI 代码用 `QIcon(svg_path)` 直接接受 SVG，不写 QSvgRenderer 预渲染层
  - 首屏预热策略留作可选优化（若首次显示抖动明显再加）
  - PyInstaller 打包：SVG 文件作为 datas 一起进 .exe，零额外依赖
- **取代**：ADR-014 第 3 点（方案 C）改为方案 D；ADR-014 其余三点（预制调用 / 脚本省 token / 放弃 PNG 位图）保留不变

---

## ADR-017：UI 输入框动态高度策略

**日期**：2026-06-19
**状态**：采纳
**取代**：无

### 背景

UI 改进第一轮把对话输入框从 `QLineEdit`（单行）改为 `QTextEdit`（多行），高度区间设为 [44, 200]px。但用 `setMinimumHeight + setMaximumHeight` 只是限制范围，初始固定为最小高度 44px，输入多行内容后输入框不会自动长高，内容溢出直接被滚动条吃掉——视觉上输入框仍是矮矮一条，长发言体验差。

用户明确反馈："输入框高度应跟随输入内容动态改变"。

### 选项

**方案 A：固定高度 + 滚动条**
- 设置一个固定高度（如 100px），多行内容靠内部滚动条消化
- 优点：实现简单
- 缺点：固定高度无法适配短/长发言——短发言浪费空间，长发言滚动条挤占视野

**方案 B：高度跟随内容动态变化（采纳）**
- 监听 `QTextEdit.document().documentLayout().documentSizeChanged` 信号
- `_adjust_height()`：根据 `documentLayout().documentSize().height()` + 边距计算所需高度
- 钳制到 `[INPUT_MIN_HEIGHT=44, INPUT_MAX_HEIGHT=200]` 区间
- 用 `setFixedHeight()` 设置实际高度
- 超过 max 后自动显示垂直滚动条（`ScrollBarAsNeeded` 策略）
- 优点：短发言占 44px 不浪费，长发言自然增长直到 200px 触顶
- 缺点：需手动写调整逻辑（约 6 行）

**方案 C：QTextEdit 自带的 sizeHint 自然增长**
- 不显式设 height，依赖 layout 的 sizeHint
- 缺点：QTextEdit 的 sizeHint 不会随内容变化（默认返回 viewport 高度），需手动触发布局重算，等价于方案 B

### 取舍

选方案 B。理由：
1. `documentSizeChanged` 信号是 Qt 文档系统提供的官方钩子，触发时机精确（内容变化即触发）
2. 钳制区间 `[44, 200]` 是明确的视觉契约——44px 是单行舒适高度，200px 是输入框不超过消息流的比例上限
3. 触顶后 `ScrollBarAsNeeded` 策略自动接管，用户可在 200px 内滚动浏览长输入
4. 实测：初始 44 → 单行 44 → 5 行 82 → 30 行触顶 200 + 滚动条出现 → 清空回 44，符合预期

### 实现要点

```python
# ChatInput.__init__ 末尾
self.document().documentLayout().documentSizeChanged.connect(self._adjust_height)

def _adjust_height(self) -> None:
    doc_h = self.document().documentLayout().documentSize().toSize().height()
    margins = self.contentsMargins()
    needed = int(doc_h + margins.top() + margins.bottom() + 2)
    clamped = max(INPUT_MIN_HEIGHT, min(needed, INPUT_MAX_HEIGHT))
    if self.height() != clamped:
        self.setFixedHeight(clamped)
```

`if self.height() != clamped` 守卫避免无变化时重复触发布局重算（防抖）。

### 影响

- 文件：`q_agent/ui/pages/chat_page.py`
- 测试：手动验证（offscreen mode + processEvents），无新增单测（UI 渲染测试需 QApplication 实例，留手动测试）
- .exe：v0.0.3 已包含此改进

## ADR-018：本地 LLM 检测首版选 Ollama 后端 + urllib 标准库 + QThread 异步检测

- **时间**：2026-06-20
- **状态**：采纳
- **取代**：无（首次实现本地 LLM 检测能力）

### 背景

第一个填充的实际功能：UI 右上角模型下拉框 + 启动时检测本地 LLM。
讨论选项：Ollama / Ollama+LM Studio / Ollama+LM Studio+llama.cpp。
首版范围确认只支持 Ollama（事实标准，HTTP API 简单）。

### 决策

1. **后端**：仅 Ollama，HTTP GET `http://localhost:11434/api/tags`，解析 `{"models":[{"name":"..."}]}`
2. **HTTP 客户端**：标准库 `urllib.request`，**不引入 requests**——坚守 CLAUDE.md 第二十节"分发零外部依赖硬规则"，urllib 在 PyInstaller --onefile 下零额外打包成本
3. **超时**：默认 2 秒（UI 友好，避免长时间卡死），可参数化
4. **异步检测**：`ModelRefreshWorker(QThread)` 后台跑 `list_models`，避免网络请求阻塞 UI 主线程；信号 `models_found(list)` / `refresh_failed(str)` 回主线程
5. **失败 UX**：下拉框显示"未发现本地 LLM"占位项 + 旁边刷新按钮（手动重试）+ 状态栏同步提示原因
6. **检测时机**：MainWindow 启动后 `QTimer.singleShot(100)` 自动触发一次（让 UI 先绘制完），后续手动点刷新
7. **异常处理**：所有失败场景（连接拒绝/超时/HTTP 错误/JSON 解析失败/字段非列表）统一抛 `OllamaError`，message 已含面向用户的友好描述

### 关键代码

```python
# 异常捕获顺序：HTTPError 必须先于 URLError（HTTPError 是 URLError 子类）
try:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
except urllib.error.HTTPError as e:
    raise OllamaError(f"Ollama 返回 HTTP {e.code}：{e.reason}") from e
except urllib.error.URLError as e:
    reason = e.reason
    if isinstance(reason, socket.timeout) or "timed out" in str(reason).lower():
        raise OllamaError(f"连接 Ollama 超时（{timeout}s）：...") from e
    raise OllamaError(f"无法连接 Ollama（{host}）：{reason}。...") from e
except TimeoutError as e:
    raise OllamaError(f"连接 Ollama 超时（{timeout}s）：...") from e
```

QThread worker：

```python
class ModelRefreshWorker(QThread):
    models_found = Signal(list)
    refresh_failed = Signal(str)
    def run(self) -> None:
        try:
            models = list_models(self._host)
        except OllamaError as e:
            self.refresh_failed.emit(str(e))
            return
        self.models_found.emit(models)
```

### 后果

- 优点：零新运行时依赖 / 异步不阻塞 UI / 失败 UX 友好 / 单测覆盖完整
- 取舍：仅 Ollama，LM Studio / llama.cpp 用户首版不可用——留待 ADR-019+ 扩展
- 取舍：未实现 `chat()`，下拉框选中模型后尚无后续动作——下一阶段
- 取舍：未持久化用户选择（QSettings 落盘）——下一候选需求

### 影响

- 文件：`q_agent/llm/ollama.py`（新增）、`q_agent/ui/toolbar.py`（改造）、`q_agent/ui/main_window.py`（启动触发）
- 图标：新增 `refresh-active.svg`（Lucide refresh-cw 风格）
- 测试：`tests/test_llm_ollama.py` 11 例 + `tests/test_ui_toolbar.py` 11 例
- .exe：v0.0.4 已包含

## ADR-019：模型下拉框本地/云端分组 + AI 气泡模型名标签

- **时间**：2026-06-20
- **状态**：采纳
- **取代**：无

### 背景

用户提出两个修改：
1. 下拉框区分本地和云端（首版仅 UI 分组占位，不接云端 API）
2. 对话气泡上方显示当前回答的模型名

### 决策

1. **下拉框分组实现**：QComboBox 改用 QStandardItemModel（QComboBox.addItem 不支持单 item disabled）。分组头用 disabled QStandardItem，setData("header", Qt.UserRole) 标记，setForeground 灰色 + setBold
2. **分组结构**：[本地 header + 本地模型/占位 + 云端 header + 云端预置项]。本地无模型时占位"未发现本地模型"，云端组照常显示
3. **云端预置**：3 家代表各 1 个（gpt-4o / claude-opus-4-7 / gemini-2.5-pro），后续真接 API 时改为动态拉取（ADR-020+）
4. **检测失败 UX**：仅显示"未发现本地 LLM"占位项，不加云端组（让用户先解决本地连接问题）
5. **AI 气泡模型标签**：
   - _add_message(role, text, model_name: str | None = None)
   - AI 消息时在气泡上方加 QLabel#ModelLabel 小灰字（11px #94A3B8）
   - model_name 来源：ChatPage._model_provider 回调，MainWindow 注入 lambda: self.toolbar.current_model()
   - 未注入或返回 None 时显示"(未选模型)"占位
6. **气泡布局重构**：AI 行从 [气泡][stretch] 改为 [垂直列：模型名label + 气泡][stretch]
7. **resize 优化**：维护 _bubble_labels 列表，resizeEvent 批量更新最大宽度（适配嵌套结构，比递归遍历更清晰高效）

### 关键代码

```python
# 分组头：disabled + 灰色 + 粗体
item = QStandardItem(text)
item.setEnabled(False)
item.setData("header", ITEM_ROLE)
item.setForeground(QBrush(QColor("#94A3B8")))
font = item.font(); font.setBold(True); item.setFont(font)

# current_model 内部检查 isEnabled（header disabled 时返回 None）
item = self._combo_model.item(idx)
if item is None or not item.isEnabled():
    return None

# ChatPage 注入 model_provider
self.chat_page.set_model_provider(self.toolbar.current_model)
```

### 后果

- 优点：用户可视觉区分本地/云端，未来真接 API 时分组结构不破坏
- 优点：AI 气泡带模型名，下一阶段接真 LLM 后天然就是"这个模型答的"
- 取舍：云端预置为静态，选了云端模型也不会真调用（UI 占位）——下一阶段接真 API
- 取舍：用户气泡不带模型名（用户自己发的消息，不需要）

### 影响

- 文件：`q_agent/ui/toolbar.py`（QStandardItemModel + 分组 + _on_models_found 重构）、`q_agent/ui/pages/chat_page.py`（_add_message 加 model_name + 嵌套布局 + set_model_provider + _bubble_labels）、`q_agent/ui/main_window.py`（注入 model_provider）、`q_agent/ui/theme.py`（ModelLabel 样式）
- 测试：`tests/test_ui_toolbar.py` 13 例 + `tests/test_ui_imports.py` 3 例新增
- .exe：v0.0.5 已包含

## ADR-020：llm 层对称骨架 + 安装包只保留最新

- **时间**：2026-06-20
- **状态**：采纳
- **背景**：用户三问之一——"软件并没有区分云端和本地，或者你编写的 py 文件并没有区分云端和本地的能力？"——刺到了痛点：v0.0.4 时 ollama.py 仅作为检测函数（list_models + NotImplementedError chat/complete），未纳入 LLMClient 体系；v0.0.5 的 UI 分组（本地/云端 header）只是壳，后端根本没有对称的 client 类层级。用户三问之二——"为什么不先完成最小闭环再添加枝叶"——确认了"现在就补对称骨架"的方向，理由是先把后端结构对称好，下一阶段接真 API 时只填方法体不动构造接口，避免后期改动带来的 bug。同时用户三问之一——"软件包不需要保留每一代，只需要保留最新一代"——要求改安装包规则。
- **决策**：
  1. **llm 层对称骨架**：
     - `q_agent/llm/ollama.py` 升级：新增 `OllamaClient(LLMClient)` 子类，构造 (model, host) + chat/complete 抛 NotImplementedError。list_models() 函数保留不变（UI 检测用）
     - `q_agent/llm/cloud/` 新建子包：`__init__.py` + `openai.py` + `anthropic.py` + `gemini.py` 三个 stub，构造 (model, api_key, base_url) + chat/complete 抛 NotImplementedError
     - `q_agent/llm/__init__.py` 统一导出 LLMClient / OllamaClient / OllamaError / list_models / LocalLLMClient / OpenAIClient / AnthropicClient / GeminiClient
     - 后端分类清晰：local（Ollama + llama.cpp 占位）+ cloud（OpenAI / Anthropic / Gemini）
  2. **所有 client 构造成功，chat/complete 抛 NotImplementedError**：下一阶段接真 API 时只填方法体，不动构造与接口（与 OllamaClient 保持一致模式）
  3. **依赖管理坚守 ADR-015**：urllib 标准库零新运行时依赖，不引入 openai/anthropic/google-generativeai 等 SDK
  4. **安装包只保留最新**（取代 ADR-010 的"历史版本长期保留不删"部分）：
     - 每次打新版本 .exe 时，删掉上一版子目录，只留当前最新版本
     - CLAUDE.md §17 同步更新，安装包/README.md 增加版本历史表保留演进记录
     - v0.0.1~v0.0.4 已删，仅留 v0.0.5；v0.0.6 打包后随之替换 v0.0.5
- **后果**：
  - 优点：后端结构对称，local/cloud 分类清晰，下一阶段接对话需求时所有 client 统一填方法体即可
  - 优点：UI 的本地/云端分组现在有对应的后端类支撑，不是空壳
  - 优点：安装包目录不冗余占空间，用户只拿最新版
  - 取舍：所有 client chat/complete 仍 NotImplementedError（与 v0.0.4/v0.0.5 一致，未退步也未进步功能层面）
  - 取舍：v0.0.1~v0.0.4 的 .exe 二进制永久丢失（演进历史靠 README 版本表 + git log 即可）
- **影响**：
  - 文件：新增 `q_agent/llm/cloud/{__init__,openai,anthropic,gemini}.py`、修改 `q_agent/llm/{__init__,ollama}.py`、新增 `tests/test_llm_clients.py`（15 例）
  - 规则：CLAUDE.md §17 改为只保留最新；安装包/README.md 改写规则并加版本历史表
  - 测试：74 个测试，覆盖率 88.02%
  - .exe：v0.0.6 已打包并启动验证通过
- **取代**：ADR-010 的"历史版本长期保留不删"部分（其余部分如子目录按版本号命名、PyInstaller --onefile、.exe 不入 git 等仍有效）

## ADR-021：Ollama Cloud 转发模型分类（remote_model / remote_host 字段判定）

- **时间**：2026-06-20
- **状态**：采纳
- **背景**：用户准确指出 v0.0.6 之前的 list_models() 把 Ollama /api/tags 返回的所有模型一律塞"本地"组，没看 remote_model / remote_host 字段——minimax-m3 / deepseek-v4-pro 等通过 Ollama Cloud 转发的模型被误判为本地。这是分类 bug，不是结构问题。用户原话："你编写的函数代码里并没有实际判断这个模型是否在本地，而是通过 ollama list 获得模型后直接就填充了"。同时用户对"硬编码 vs 动态"也提出质疑：CLOUD_PRESET 是硬编码占位（ADR-019 明确），但本地组是动态调 API，用户的删除模型检测不出来推测不成立（list_models 无缓存每次启动重新调）。
- **决策**：
  1. **新增 ModelEntry NamedTuple**：`q_agent/llm/ollama.py` 定义 `ModelEntry(name, is_remote, remote_host)`
  2. **list_models() 破坏性改签名**：返回 `list[ModelEntry]`（旧 list[str]）。`is_remote = bool(remote_model) or bool(remote_host)`，任一字段非空即判定为 cloud 转发
  3. **UI 下拉框改三组结构**：本地（真本地 is_remote=False）+ Ollama Cloud（转发 is_remote=True）+ 云端预置（CLOUD_PRESET 占位）。Ollama Cloud 组仅在存在转发模型时才显示 header，避免空组干扰
  4. **graceful degradation**：如果 Ollama 版本较老 /api/tags 不返回 remote_* 字段，所有模型 is_remote=False 退化为 v0.0.6 行为，不会更糟
  5. **CLOUD_PRESET 保留不变**：是 ADR-019 明确的"未接 API 占位"，与"通过 Ollama 转发的真实 cloud 模型"语义不同（前者直连 OpenAI/Anthropic/Google API 未实现，后者通过 Ollama 代理已可调用）
- **后果**：
  - 优点：分类正确——minimax-m3 等显示在 Ollama Cloud 组而非本地组
  - 优点：用户可视觉区分三类模型，下次 Ollama cloud 模型再多也不会再错分
  - 优点：graceful——老版 Ollama 不会因缺字段报错
  - 取舍：list_models() 签名破坏性变更（list[str] → list[ModelEntry]），调用点仅 toolbar.worker，已同步更新
  - 取舍：CLOUD_PRESET 仍是硬编码占位，等真接 OpenAI/Anthropic/Google API 时改动态拉取（ADR-020+ 范围）
- **影响**：
  - 文件：`q_agent/llm/ollama.py`（新增 ModelEntry + list_models 改签名）、`q_agent/llm/__init__.py`（导出 ModelEntry）、`q_agent/ui/toolbar.py`（三组分类 + HEADER_OLLAMA_CLOUD）、`tests/test_llm_ollama.py`（3 例新增）、`tests/test_ui_toolbar.py`（重写覆盖三组 4 种组合）
  - 测试：81 个测试通过，覆盖率 88.15%
  - .exe：v0.0.7 已打包并启动验证通过
- **取代**：无（修正 ADR-019 实现细节，不动 ADR-019 决策本身）

## ADR-022：通过 Ollama 唤醒模型 + 流式批量刷新（500字/500ms 混合阈值）

- **时间**：2026-06-20
- **状态**：采纳
- **背景**：v0.0.7 完成模型下拉框三组分类后，下一步是把已选模型真正用起来——用户发送对话，实际调 Ollama /api/chat 拿回复显示在 AI 气泡。原 _on_send_clicked 是 echo 占位。用户明确反馈 UX 决策："攒一段信息，比如500字，然后流失返回，这样可以提升出现速度，如果真就http实时监视的话，有些计算比较慢的，那真就是一秒钟一个字，用户会崩溃的"——拒绝纯 token 流式（一秒一字让人崩溃），要批量刷新。
- **决策**：
  1. **后端填 chat_stream**：`OllamaClient.chat_stream(messages, timeout=120.0) -> Iterator[str]` 流式调 POST /api/chat stream=true，NDJSON 逐行 json.loads，yield `chunk.message.content`，遇 `done=true` 返回。错误处理复用 list_models 的 urllib 模式（HTTPError 在 URLError 之前捕获，socket.timeout 单独处理）
  2. **chat() 填为 "".join(self.chat_stream(messages))**：同步便捷方法供编排层非流式调用
  3. **ChatWorker QThread 后台跑流式**：信号 chunk_received(str) / chat_failed(str) / chat_done()，常量 CHUNK_SIZE=500 + FLUSH_MS=500.0，混合刷新策略——buffer 攒满 500字 OR 距上次 flush 满 500ms 任一触发即 emit，循环结束 emit 剩余 buffer + chat_done。stop() 接口留作未来取消按钮（v0.0.8 未接 UI）
  4. **chat_page 接入真实调用**：_on_send_clicked 重写——取 group 防御性检查（SENDABLE_GROUPS=("local", "ollama-cloud")）→ add user → 构造 messages_for_llm → 创建 pending AI 气泡（append_to_history=False 不污染历史）→ loading 状态（禁用输入+按钮变"生成中"）→ 启动 ChatWorker
  5. **三 slot**：_on_chunk（追加到 pending 气泡 + scroll）/ _on_chat_failed（pending 气泡 objectName 改 MessageError 红色样式 + reset）/ _on_chat_done（完整回复入 _messages + 清 pending + reset）
  6. **toolbar 暴露 group**：新增 model_group_changed=Signal(object) 信号 + current_model_group() 方法，_on_combo_changed 同时 emit text 和 group
  7. **云端预置禁用发送**：update_send_enabled("cloud") → send_btn.setEnabled(False) + tooltip "云端 API 未接，请选本地或 Ollama Cloud 模型"；SENDABLE_GROUPS 判定 local/ollama-cloud 启用 iff 输入框非空；None 禁用 + tooltip "未选模型"
  8. **theme 加 MessageError 红色样式**：QLabel#MessageError 红字红底红边，区别于正常 AI 气泡
- **后果**：
  - 优点：用户发送消息真实调 Ollama，AI 气泡每 500字/500ms 刷新一段，避免一秒一字崩溃
  - 优点：云端预置未接 API 时禁用发送按钮 + tooltip，用户不会误触发 NotImplementedError
  - 优点：错误气泡红色视觉区分，失败时用户一眼能看出
  - 取舍：历史消息首版全传（token 消耗大但简单），上下文裁剪留 v0.0.9+
  - 取舍：取消按钮 UI 未接（ChatWorker.stop() 接口已留，v0.0.9+ 接）
  - 取舍：host 仍 hardcoded "http://localhost:11434"，QSettings 持久化留 v0.0.9+
- **影响**：
  - 文件：`q_agent/llm/ollama.py`（chat_stream + chat 填充）、新建 `q_agent/ui/chat_worker.py`（ChatWorker QThread）、`q_agent/ui/pages/chat_page.py`（_on_send_clicked 重写 + 3 slot + SENDABLE_GROUPS + set_group_provider/set_host/update_send_enabled + _add_message 加 append_to_history + _scroll_to_bottom 防御 isValid）、`q_agent/ui/toolbar.py`（model_group_changed 信号 + current_model_group 方法）、`q_agent/ui/main_window.py`（注入 + 信号连接 + 启动 QTimer.singleShot 主动同步）、`q_agent/ui/theme.py`（MessageError 红色样式）、新增 `tests/test_ui_chat_page.py`（12 例）+ 扩充 `tests/test_llm_ollama.py`（6 例 chat_stream）+ `tests/test_ui_toolbar.py`（5 例 group）
  - 测试：106 个测试通过，覆盖率 86.99%
  - .exe：v0.0.8 已打包并验证通过
- **取代**：无（在 ADR-021 三组分类基础上接真实调用，不修改 ADR-021 决策）

## ADR-023：模型内存释放 + 切换清空上下文 + 模型名颜色

- **时间**：2026-06-20
- **状态**：采纳
- **背景**：v0.0.8 通过 Ollama 唤醒模型后，用户提三个新需求：
  1. Ollama 默认 keep_alive=5min 把模型留在 RAM 待机；用户不想用某模型时它仍占内存。需"释放"按钮主动卸载出 RAM
  2. 切换模型后历史对话对新模型无意义（不同模型的 system prompt/上下文不同），需清空当前对话 + 提示用户"模型已切换"
  3. 现在所有 AI 气泡上方模型名都是统一灰色 #94A3B8，多模型对话时无法一眼区分是哪个模型说的
- **决策**：
  1. **内存释放**：新增 `release_model(model, host, timeout=30.0)` 同步函数（POST /api/generate body={"model":..., "keep_alive": 0}，Ollama 在当前生成完成后立即卸载模型权重；模型没在内存时 no-op）。toolbar 加 `release_btn`（与 refresh_btn 并排，Lucide power-off 风格 release-active.svg 图标），仅 local/ollama-cloud 启用，点击弹 QMessageBox 确认 → 启动 `ModelReleaseWorker(QThread)` 异步调用避免阻塞 UI；释放成功 emit `model_released(str)` + 状态栏"已释放 XXX 内存"，失败 emit `release_failed(str)`
  2. **切换清空 + 系统提示**：toolbar._on_combo_changed 现同时 emit model_selected(str) + model_group_changed(group) + 同步 release_btn 状态。main_window 连接 `toolbar.model_selected → chat_page._on_model_changed`。`_on_model_changed(model_name)` 调 `_clear_messages()`（移除所有 row widget 保留末尾 stretch + 清空 _messages + pending 状态）+ `_add_system_message(SYSTEM_MSG_SWITCHED.format(model=...))`（居中布局 QLabel#MessageSystem 灰色斜体 12px，不入 _messages 不是对话内容）。首次自动选择抑制：`_suppress_select_emit` flag 让 _on_models_found 自动选首个模型时不 emit model_selected（避免清空初始问候），但仍 emit group_changed 同步发送按钮状态
  3. **模型名颜色**：`MODEL_NAME_PALETTE` 8 个高对比色（绿/蓝/紫/粉/橙/青/黄/靛），`_model_color(name)` 用 `zlib.crc32(name.encode("utf-8")) % 8` 取色——zlib 跨进程稳定（不同于 Python 内置 hash 随机化），同一模型每次启动显示同色。AI 气泡上方 ModelLabel 用 `setStyleSheet(f"color: {color}; font-size: 11px; padding: 0 4px;")` 应用 hash 色，覆盖全局 QSS 的灰色规则；占位文本 NO_MODEL_TEXT 返回默认灰 #94A3B8
- **后果**：
  - 优点：用户可主动释放不用的模型内存，避免 Ollama RAM 堆积多个待机模型
  - 优点：切换模型时上下文清空 + 系统提示，用户明确知道"新对话开始"，避免误以为模型在延续旧上下文
  - 优点：模型名按 hash 稳定着色，多模型对话时一眼区分；同一模型每次显示同色不混淆
  - 取舍：release_model 调用是同步阻塞（QThread 内 30s timeout），如果模型正在 chat 生成中调用，Ollama 会在当前生成完成后立即卸载（keep_alive=0 仅影响下次空闲时长，不会强制中断当前生成）
  - 取舍：切换模型清空对话是硬规则——历史消息不保留；用户切回原模型也需重新输入（如需保留历史应走"新建对话"分离会话）
  - 取舍：模型名 hash 颜色可能碰撞（不同模型名 crc32 mod 8 同值），但 8 色调色板足够日常使用，碰撞概率 1/8 可接受
- **影响**：
  - 文件：`q_agent/llm/ollama.py` 新增 release_model、`q_agent/llm/__init__.py` 导出、`q_agent/ui/toolbar.py` 加 release_btn + ModelReleaseWorker + _suppress_select_emit flag + _on_release_clicked/_on_released/_on_release_failed 三 slot、`q_agent/ui/pages/chat_page.py` 加 _on_model_changed + _clear_messages + _add_system_message + _model_color + _find_first_label_by_object_name（测试辅助）+ MODEL_NAME_PALETTE + SYSTEM_MSG_SWITCHED、`q_agent/ui/main_window.py` 连接 model_selected → _on_model_changed、`q_agent/ui/theme.py` 加 MessageSystem 样式、新增 `q_agent/assets/icons/release-active.svg` + manifest 注册
  - 测试：14 例新增（release_model happy/http/connection/timeout 4 + ModelReleaseWorker released/failed 2 + chat_page _on_model_changed/_clear_messages/_model_color 稳定/占位/_add_system_message 5 + toolbar release_btn 初始禁用/local 启用/cloud 禁用 3），总 120 通过，覆盖率 85.31%
  - .exe：v0.0.9 已打包并验证通过
- **取代**：无（在 ADR-022 通过 Ollama 唤醒基础上扩展内存管理与 UX 改进，不修改 ADR-022 决策）

## ADR-024：加载指示器（三点跳动 + 流动彩虹 + 半透明）

**日期**：2026-06-20
**状态**：已实施（v0.0.10）
**关联**：ADR-022（流式批量刷新，本 ADR 补足"等待首 chunk 期间"的视觉反馈）

### 背景

v0.0.8 接通 Ollama 流式后，用户发送对话到首个 chunk 到达之间有数百毫秒~数秒的"空等期"，期间 UI 只显示"生成中"按钮文字，pending AI 气泡为空 QLabel（高度 0 看不见）。用户看不出"AI 是否在跑"，体验空洞。

v0.0.10 加加载指示器填补空等期。

### 决策

四个维度经 AskUserQuestion 确认：

| 维度 | 选项 | 决策 |
|------|------|------|
| 形式 | 不确定进度条 / spinner / 三点跳动 / 流动彩虹横条 | **三点跳动**（iMessage 打字气泡风格，轻量友好） |
| 位置 | pending 气泡内 / 按钮位置 / 顶部悬浮条 / 输入框上方 | **pending AI 气泡内**（贴近用户视线） |
| 彩色 | 模型 hash 色 / 流动彩虹渐变 / 品牌主色 | **流动彩虹渐变**（HSV 色相循环，独立于模型色，活泼） |
| 透明度 | 元素半透明 / 消息流遮罩 / 气泡半透明 | **加载指示元素本身半透明**（alpha=180 ≈ 70%，不刺眼） |

### 实施

- 新建 `q_agent/ui/loading_dots.py`：`LoadingDots(QWidget)` 自定义 paintEvent
  - 三个圆点（DOT_SIZE=8, DOT_GAP=8）依次上下跳动（DOT_BOUNCE=5px）
  - 相位偏移 `i * 0.33` 让三个点错开 1/3 周期 → 依次跳动
  - 跳动用 `-abs(math.sin(t * 2π))` → 平滑上跳下落
  - 颜色 `QColor.fromHsv((phase*360 + i*60) % 360, 220, 230, 180)` → 流动彩虹
  - QTimer 80ms tick，phase += 0.05，1.6s 一周期
- `chat_page._add_message` 加 `loading: bool = False` 参数，pending AI 气泡用 True → 在模型名与气泡之间插入 LoadingDots
- 新增 `_pending_loading: LoadingDots | None` 字段 + `_remove_pending_loading()` 辅助方法
- `_on_chunk` 首次调用 / `_on_chat_failed` / `_on_chat_done` / `_clear_messages` 均清理 LoadingDots
- 透明度 `DOT_ALPHA=180`（~70%）通过 QColor 第四参数 alpha 通道实现，非 setWindowOpacity（仅顶层窗口有效）

### 取舍

- **不用 QPropertyAnimation + QML**：自定义 paintEvent + QTimer 更轻量，PyInstaller 打包友好（不引入 QtQml 依赖），符合 ADR-015 零新运行时依赖
- **不用 QMovie/GIF**：GIF 资源需打包进 .exe 增体积，矢量代码渲染更轻
- **HSV 而非固定调色板**：流动效果需要色相连续变化，HSV 是最自然的色彩空间
- **透明度 alpha=180 而非 setStyleSheet opacity**：Qt widget 无原生 opacity 属性，QGraphicsEffect 有性能开销，直接 painter alpha 通道最直接
- **跳动幅度 5px 而非更大**：视觉提示性足够 + 不抢眼不晃动，符合"半透明不刺眼"决策

### 不在范围内（v0.0.11+）

- 取消按钮接 ChatWorker.stop()（加载中可点取消）
- 加载时长统计 / 慢响应警告（如 5s 无 chunk 提示"Ollama 响应慢"）
- 主题切换时 LoadingDots 配色变体（当前固定 HSV 流动）
- 字体/字号优化（当前 dot_size=8 固定，不随 DPI 缩放）


## ADR-025：release_model 卸载验证（/api/ps 轮询确认）

**日期**：2026-06-20
**状态**：已实施（v0.0.11）
**关联**：ADR-023（v0.0.9 内存释放，本 ADR 补足"卸载是否真的生效"的可信反馈）

### 背景

v0.0.9 实现内存释放功能后，用户报告"点了释放按钮选 Yes，但任务管理器 GPU 占用依然存在，没有被释放"。

排查发现：
- 代码本身工作正常：curl 直接调 `/api/generate keep_alive=0` → `/api/ps` 立即变空，Python `release_model()` 同样工作
- `nvidia-smi` 显示 VRAM 从 5.6GB 降到 1GB（剩余 1GB 是 explorer/NVIDIA Overlay 等系统进程）
- 真正原因：**Ollama 进程级 CUDA context 不立即归还 OS**——`/api/ps` 显示模型已卸载（Ollama 内部确实释放了模型权重），`nvidia-smi` 显示 VRAM 已归还 OS，但**任务管理器看 ollama.exe 进程的"专用 GPU 内存"列可能仍显示几 GB 占用**，因为进程级 CUDA pool 不立即归还（需要等一段时间或进程退出）

用户看任务管理器 GPU 占用"依然存在"是误判，但 v0.0.9 状态栏只说"已释放 XXX 内存"过于笼统，没有给用户**可信的"真的卸载了"的反馈**。

### 决策

在 `release_model` 内部加 **`/api/ps` 验证步骤**：

1. 调 POST /api/generate keep_alive=0 触发卸载（v0.0.9 原逻辑）
2. 立即调 GET /api/ps 检查模型是否还在加载列表
3. 若还在，sleep 300ms 后重试，最多 3 次
4. 3 次后仍在 → 抛 `OllamaError("Ollama 接受卸载请求但 XXX 仍在内存（可能正在生成中，请稍后重试）")`
5. 3 次内卸载成功 → 正常返回

状态栏文案改为：
- ✅ 成功：`已卸载 XXX 出 Ollama（API 验证通过，VRAM 已归还；任务管理器进程级 GPU 内存可能延迟显示）`
- ❌ 失败：`释放失败：Ollama 接受卸载请求但 XXX 仍在内存（可能正在生成中，请稍后重试）`

### 实施

- `q_agent/llm/ollama.py`：
  - 新增 `_is_model_loaded(model, host, timeout) -> bool` 辅助函数，调 GET /api/ps 检查模型是否在加载列表
  - `release_model` 加 4 个新参数：`verify: bool = True` / `verify_attempts: int = 3` / `verify_interval: float = 0.3` / `timeout` 已存在
  - 卸载请求成功后，若 verify=True 则轮询 /api/ps，全部尝试后仍在 → 抛 OllamaError
  - import `time` 用于 sleep
- `q_agent/ui/toolbar.py`：
  - `_on_released` 状态栏文案明确说明"API 验证通过，VRAM 已归还，任务管理器进程级 GPU 内存可能延迟显示"
  - `_on_release_failed` 文档说明区分"连接失败"与"卸载未生效"两种语义
- 测试 5 例新增（test_llm_ollama.py）：
  - test_release_model_verifies_unload_success（generate OK + /api/ps 空 → 通过）
  - test_release_model_verifies_unload_still_loaded（3 次轮询后仍含模型 → OllamaError）
  - test_release_model_verify_retries_until_success（前 2 次含模型 + 第 3 次空 → 通过，验证轮询）
  - test_release_model_verify_disabled_skips_ps（verify=False 只调 generate）
  - 原 test_release_model_happy 改用 verify=False 跳过验证专门测 generate payload

### 取舍

- **轮询而非单次验证**：Ollama 卸载 API 返回快但内部清理有几十毫秒延迟，单次 /api/ps 可能仍含模型。300ms 间隔 × 3 次覆盖 0.9s 内的卸载完成，足以确认。
- **`verify` 默认 True 但可关闭**：编排层非 UI 场景可能不需要验证（如批量卸载），保留 verify=False 开关。
- **失败抛错而非返回 bool**：让 UI 走 `_on_release_failed` 分支统一处理，文案区分"连接失败"与"卸载未生效"两种语义，用户能判断是网络问题还是模型在生成中。
- **不解决"进程级 CUDA 不归还"**：这是 Ollama 已知行为，我们无法控制。通过状态栏文案明确告知用户"VRAM 已归还，任务管理器进程级 GPU 内存可能延迟显示"，避免用户误判功能失效。
- **不立即重试卸载**：如果模型正在生成中，重试卸载无意义（Ollama 会等当前生成完成才卸载）。让用户手动稍后重试更合理。

### 不在范围内（v0.0.12+）

- 取消按钮接 ChatWorker.stop()（加载中可点取消，避免用户在生成中点释放而困惑）
- 加载时长统计 + 慢响应警告（如 5s 无 chunk 提示"Ollama 响应慢"）
- 释放成功后下拉框不选中此模型（当前保留选中态，下次发送会重新加载）
- Ollama 进程级 CUDA 彻底归还（需 Ollama 自身改进，非本项目可控）


---

## ADR-026：硬件监控曲线（sidebar 底部常驻 4 折线）

**日期**：2026-06-20
**版本**：v0.0.12
**状态**：已采纳

### 背景

用户要求"在左侧工具栏增加硬件占用曲线，CPU 和 GPU 实时显示"。需在 sidebar 内常驻一个硬件监控区，覆盖 CPU + GPU + 显存 + 内存 RAM 四指标，实时刷新。

### 决策

1. **位置**：sidebar 底部常驻，固定高度 160px。Sidebar 从 `QListWidget` 改为 `QFrame` 容器（含 `QListWidget` 上半部分 tab 列表 + `HardwareMonitor` 下半部分折线图），保留 `tab_changed` 信号。
2. **指标**：CPU%（蓝 #3B82F6）/ GPU 利用率%（绿 #22C55E）/ VRAM%（紫 #A855F7）/ RAM%（橙 #F97316），4 色高对比可区分。
3. **数据源**：引入 `psutil`（CPU + RAM 跨平台）+ `pynvml`（nvidia-ml-py，NVIDIA GPU 利用率 + 显存）两个运行时依赖，PyInstaller `--collect-all` 打包进 `.exe`，符合 ADR-015 零外部依赖安装硬规则。
4. **采样**：`HardwareMonitorWorker(QThread)` 1s 采集一次样本，`sample_collected(dict)` 信号回主线程，`_on_sample` 追加到各指标历史 list + 截断到 60s + `self.update()` 触发重绘。
5. **渲染**：`paintEvent` 自绘——顶部 20px 图例（色块 + 名称 + 当前数值，无数据时显示 N/A）+ 下方 140px 折线图区域（4 条折线叠加，0-100% y 轴，25%/50%/75% 网格线）。
6. **容错**：`pynvml.nvmlInit()` 失败（无 NVIDIA 显卡 / 驱动问题）时 `_nvml_ok=False`，GPU/VRAM 永远 None，折线画灰色 #475569 N/A 占位横线；`None` 段断开不连线（避免错误跨断点连线）。
7. **生命周期**：`MainWindow.show` 后 `QTimer.singleShot(200, start)` 启动 worker（延迟 200ms 让 UI 先绘制避免首帧空白）；`closeEvent` 调 `worker.stop()`（设 `_stop` flag）+ `worker.wait(2000)` 优雅退出，避免线程悬挂。

### 取舍

- **折线图而非柱状图**：折线展示 60s 历史趋势更直观（用户能看出"5s 前飙升过一次"），柱状图只能看当前瞬间。
- **4 指标叠加而非分 4 个子图**：sidebar 宽度仅 200px，分 4 个子图每个太窄看不清；叠加在同一坐标系 + 4 色区分更紧凑。
- **60s 历史**：足够看趋势，又不至于太长折线挤成一团。1s 一个样本 × 60 = 60 个点，分辨率刚好。
- **psutil + pynvml 而非 GPUtil**：GPUtil 内部也是调 pynvml，多一层封装反而不透明；直接用 pynvml 更可控，且能拿显存（GPUtil 不直接支持）。
- **pynvml import 失败容错而非硬依赖**：让无 NVIDIA 显卡的用户也能用 CPU + RAM 折线，不会因 GPU 不可用就整个组件崩溃。
- **`contextlib.suppress(Exception)` 替代 `try-except-pass`**：ruff 规则要求，更 Pythonic。
- **`--collect-all pynvml` 打包**：pynvml 内部有动态 import 路径（nvidia-ml-py 包名 vs pynvml 模块名），`--collect-all` 确保 .exe 内部能正确找到。
- **worker.stop() + wait(2000)**：先设 flag 让 run 循环早退，再 wait 最多 2s 确保线程真正退出；超时 2s 足够 1s 采样间隔的 msleep 早退。

### 不在范围内（v0.0.13+）

- 采样间隔可配置（用户可在设置中调 1s/2s/5s）
- 历史窗口可配置（60s/120s/300s）
- 写盘持久化（关闭重启后保留历史）
- 单指标点击放大查看（小屏空间不够，需新窗口）
- 报警阈值（如 CPU > 90% 持续 10s 红色高亮）
- 非 NVIDIA GPU 支持（AMD/Intel 需引入额外依赖，等用户提需求）

---

## ADR-027：贴纸式开发原则（v0.0.14 确立）

日期：2026-06-20
状态：接受
取代：无（新增原则，部分扩展 ADR-005 项目框架搭建策略 + 第十九节指令执行自由度）

### 背景

v0.0.12 实施"硬件监控曲线"时，AI 把 `Sidebar` 从 `QListWidget` 改成 `QFrame` 容器内嵌 `HardwareMonitor`，连锁引发 4 个独立问题：
1. QSS 选择器 `QListWidget#Sidebar` 失配（objectName 改了但 QSS 没同步）→ tab item 失去 padding/margin/圆角/选中态，"块变小"
2. tooltip 异常（QListWidget 嵌在 QFrame 内事件层级多一层）
3. SVG 图标消失（打包命令漏 `--add-data`，独立低级错误，跟架构无关但同次出现）
4. 用户对 UI 稳定性信心受损（13 个版本 UI 变了 7+ 次）

用户明确批评："增加功能按键就好像在空白的地方贴一张贴纸，能点击这个按钮影响到的代码也只是这个功能相关的代码。当前这个状态和我一开始设计的严重背离。"

### 决策

确立**贴纸式开发原则**作为本项目 UI 层的核心架构规则：

1. **基座与贴纸划分**：
   - 基座 = v0.0.1 写好的 UI 框架（MainWindow 布局骨架、Sidebar 4 tab、ChatPage、Toolbar、MenuBar、theme QSS、icons 资源系统）。基座写好后永不再动（除非明确扩展公开接口）。
   - 贴纸 = 每个新功能 = 独立 widget 文件 + 父容器一行 `addWidget` 挂载 + 一行信号槽连接。

2. **新功能挂载规范**：
   - 新建独立 widget 文件（如 `q_agent/ui/hardware_monitor.py`），自己管自己的渲染、回调、生命周期
   - 父容器（MainWindow / Page）一行 `addWidget` 挂载，一行信号槽连接
   - 资源集中 `q_agent/assets/icons/`，通过 `load_icon(name)` 引用
   - widget 之间不互相引用，一个崩溃不影响其他（Qt 异常隔离 + 独立信号槽）

3. **架构级改动的判定**（触发第十九节"先展示方案让用户否决"）：
   - 改既有模块的类继承关系（如 QListWidget → QFrame）
   - 改既有模块的 objectName（导致 QSS 选择器失配）
   - 改既有模块的公开接口（信号签名、公开方法签名）
   - 把新功能塞进既有模块内部（而非独立挂载）
   - 以上任一动作 = 架构级改动，必须先展示方案让用户否决，不得以"判断力"为由直接执行

### 取舍

- **贴纸式 vs 容器化内嵌**：容器化看似"紧凑"，但破坏既有模块内聚性，导致 QSS/事件/资源连锁失配。贴纸式牺牲一点布局嵌套（多一层 left panel），换既有模块零侵入，长期可维护性远胜。
- **布局管理器 vs 绝对坐标**：用户原始设想是绝对坐标（VB/Delphi 风格），但聊天消息流/下拉框/动态内容用绝对坐标极痛苦。改用 Qt 布局管理器 + 独立 widget，满足同样隔离需求 + 自动响应式 + 动态内容原生支持。资源占用三者几乎相同（差异 < 1KB，被 PySide6 100MB 级开销淹没）。
- **强制规则 vs 靠 AI 判断力**：第十九节原本给 AI "判断力"空间判断"大决策"，但 v0.0.12 AI 误判"sidebar 容器化"为小改动。第二十一节明文列出架构级改动的具体判定条件，不再靠判断力。

### 不在范围内

- 基座本身的演进（v0.0.1 UI 框架如有结构性缺陷，仍可通过展示方案后重构，本原则只约束"新功能增加"路径）
- 非 UI 层的贴纸式（编排/记忆/技能层是否同样适用，等用户提需求时再讨论）

### 关联

- 扩展 ADR-005（项目框架搭建策略）：基座 = 框架阶段一次性做好的部分
- 扩展第十九节（指令执行自由度）：明文化"架构级改动"的具体判定
- 被本 ADR 修正的历史决策：ADR-026 中"Sidebar 从 QListWidget 改为 QFrame 容器"的部分被 ADR-028 回退

---

## ADR-028：v0.0.12 sidebar 容器化违反贴纸式原则的回退决策（v0.0.14）

日期：2026-06-20
状态：接受
取代：ADR-026 中"Sidebar 从 QListWidget 改为 QFrame 容器"部分

### 背景

v0.0.12 ADR-026 决策"Sidebar 从 QListWidget 改为 QFrame 容器（含 QListWidget 上半部分 tab 列表 + HardwareMonitor 下半部分折线图）"违反 ADR-027 贴纸式开发原则，连锁引发 4 个问题（详见 ADR-027 背景段）。

v0.0.13 尝试治标（QSS 选择器改名 `QListWidget#SidebarList`），但容器化结构还在，tooltip 异常等连锁问题未根除，且打包命令漏 `--add-data` 导致 SVG 图标消失（与架构无关但同次出现的低级错误）。

### 决策

v0.0.14 治本回退 + 贴纸式重构：

1. **sidebar.py 恢复 v0.0.9 QListWidget 子类原貌**：
   - `class Sidebar(QListWidget)`，objectName="Sidebar"
   - 4 tab + 图标 + tooltip + tab_changed 信号
   - 零内嵌 HardwareMonitor（HardwareMonitor 不再是 sidebar 子组件）

2. **main_window.py 新建 left panel 贴纸式挂载**：
   - left panel = QWidget + QVBoxLayout（sidebar stretch=1 + hardware_monitor 底部固定 160px）
   - left_panel.setFixedWidth(200) 放进水平布局左侧
   - `self.hardware_monitor = HardwareMonitor(left_panel)` 一行挂载
   - closeEvent 调 `self.hardware_monitor.stop()` 优雅退出
   - QTimer.singleShot(200, self.hardware_monitor.start) 启动 worker

3. **theme.py 恢复 QSS 选择器**：
   - 4 处 `QListWidget#SidebarList` 改回 `QListWidget#Sidebar`（v0.0.9 原貌）
   - 删除 v0.0.13 新增的 `QFrame#Sidebar` 和 `QListWidget#SidebarList` 选择器

4. **hardware_monitor.py 保持不变**（已是独立模块，符合贴纸式）

5. **打包命令固化**（CLAUDE.md 第十七节补充）：
   - 标准命令必须含 `--add-data "q_agent/assets;q_agent/assets"` + `--collect-all pynvml` + `--collect-all psutil` + `--hidden-import pynvml`
   - 严格从 `安装包/README.md` 复制粘贴，不得手敲删参数

### 取舍

- **回退 vs 继续治标**：v0.0.13 治标只修 QSS 选择器，tooltip 异常/容器化结构问题仍在。回退治本——sidebar 完全恢复 v0.0.9，HardwareMonitor 独立挂载，既有模块零侵入。
- **left panel 多一层嵌套 vs sidebar 容器化**：left panel 多一层 QWidget + QVBoxLayout（多约 100 字节内存），但换 sidebar 完全零改动 + HardwareMonitor 独立可增删。资源差异 < 1KB 可忽略，架构清晰度大幅提升。
- **打包命令固化 vs 靠 AI 记忆**：v0.0.12 AI 凭记忆手敲漏了 `--add-data`。固化到 README.md 模板 + CLAUDE.md 强制规则，下次必须复制粘贴，从机制上杜绝。

### 后果

- v0.0.14 起，sidebar 回到 v0.0.9 稳定基座，后续新功能不得再侵入
- HardwareMonitor 由 MainWindow left panel 一行挂载，删除时只动 main_window.py 一行 + hardware_monitor.py 文件，sidebar 零影响
- 打包命令严格按模板，SVG 图标资源不再漏打包
- CLAUDE.md 第二十一节 + 第十七节补充 + ADR-027/028 共同构成"贴纸式"规则防线，下次 AI（含本 AI）在规则层面就被拦住，不靠判断力

### 关联

- 取代 ADR-026 中"Sidebar 从 QListWidget 改为 QFrame 容器"部分（ADR-026 其余关于 HardwareMonitor 指标/数据源/采样/渲染/容错/生命周期的决策保留不变）
- 落实 ADR-027 贴纸式开发原则的首个执行案例
- 补强第十七节可执行安装包规则（打包命令固化）

---

## ADR-029：硬件监控独立窗口 + menu_bar 回调模式（v0.0.15）

**日期**：2026-06-20
**状态**：生效
**取代**：ADR-026 中"sidebar 底部常驻 HardwareMonitor widget"部分（ADR-026 其余指标/数据源/采样/容错决策保留，ADR-028 已取代容器化部分，本 ADR 进一步取代"挂载位置"部分）

### 背景

v0.0.12 把硬件监控塞进 sidebar 底部（QFrame 容器内嵌），v0.0.14 治本回退为 MainWindow left panel 一行 `addWidget` 挂载——但仍占用 left panel 160px 底部常驻空间。v0.0.15 用户进一步要求："把当前的 GPU 监控相关的从原来的地方移除，在上方文件/帮助的菜单栏添加监控按钮，点击监控会弹出一个独立窗口，显示 GPU 利用率、CPU 利用率、显存占用、内存占用，以及 CPU 和 GPU 的温度。"

### 决策

1. **硬件监控从 left panel 常驻 → 独立窗口**：MainWindow left panel 只剩 sidebar，恢复极简结构。HardwareMonitorWindow（新文件 `q_agent/ui/hardware_monitor_window.py`）作为独立 QWidget 窗口，由 menu_bar "监控"菜单 triggered 弹出。
2. **menu_bar 回调模式扩展公开接口**：MenuBar.__init__ 新增 `monitor_callback: Callable[[], None] | None = None` 参数（类比 Toolbar 的 `status_callback` 注入模式）。新增 `_build_monitor_menu()` 方法，"打开监控"QAction `triggered.connect(monitor_callback)`。不侵入既有 `_build_file_menu` / `_build_help_menu`。
3. **MainWindow 持有 _hw_window 引用**：`_open_hardware_monitor()` 实例化 + show + raise；若已打开则再次 show + raise 激活避免重复实例化；closeEvent 关闭 _hw_window 避免 worker 线程悬挂。
4. **指标扩展为 6 个**：METRICS 增加 `cpu_temp`（Windows psutil 不支持 sensors_temperatures，永远 None）+ `gpu_temp`（pynvml `nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU=0)`）。温度与百分比数值范围 0-100 巧合一致，可共用 y 轴。
5. **hardware_monitor.py 拆分**：只保留 Worker + 常量 + METRICS + collect_sample_sync（测试辅助）；HardwareMonitorWindow + MonitorCell 独立到 hardware_monitor_window.py，符合贴纸式"独立 widget 文件"原则。

### 取舍

- **常驻 vs 独立窗口**：常驻占用 left panel 160px 空间，独立窗口只在需要时弹出。用户明确选择独立窗口，节省主窗口空间。
- **menu_bar callback 注入 vs 直接持引用**：callback 注入保持 MenuBar 通用性（不依赖 MainWindow 实现细节），类比 Toolbar status_callback 已有模式，一致性好。MenuBar 不直接 import HardwareMonitorWindow，避免双向耦合。
- **温度指标加入 vs 维持 4 指标**：用户明确要求显示 CPU/GPU 温度。Windows psutil 不支持 CPU 温度采集，标记 N/A 占位（灰色横线）比强行引入第三方库（如 wmi/LibreHardwareMonitor）更符合"零第三方依赖起步"原则。GPU 温度 pynvml 原生支持，与 GPU 利用率/显存共用 NVML handle 零额外开销。

### 后果

- v0.0.15 起 left panel 仅 sidebar，主窗口空间释放给主内容区
- 硬件监控按需打开，关闭后 worker 优雅停止（`worker.stop() + wait(2000)`）
- menu_bar 获得第二个 callback 注入点（首个为 status_callback），形成"MenuBar 通用 + MainWindow 注入回调"模式，后续新菜单项（如"打开日志"）沿用此模式
- METRICS 6 指标 + 单位字段（% / °C）数据结构定型，MonitorCell 按 unit 切换数值显示格式（`f"{last:.0f}%"` vs `f"{last:.0f}°C"`）

### 关联

- 取代 ADR-026 中"sidebar 底部常驻挂载"部分（ADR-026 其余指标/数据源/采样/容错决策保留）
- 落实 ADR-027 贴纸式开发原则的第二个执行案例（首个为 v0.0.14 left panel 一行挂载）
- 与 ADR-024（加载指示器）共享"独立 widget 文件"贴纸式模式


---

## ADR-030：新建对话/清空按钮接通实际行为（v0.0.16）

**日期**：2026-06-20
**状态**：生效

### 背景

v0.0.1 起 toolbar 左侧就有 new-chat / clear 两个图标按钮，v0.0.8 加 status_callback 占位回显"已点击：新建对话（活 UI 空壳，无实际行为）"。这是接口预留型待办——按钮 UI 早建好，行为没接。chat_page._clear_messages() 在 v0.0.9 已实现（被 model_selected 信号触发用于切换模型清空上下文），可直接复用。

v0.0.16 用户提出审查三个候选（取消按钮/QSettings/新建清空按钮）是否会"把软件返回到之前状态"——审查后确认三个候选都是扩展公开接口而非侵入既有模块，与 v0.0.12 sidebar 容器化错误性质完全不同。

### 决策

1. **Toolbar 扩展 2 个信号**（纯增量扩展公开接口）：
   - `new_chat_requested = Signal()`
   - `clear_requested = Signal()`
   - 类比 v0.0.9 已有 `model_released` 信号模式
2. **_build_actions 改 triggered 目标**：new_chat/clear 的 triggered 从 `_status_callback("活 UI 空壳...")` 改为 `self.new_chat_requested.emit` / `self.clear_requested.emit`
3. **MainWindow 加 2 行 connect**：`toolbar.new_chat_requested.connect(chat_page._clear_messages)` + `toolbar.clear_requested.connect(chat_page._clear_messages)`
4. **chat_page._clear_messages 复用**：v0.0.9 已实现（清空消息流 + 清空 pending AI 气泡状态 + 清空 LoadingDots），零侵入

### 取舍

- **新建对话 vs 清空语义**：当前两个按钮行为都连 _clear_messages（清空消息流）。语义上"新建对话"未来可加更多初始化（如 session_id 重置/计数器清零），但当前实现两者行为一致——这是最小可工作版本，未来扩展只动 new_chat_requested 的连接目标，clear_requested 不动。
- **两个独立信号 vs 合并一个 chat_cleared 信号**：分开两个信号更灵活——未来 new_chat 可加"显示初始问候"等额外行为，clear 保持纯清空。合并一个信号会让两个按钮锁死同行为。
- **连接到 _clear_messages（私有方法）vs 加 public clear() 方法**：_clear_messages 已被 model_selected 信号槽连接（v0.0.9 模式），MainWindow 持有 chat_page 引用调用其方法是 Qt 信号槽常见模式，不需要为接入新按钮暴露 public API。

### 后果

- v0.0.16 起 toolbar 左侧"新建对话"/"清空"按钮有实际行为：清空当前对话消息流
- 状态栏不再显示"活 UI 空壳"占位文案
- chat_page._clear_messages 仍是 v0.0.9 实现，零修改
- Toolbar 类继承/objectName/既有信号全不变，仅新增 2 信号——符合贴纸式原则
- 工具栏第三个按钮"关于"仍保留 status_callback 占位（活 UI 空壳），未来若需要打开关于弹窗可同模式扩展 about_requested 信号

### 关联

- 接口预留型待办首例落地（v0.0.8 留 status_callback 占位 → v0.0.16 接通实际行为）
- 落实 ADR-027 贴纸式原则的第三个执行案例（v0.0.14 left panel 挂载 + v0.0.15 独立窗口 + v0.0.16 toolbar 信号扩展）
- 候选审查报告记录：取消按钮（ChatWorker.stop 接口已留 v0.0.8，待 v0.0.17+）/ QSettings（完全空白，需先出方案避免散弹式侵入三模块）

