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