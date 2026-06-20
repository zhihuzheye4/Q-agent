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