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
