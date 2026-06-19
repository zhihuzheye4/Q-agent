# 安装包

本目录存放 Q-agent 各里程碑的可执行 `.exe` 文件。

## 规则

- **每完成一个可运行里程碑，必须生成一个 .exe 放到本目录**
- 子目录按版本号命名：`v0.0.1/`、`v0.0.2/`、`v0.1.0/` …
- 每个子目录内含 PyInstaller 打包产物（`Q-agent.exe` + `_internal/`）
- `.exe` 二进制不入 git（已在 `.gitignore` 忽略），目录结构靠 `.gitkeep` + 本 README 保留
- 历史版本长期保留，不删旧版本

## 打包命令（待 PyInstaller 安装后启用）

```bash
# F 盘 venv 内执行
pyinstaller --distpath 安装包 --name Q-agent --onefile q_agent/cli.py
```

## 版本历史

| 版本 | 日期 | 对应 commit | 说明 |
|------|------|-------------|------|
| （待生成 v0.0.1） | - | - | 项目框架搭建版本，等 PyInstaller 安装后生成 |