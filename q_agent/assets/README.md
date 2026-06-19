# UI 资源目录

本目录存放 Q-agent 软件本体调用的资源文件。

## 子目录

### `icons/` — UI 界面矢量图

- **只存** UI 界面调用的矢量图（SVG 格式）
- **不存** 位图（PNG/JPG）、字体、音频、配置文件等其他资源
- **不存** 开发文档用的图（那些放 `memory/` 或根目录）
- 命名规范：`图标名-状态.svg`，如 `send-active.svg`、`send-disabled.svg`
- 当前为空目录，等 UI 界面实现时再填充

## 打包说明

`q_agent/assets/` 是包内资源，会被 PyInstaller 一起打包进 .exe，UI 代码用 `importlib.resources` 或 `pathlib.Path(__file__).parent / "assets"` 访问。