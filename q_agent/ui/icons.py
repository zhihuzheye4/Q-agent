"""图标加载（方案 D：QIcon 直接受 SVG + manifest.json 索引）。

方案 D 核心：
    - 每个 SVG 文件离散存放（不用 sprite 聚合）
    - QIcon(str(svg_path)) 直接接受 SVG，Qt 内部 QSvgIconEngine 按渲染 size 智能缓存
    - 显示到哪个图标哪个尺寸才首次渲染——按需渲染而非全量预热
    - 任意缩放/主题切换由 Qt 自行处理

依赖：
    - q_agent/assets/icons/manifest.json（由 scripts/generate_icons.py 生成）
    - q_agent/assets/icons/*.svg（同上）
    - PySide6.QtGui.QIcon

资源访问：
    - 用 importlib.resources 兼容 PyInstaller --onefile 打包（资源解压到 _MEIPASS）
    - fallback 到 Path(__file__).parent.parent / "assets" / "icons"（开发期直接读源码树）
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _resolve_icons_dir() -> Path:
    """解析图标目录路径，兼容 PyInstaller 打包 + 开发期源码树。"""
    try:
        from importlib.resources import files

        return Path(str(files("q_agent") / "assets" / "icons"))
    except Exception:
        return Path(__file__).resolve().parent.parent / "assets" / "icons"


ICONS_DIR = _resolve_icons_dir()


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, Any]:
    """加载 manifest.json 一次，缓存图标名→元数据映射。"""
    manifest_path = ICONS_DIR / "manifest.json"
    if not manifest_path.exists():
        return {"version": "0.0.1", "icons": []}
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data


def icon_path(name: str, state: str = "active") -> Path:
    """根据图标名+状态返回 SVG 文件路径。

    Args:
        name: 图标名（如 "send" / "chat" / "settings"）
        state: 状态（active / disabled / hover），默认 active
    """
    return ICONS_DIR / f"{name}-{state}.svg"


def load_icon(name: str, state: str = "active") -> Any:
    """方案 D 核心：QIcon 直接受 SVG 文件，Qt 内部按 size 智能缓存。

    延迟 import PySide6 让无 PySide6 环境下 import 此模块不崩。
    """
    from PySide6.QtGui import QIcon

    svg_path = icon_path(name, state)
    if not svg_path.exists():
        return QIcon()
    return QIcon(str(svg_path))


def list_icons() -> list[str]:
    """列出 manifest.json 中所有图标名（去重）。"""
    manifest = load_manifest()
    return list({item["name"].rsplit("-", 1)[0] for item in manifest.get("icons", [])})
