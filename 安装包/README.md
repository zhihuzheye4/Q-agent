# 安装包

本目录存放 Q-agent 各里程碑的可执行 `.exe` 文件。

## 规则

- **每完成一个可运行里程碑，必须生成一个 .exe 放到本目录**
- 子目录按版本号命名：`v0.0.1/`、`v0.0.2/`、`v0.1.0/` …
- 每个子目录内含 PyInstaller 打包产物（`Q-agent.exe` + `_internal/`）
- `.exe` 二进制不入 git（已在 `.gitignore` 忽略），目录结构靠 `.gitkeep` + 本 README 保留
- 历史版本长期保留，不删旧版本

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
```

约束：
- `--onefile` 单文件 .exe，零外部依赖安装（CLAUDE.md 第二十节）
- `--windowed` 隐藏控制台窗口（GUI 应用）
- `--add-data` 把 q_agent/assets/ 资源打包进 .exe（SVG + manifest.json）
- 入口脚本 `q_agent/cli.py` 必须含 `if __name__ == "__main__":` 守护，否则 .exe 启动后不调 main()
- .exe 体积约 47MB（含 PySide6 + Qt 全套运行时）

## 版本历史

| 版本 | 日期 | 对应 commit | 说明 |
|------|------|-------------|------|
| v0.0.1 | 2026-06-19 | （本次 commit） | UI 界面空壳版本：4 tab 切换 + 输入框/发送按钮 + 设置面板 + 工具栏 + 菜单栏。活的 UI 无实际功能，对接本地 LLM 留待下一里程碑。47MB .exe 零外部依赖。 |
| v0.0.2 | 2026-06-19 | （本次 commit） | UI 改进：(1) tooltip 透明背景修复白色方块遮盖文字 (2) 气泡宽度比例 0.7→0.92 长发言友好 (3) 设置齿轮换用 Feather settings 经典 8 齿 path（stroke-width=2 渲染完整）(4) 输入框 QLineEdit→QTextEdit 多行支持长发言，Enter 发送 Shift+Enter 换行，高度 44-200px 自适应。45MB .exe 零外部依赖。 |
| v0.0.3 | 2026-06-19 | （本次 commit） | UI 改进：输入框高度随内容动态变化——监听 documentLayout().documentSizeChanged 信号，根据文档实际高度在 [44, 200] 之间钳制 setFixedHeight，超出 200px 显示滚动条，清空回 44。45MB .exe 零外部依赖。 |
| v0.0.4 | 2026-06-20 | 54abe5f | 第一个填充实际功能：UI 右上角加模型下拉框 + 刷新按钮，启动时异步检测本地 Ollama 模型（GET /api/tags）。用 urllib 标准库零新运行时依赖；ModelRefreshWorker(QThread) 后台跑避免阻塞 UI；检测失败显示"未发现本地 LLM"占位项 + 状态栏提示。47MB .exe 零外部依赖。 |