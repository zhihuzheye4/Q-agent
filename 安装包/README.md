# 安装包

本目录存放 Q-agent 当前里程碑的可执行 `.exe` 文件。

## 规则

- **每完成一个可运行里程碑，必须生成一个 .exe 放到本目录**
- 子目录按版本号命名：`v0.0.5/`、`v0.0.6/` …
- 每个子目录内含 PyInstaller 打包产物（`Q-agent.exe`）
- `.exe` 二进制不入 git（已在 `.gitignore` 忽略），目录结构靠 `.gitkeep` + 本 README 保留
- **只保留最新一代**：每次打新版本时，删掉旧版本子目录，只留当前最新版本（2026-06-20 用户明确修改，避免冗余历史 .exe 占空间；版本演进历史靠下方"版本历史"表 + git log 即可）

## 打包命令（F 盘 venv 内执行）

```bash
pyinstaller \
  --distpath 安装包 \
  --workpath build \
  --name Q-agent \
  --onefile \
  --windowed \
  --add-data "q_agent/assets;q_agent/assets" \
  --clean --noconfirm q_agent/cli.py
# 打包后把 安装包/Q-agent.exe 移到 安装包/v{版本}/Q-agent.exe
# 同时删除上一版子目录，只留当前最新
```

约束：
- `--onefile` 单文件 .exe，零外部依赖安装（CLAUDE.md 第二十节）
- `--windowed` 隐藏控制台窗口（GUI 应用）
- `--add-data` 把 q_agent/assets/ 资源打包进 .exe（SVG + manifest.json）
- 入口脚本 `q_agent/cli.py` 必须含 `if __name__ == "__main__":` 守护，否则 .exe 启动后不调 main()
- .exe 体积约 47MB（含 PySide6 + Qt 全套运行时）

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