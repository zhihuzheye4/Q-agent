# UI 资源目录

本目录存放 Q-agent 软件本体调用的资源文件。

## 子目录

### `icons/` — UI 界面矢量图

- **只存** UI 界面调用的矢量图（SVG 格式）
- **不存** 位图（PNG/JPG）、字体、音频、配置文件等其他资源
- **不存** 开发文档用的图（那些放 `memory/` 或根目录）
- 命名规范：`图标名-状态.svg`，如 `send-active.svg`、`send-disabled.svg`
- 调用方案：SVG sprite + QtSvg 首次缓存（见 ADR-014）。脚本预制，UI 启动时 `QSvgRenderer` 加载 sprite 按 id 渲染到 `QPixmap` 缓存，显示时调缓存。
- 当前为空目录（仅 `.gitkeep`），等 UI 界面真正需要图标时再用 `scripts/generate_icons.py` 生成。

## 图标生成脚本

脚本路径：`scripts/generate_icons.py`（dev 辅助脚本，不在分发包内）

调用方式：

```bash
# F 盘 venv 内执行
python scripts/generate_icons.py              # 生成 SVG（默认）
python scripts/generate_icons.py --png        # SVG + PNG（按需，用 PySide6.QtSvg 转）
python scripts/generate_icons.py --output <dir>  # 自定义输出目录
python scripts/generate_icons.py --clean      # 清理输出目录测试产物
```

设计哲学：
1. 预制调用而非实时渲染——脚本开发期一次性生成，UI 运行时只读文件
2. PNG 转换按需使用——`--png` 是显式开关，默认关闭（像电脑开机不需要把所有软件全开）
3. 测试产物验证完上限后删除（`--clean`），避免文件杂乱臃肿

技术栈：PySide6（Qt 6 官方 Python 绑定，LGPL 商用免费），QtSvg 模块内置（矢量图渲染零额外依赖）。

## 打包说明

`q_agent/assets/` 是包内资源，会被 PyInstaller 一起打包进 .exe，UI 代码用 `importlib.resources` 或 `pathlib.Path(__file__).parent / "assets"` 访问。

分发零外部依赖硬规则（CLAUDE.md 第二十节）：最终用户拿 `.exe` 双击即跑，所有运行时依赖（含 PySide6 + QtSvg + 资源）由 PyInstaller `--onefile` 打包进单个 `.exe`。