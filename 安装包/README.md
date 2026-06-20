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
| v0.0.13 | 2026-06-20 | _未 commit，被 v0.0.14 覆盖_ | 治标不治本的尝试：修复 v0.0.12 sidebar 容器化改造遗留的 QSS 选择器失配（theme.py 4 处 `QListWidget#Sidebar` → `QListWidget#SidebarList` + 新增 `QFrame#Sidebar` 背景样式）。用户验证后 tab 大小恢复但**图标仍未出现 + tooltip 消失**——根因是 v0.0.12 打包命令漏 `--add-data` 导致 SVG 没进 .exe（独立低级错误）+ sidebar 容器化结构本身违反贴纸式原则。用户提出"贴纸式开发"哲学批评后，v0.0.13 治标方案被废弃，v0.0.14 治本回退。v0.0.13 的 QSS 选择器改动被 v0.0.14 反向覆盖（改回 `#Sidebar`），未单独 commit，仅作版本历史留痕。 |
| v0.0.14 | 2026-06-20 | _pending_ | **贴纸式重构治本回退**：① sidebar.py 恢复 v0.0.9 QListWidget 子类原貌（`class Sidebar(QListWidget)` + objectName="Sidebar" + 4 tab + 图标 + tooltip + tab_changed 信号，零内嵌 HardwareMonitor）；② main_window.py 新建 left panel（QWidget + QVBoxLayout：sidebar stretch=1 + hardware_monitor 底部固定 160px，整体 fixed 200px 宽放进水平布局左侧）——HardwareMonitor 改由 MainWindow 一行 `addWidget` 贴纸式挂载，sidebar 完全不碰；③ theme.py 4 处 QSS 选择器改回 `QListWidget#Sidebar`，删除 v0.0.13 新增的 `QFrame#Sidebar` 和 `QListWidget#SidebarList`；④ 打包命令严格按 README.md 标准模板（含 `--add-data "q_agent/assets;q_agent/assets"` + `--hidden-import pynvml` + `--collect-all pynvml/psutil`）——修复 v0.0.12 漏 `--add-data` 导致 SVG 图标消失的低级错误；⑤ CLAUDE.md 新增第二十一节"贴纸式开发原则"（基座永不动 + 新功能独立 widget + 父容器一行挂载 + 改既有类继承/objectName/公开接口 = 架构级改动触发第十九节先展示）+ 第十七节补充"打包命令必须严格从 README.md 复制粘贴，不得手敲删参数"；⑥ ADR-027 贴纸式开发原则 + ADR-028 v0.0.12 sidebar 容器化回退决策。测试 144 通过，84.25% 覆盖率，ruff/mypy strict 全绿。 |