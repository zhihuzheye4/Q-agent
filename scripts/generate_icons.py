"""
Q-agent UI 矢量图生成脚本

输入：内置图标定义 + 可选设计规范文件
输出：q_agent/assets/icons/*.svg  +  manifest.json  +  可选 *.png

调用方式：
    python scripts/generate_icons.py              # 只生成 SVG（默认）
    python scripts/generate_icons.py --png        # SVG + PNG（按需，用 PySide6.QtSvg 转）
    python scripts/generate_icons.py --output <dir>  # 自定义输出目录
    python scripts/generate_icons.py --clean      # 清理输出目录（删测试产物用）

设计哲学：
    1. 预制调用而非实时渲染——脚本开发期一次性生成，UI 运行时只读文件
    2. PNG 转换按需使用——脚本"有"这能力不等于"必须"用，--png 是显式开关
    3. 测试产物验证完上限后删除，避免文件杂乱臃肿

5 级递进复杂度测试图标（测脚本生成上限）：
    L1 circle-active        单一圆，~5 行
    L2 send-active           纸飞机多 path，~15 行
    L3 settings-active       8 齿齿轮 transform rotate 复用，~30 行
    L4 cloud-sync-active     云 + 循环箭头 + 渐变，~60 行
    L5 ai-brain-active       大脑 + 电路纹理 + 滤镜 + 多色渐变，~150 行
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT_DIR_DEFAULT = BASE / "q_agent" / "assets" / "icons"

VIEWBOX = "0 0 24 24"
STROKE_WIDTH = 2
STROKE_COLOR = "currentColor"
FILL_NONE = "none"


# ===== 基础几何 primitive（返回 SVG XML 片段） =====


def _attrs(**attrs: object) -> str:
    """把 key=value 转成 SVG 属性字符串（key 下划线转短横）"""
    parts = []
    for k, v in attrs.items():
        if v is None:
            continue
        key = k.replace("_", "-")
        parts.append(f'{key}="{v}"')
    return " ".join(parts)


def circle(cx: float, cy: float, r: float, **attrs: object) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" {_attrs(**attrs)}/>'


def rect(x: float, y: float, w: float, h: float, **attrs: object) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" {_attrs(**attrs)}/>'


def path(d: str, **attrs: object) -> str:
    return f'<path d="{d}" {_attrs(**attrs)}/>'


def polygon(points: str, **attrs: object) -> str:
    return f'<polygon points="{points}" {_attrs(**attrs)}/>'


def line(x1: float, y1: float, x2: float, y2: float, **attrs: object) -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {_attrs(**attrs)}/>'


def group(children: list[str], **attrs: object) -> str:
    body = "\n    ".join(children)
    attr_str = _attrs(**attrs)
    open_tag = f"<g {attr_str}>" if attr_str else "<g>"
    return f"{open_tag}\n    {body}\n  </g>"


# ===== defs 节点（渐变/滤镜，供图标引用） =====


def linear_gradient(id_: str, stops: list[tuple[float, str]]) -> str:
    """线性渐变，stops = [(offset, color), ...]"""
    stop_xml = "\n    ".join(f'<stop offset="{off}" stop-color="{col}"/>' for off, col in stops)
    return f'<linearGradient id="{id_}">\n    {stop_xml}\n  </linearGradient>'


def radial_gradient(
    id_: str,
    stops: list[tuple[float, str]],
    cx: float = 0.5,
    cy: float = 0.5,
    r: float = 0.5,
) -> str:
    stop_xml = "\n    ".join(f'<stop offset="{off}" stop-color="{col}"/>' for off, col in stops)
    return (
        f'<radialGradient id="{id_}" cx="{cx}" cy="{cy}" r="{r}">\n'
        f"    {stop_xml}\n"
        f"  </radialGradient>"
    )


def filter_drop_shadow(
    id_: str,
    dx: float = 0,
    dy: float = 1,
    std_dev: float = 1.5,
    flood: str = "#000000",
    flood_opacity: float = 0.4,
) -> str:
    return (
        f'<filter id="{id_}" x="-50%" y="-50%" width="200%" height="200%">\n'
        f'    <feDropShadow dx="{dx}" dy="{dy}" stdDeviation="{std_dev}" '
        f'flood-color="{flood}" flood-opacity="{flood_opacity}"/>\n'
        f"  </filter>"
    )


# ===== 渲染器 =====


def render_svg(body: str, defs: str = "", viewBox: str = VIEWBOX) -> str:
    """组装完整 SVG XML，含 xmlns + defs + body

    顶层默认属性（参考 Lucide / Feather 现代图标库）：
        fill=none + stroke=currentColor + stroke-width=2
        stroke-linecap=round + stroke-linejoin=round（线条柔和，视觉精致）
    """
    defs_block = f"  <defs>\n    {defs}\n  </defs>\n" if defs else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewBox}" '
        f'fill="{FILL_NONE}" stroke="{STROKE_COLOR}" stroke-width="{STROKE_WIDTH}" '
        f'stroke-linecap="round" stroke-linejoin="round">\n'
        f"{defs_block}"
        f"  {body}\n"
        f"</svg>"
    )


# ===== 5 级递进复杂度图标定义 =====


def icon_circle_active() -> str:
    """L1 简单：圆（参考 Lucide circle，r=9 视觉饱满）"""
    body = circle(12, 12, 9)
    return render_svg(body)


def icon_send_active() -> str:
    """L2 中等：纸飞机（Lucide send 官方 path）"""
    body = group(
        [
            path("m22 2-7 20-4-9-9-4Z"),
            path("M22 2 11 13"),
        ]
    )
    return render_svg(body)


def icon_settings_active() -> str:
    """L3 复杂：齿轮（Feather settings 经典 8 齿轮廓 + 中心圆，stroke-width=2 渲染完整）"""
    # Feather "settings" 标准 path：外圈带 8 个小凸起（视觉上即齿轮齿）
    gear_outer = (
        "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06"
        "a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2"
        "v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0"
        " 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3"
        "a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82"
        "l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9"
        "a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51"
        " 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06"
        "a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2"
        "h-.09a1.65 1.65 0 0 0-1.51 1z"
    )
    body = group(
        [
            path(gear_outer),
            circle(12, 12, 3),
        ]
    )
    return render_svg(body)


def icon_cloud_sync_active() -> str:
    """L4 高复杂：云（Lucide cloud）+ 双向循环箭头（refresh-cw 缩小）+ 线性渐变"""
    defs = linear_gradient(
        "cloudGrad",
        [(0, "#4A90E2"), (1, "#1B4F9C")],
    )
    # Lucide cloud 标准云形
    cloud = path(
        "M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z",
        fill="url(#cloudGrad)",
        stroke=FILL_NONE,
    )
    # 同步循环箭头（refresh 风格，缩小到云中央 ~12,13，半径 2.8）
    # 上半弧 + 箭头
    arc_up = path(
        "M9.5 12.5a2.8 2.8 0 0 1 4.6-.8L15 11.5",
        stroke="white",
        stroke_width=1.5,
    )
    arrow_up_head = polygon("15 9 15 12 12.5 11", fill="white", stroke=FILL_NONE)
    # 下半弧 + 箭头
    arc_down = path(
        "M14.5 13.5a2.8 2.8 0 0 1-4.6.8L9 14.5",
        stroke="white",
        stroke_width=1.5,
    )
    arrow_down_head = polygon("9 17 9 14 11.5 15", fill="white", stroke=FILL_NONE)
    body = group(
        [
            cloud,
            arc_up,
            arrow_up_head,
            arc_down,
            arrow_down_head,
        ]
    )
    return render_svg(body, defs=defs)


def icon_ai_brain_active() -> str:
    """L5 极限：大脑（Lucide brain 简化）+ 电路纹理 + 阴影滤镜 + 多色渐变"""
    defs = "  ".join(
        [
            linear_gradient(
                "brainGrad",
                [(0, "#9B5DE5"), (0.5, "#F15BB5"), (1, "#FEE440")],
            ),
            radial_gradient("nodeGrad", [(0, "#00BBF9"), (1, "#0055AA")]),
            filter_drop_shadow(
                "brainShadow",
                dx=0,
                dy=1.5,
                std_dev=1.2,
                flood="#5B08A5",
                flood_opacity=0.5,
            ),
        ]
    )
    # 大脑左右半球（基于 Lucide brain path 简化）
    brain_left = path(
        "M9.5 4A3.5 3.5 0 0 0 6 7.5v.27a3.5 3.5 0 0 1-1.5 2.83l-.27.16"
        "a3.5 3.5 0 0 0 0 6.06l.27.16a3.5 3.5 0 0 1 1.5 2.83v.27"
        "a3.5 3.5 0 0 0 3.5 3.5h.5V4Z",
        fill="url(#brainGrad)",
        stroke=FILL_NONE,
        filter="url(#brainShadow)",
    )
    brain_right = path(
        "M14.5 4A3.5 3.5 0 0 1 18 7.5v.27a3.5 3.5 0 0 0 1.5 2.83l.27.16"
        "a3.5 3.5 0 0 1 0 6.06l-.27.16a3.5 3.5 0 0 0-1.5 2.83v.27"
        "a3.5 3.5 0 0 1-3.5 3.5H14V4Z",
        fill="url(#brainGrad)",
        stroke=FILL_NONE,
        filter="url(#brainShadow)",
    )
    # 沟回（大脑纹理，白色细线）
    sulci = group(
        [
            path("M7 8q1.5 1 1.5 3t-1.5 3", stroke="white", stroke_width=0.8),
            path("M9 10q1 1 0 3", stroke="white", stroke_width=0.8),
            path("M17 8q-1.5 1-1.5 3t1.5 3", stroke="white", stroke_width=0.8),
            path("M15 10q-1 1 0 3", stroke="white", stroke_width=0.8),
            path("M12 6v12", stroke="white", stroke_width=0.6),
        ]
    )
    # 电路节点（连接线 + 节点圆）
    circuit = group(
        [
            line(3, 7, 6, 9, stroke="#00BBF9", stroke_width=1),
            line(21, 7, 18, 9, stroke="#00BBF9", stroke_width=1),
            line(3, 17, 6, 15, stroke="#00BBF9", stroke_width=1),
            line(21, 17, 18, 15, stroke="#00BBF9", stroke_width=1),
            circle(3, 7, 1.2, fill="url(#nodeGrad)", stroke=FILL_NONE),
            circle(21, 7, 1.2, fill="url(#nodeGrad)", stroke=FILL_NONE),
            circle(3, 17, 1.2, fill="url(#nodeGrad)", stroke=FILL_NONE),
            circle(21, 17, 1.2, fill="url(#nodeGrad)", stroke=FILL_NONE),
        ]
    )
    body = group(
        [
            brain_left,
            brain_right,
            sulci,
            circuit,
        ]
    )
    return render_svg(body, defs=defs)


# ===== UI 界面图标（Q-agent 实际使用的，参考 Lucide / Feather 风格） =====


def icon_chat_active() -> str:
    """对话 tab：消息气泡（Lucide message-circle 简化）"""
    body = path(
        "M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"  # noqa: E501
    )
    return render_svg(body)


def icon_skills_active() -> str:
    """技能 tab：星形（Lucide sparkles 简化，象征能力/技能）"""
    body = group(
        [
            path(
                "M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.582a.5.5 0 0 1 0 .962L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"  # noqa: E501
            ),
            path("M20 3v4"),
            path("M22 5h-4"),
            path("M4 17v2"),
            path("M5 18H3"),
        ]
    )
    return render_svg(body)


def icon_memory_active() -> str:
    """记忆 tab：数据库柱体（Lucide database 简化）"""
    body = group(
        [
            path("M12 2C6.5 2 2 3.6 2 5.5S6.5 9 12 9s10-1.6 10-3.5S17.5 2 12 2z"),
            path("M2 5.5v6C2 13.4 6.5 15 12 15s10-1.6 10-3.5v-6"),
            path("M2 11.5v6C2 19.4 6.5 21 12 21s10-1.6 10-3.5v-6"),
        ]
    )
    return render_svg(body)


def icon_new_chat_active() -> str:
    """工具栏：新建对话（加号 + 消息气泡）"""
    body = group(
        [
            path("M12 5v14"),
            path("M5 12h14"),
        ]
    )
    return render_svg(body)


def icon_clear_active() -> str:
    """工具栏：清空（Lucide trash 简化）"""
    body = group(
        [
            path("M3 6h18"),
            path("M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"),
            path("M10 11v6"),
            path("M14 11v6"),
        ]
    )
    return render_svg(body)


def icon_about_active() -> str:
    """工具栏：关于（Lucide info 圆 + i）"""
    body = group(
        [
            circle(12, 12, 10),
            path("M12 16v-4"),
            path("M12 8h.01"),
        ]
    )
    return render_svg(body)


def icon_stop_active() -> str:
    """工具栏：取消生成（外圈圆形描边 + 内部红色方块，停止符号）"""
    body = group(
        [
            circle(12, 12, 10),
            rect(8.5, 8.5, 7, 7, **{"fill": "#EF4444", "stroke": "none"}),
        ]
    )
    return render_svg(body)


def icon_refresh_active() -> str:
    """工具栏：刷新（Lucide refresh-cw 双圆弧箭头）"""
    body = group(
        [
            path("M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"),
            path("M21 3v5h-5"),
            path("M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"),
            path("M3 21v-5h5"),
        ]
    )
    return render_svg(body)


def icon_tool_pending_active() -> str:
    """工具气泡：执行中（蓝色齿轮，#4A9FFA）"""
    body = group(
        [
            circle(12, 12, 9, **{"stroke": "#4A9FFA"}),
            path("M12 6v3", **{"stroke": "#4A9FFA"}),
            path("M12 15v3", **{"stroke": "#4A9FFA"}),
            path("M6 12h3", **{"stroke": "#4A9FFA"}),
            path("M15 12h3", **{"stroke": "#4A9FFA"}),
        ]
    )
    return render_svg(body)


def icon_tool_success_active() -> str:
    """工具气泡：成功（绿色圆勾，#3FB950）"""
    body = group(
        [
            circle(12, 12, 9, **{"stroke": "#3FB950"}),
            path("M8 12l3 3 5-6", **{"stroke": "#3FB950"}),
        ]
    )
    return render_svg(body)


def icon_tool_failed_active() -> str:
    """工具气泡：失败（红色圆叉，#F85149）"""
    body = group(
        [
            circle(12, 12, 9, **{"stroke": "#F85149"}),
            path("M9 9l6 6", **{"stroke": "#F85149"}),
            path("M15 9l-6 6", **{"stroke": "#F85149"}),
        ]
    )
    return render_svg(body)


def icon_tool_cancelled_active() -> str:
    """工具气泡：取消（灰色圆圈横线，#8B949E）"""
    body = group(
        [
            circle(12, 12, 9, **{"stroke": "#8B949E"}),
            path("M8 12h8", **{"stroke": "#8B949E"}),
        ]
    )
    return render_svg(body)


# ===== 图标注册表 =====


ICONS: list[tuple[str, str, Callable[[], str]]] = [
    # 5 级递进复杂度测试图标（保留作测试样本）
    ("circle-active", "L1", icon_circle_active),
    ("send-active", "L2", icon_send_active),
    ("settings-active", "L3", icon_settings_active),
    ("cloud-sync-active", "L4", icon_cloud_sync_active),
    ("ai-brain-active", "L5", icon_ai_brain_active),
    # UI 界面实际调用图标
    ("chat-active", "UI", icon_chat_active),
    ("skills-active", "UI", icon_skills_active),
    ("memory-active", "UI", icon_memory_active),
    ("new-chat-active", "UI", icon_new_chat_active),
    ("clear-active", "UI", icon_clear_active),
    ("about-active", "UI", icon_about_active),
    ("refresh-active", "UI", icon_refresh_active),
    ("stop-active", "UI", icon_stop_active),
    # v0.0.19 工具气泡 4 状态图标
    ("tool-pending-active", "UI", icon_tool_pending_active),
    ("tool-success-active", "UI", icon_tool_success_active),
    ("tool-failed-active", "UI", icon_tool_failed_active),
    ("tool-cancelled-active", "UI", icon_tool_cancelled_active),
]


# ===== 输出器 =====


def write_svg(svg: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def svg_to_png(svg_path: Path, png_path: Path) -> None:
    """用 PySide6.QtSvg.QSvgRenderer 渲染 SVG 到 PNG（延迟 import）"""
    from PySide6.QtCore import QCoreApplication, QSize, Qt  # type: ignore[import-not-found]
    from PySide6.QtGui import QImage, QPainter  # type: ignore[import-not-found]
    from PySide6.QtSvg import QSvgRenderer  # type: ignore[import-not-found]

    QCoreApplication([])  # 初始化 QApp 必需
    renderer = QSvgRenderer(svg_path.read_bytes())
    size = QSize(128, 128)
    img = QImage(size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    img.save(str(png_path), "PNG")


def write_manifest(icons_meta: list[dict[str, object]], path: Path) -> None:
    manifest = {
        "version": "0.0.1",
        "viewBox": VIEWBOX,
        "icons": icons_meta,
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


# ===== 清理 =====


def clean_output(out_dir: Path) -> int:
    """删除输出目录下所有 .svg / .png / manifest.json（保留 .gitkeep + README.md）"""
    removed = 0
    for pattern in ("*.svg", "*.png", "manifest.json"):
        for p in out_dir.glob(pattern):
            p.unlink()
            removed += 1
    return removed


# ===== 主入口 =====


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Q-agent UI 矢量图生成脚本（5 级递进复杂度测试上限）"
    )
    parser.add_argument(
        "--png",
        action="store_true",
        help="同时生成 PNG（按需，用 PySide6.QtSvg 转）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR_DEFAULT,
        help="输出目录",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理输出目录测试产物（保留 .gitkeep + README）",
    )
    args = parser.parse_args()

    out_dir = args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.clean:
        n = clean_output(out_dir)
        print(f"[清理] 已删除 {n} 个测试产物")
        return

    print(f"[生成] 输出目录：{out_dir}")
    icons_meta: list[dict[str, object]] = []
    total_start = time.perf_counter()

    for name, level, fn in ICONS:
        t0 = time.perf_counter()
        svg = fn()
        elapsed = (time.perf_counter() - t0) * 1000
        svg_path = out_dir / f"{name}.svg"
        write_svg(svg, svg_path)
        size_kb = svg_path.stat().st_size / 1024
        print(f"  [{level}] {name}.svg  {size_kb:.2f} KB  {elapsed:.2f} ms")
        meta: dict[str, object] = {
            "name": name,
            "file": f"{name}.svg",
            "level": level,
        }
        if args.png:
            png_path = out_dir / f"{name}.png"
            svg_to_png(svg_path, png_path)
            meta["png"] = f"{name}.png"
            print(f"         └─ {name}.png 已生成")
        icons_meta.append(meta)

    manifest_path = out_dir / "manifest.json"
    write_manifest(icons_meta, manifest_path)

    total_ms = (time.perf_counter() - total_start) * 1000
    print(f"[完成] {len(ICONS)} 个图标，总耗时 {total_ms:.2f} ms")
    print(f"[完成] manifest.json 已写入 {manifest_path}")


if __name__ == "__main__":
    main()
