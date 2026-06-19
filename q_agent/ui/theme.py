"""QSS 暗色主题（从 memory/设计规范/MASTER.md 翻译）。

设计 token 来源：/ui-ux-pro-max skill --design-system -f markdown
- Style: Dark Mode (OLED)
- Background: #0F172A（窗口背景）
- Primary: #1E293B（侧边栏 / 工具栏背景）
- Secondary: #334155（次级按钮 / 悬停）
- Accent: #22C55E（发送按钮 / CTA，绿色）
- Foreground: #F8FAFC（主文字）
- Muted: #272F42（占位符 / 禁用）
- Border: #475569（边框 / 分隔线）
- Destructive: #EF4444（删除）
- Ring: #1E293B（焦点环）

字体：Inter（设计规范要求），但 Windows 系统未预装 → fallback 到默认（Segoe UI）。
本次为活 UI 空壳，字体升级留待用户提"字体优化"需求。
"""

from __future__ import annotations

from typing import Any

# === 设计 token 常量（供 Python 代码引用，如 setStyleSheet 外的颜色操作） ===

COLOR_PRIMARY = "#1E293B"
COLOR_ON_PRIMARY = "#FFFFFF"
COLOR_SECONDARY = "#334155"
COLOR_ACCENT = "#22C55E"
COLOR_BACKGROUND = "#0F172A"
COLOR_FOREGROUND = "#F8FAFC"
COLOR_MUTED = "#272F42"
COLOR_BORDER = "#475569"
COLOR_DESTRUCTIVE = "#EF4444"
COLOR_RING = "#1E293B"

FONT_FAMILY = "Inter, 'Segoe UI', 'Microsoft YaHei', sans-serif"

# === QSS 全局主题 ===

DARK_QSS = f"""
* {{
    font-family: {FONT_FAMILY};
    color: {COLOR_FOREGROUND};
}}

QMainWindow, QWidget {{
    background-color: {COLOR_BACKGROUND};
}}

/* ===== 侧边栏 ===== */
QListWidget#Sidebar {{
    background-color: {COLOR_PRIMARY};
    border: none;
    border-right: 1px solid {COLOR_BORDER};
    outline: 0;
    padding: 8px 4px;
}}
QListWidget#Sidebar::item {{
    color: {COLOR_FOREGROUND};
    padding: 12px 16px;
    border-radius: 6px;
    margin: 2px 4px;
}}
QListWidget#Sidebar::item:hover {{
    background-color: {COLOR_SECONDARY};
}}
QListWidget#Sidebar::item:selected {{
    background-color: {COLOR_SECONDARY};
    border-left: 2px solid {COLOR_ACCENT};
    color: {COLOR_FOREGROUND};
}}

/* ===== 主内容区 ===== */
QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {COLOR_BACKGROUND};
}}

/* ===== 对话消息流 ===== */
QLabel#MessageUser {{
    background-color: {COLOR_SECONDARY};
    color: {COLOR_FOREGROUND};
    padding: 10px 14px;
    border-radius: 10px;
    border-top-right-radius: 2px;
}}
QLabel#MessageAI {{
    background-color: {COLOR_MUTED};
    color: {COLOR_FOREGROUND};
    padding: 10px 14px;
    border-radius: 10px;
    border-top-left-radius: 2px;
}}
QLabel#MessagePlaceholder {{
    color: {COLOR_MUTED};
    padding: 24px;
    font-size: 13px;
}}

/* ===== 输入框 ===== */
QLineEdit#ChatInput {{
    background-color: {COLOR_MUTED};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 10px 14px;
    color: {COLOR_FOREGROUND};
    selection-background-color: {COLOR_ACCENT};
}}
QLineEdit#ChatInput:focus {{
    border: 2px solid {COLOR_RING};
    padding: 9px 13px;
}}

/* ===== 按钮 ===== */
QPushButton {{
    background-color: {COLOR_PRIMARY};
    color: {COLOR_ON_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    min-width: 64px;
}}
QPushButton:hover {{
    background-color: {COLOR_SECONDARY};
    border: 1px solid {COLOR_FOREGROUND};
}}
QPushButton:pressed {{
    background-color: {COLOR_MUTED};
}}
QPushButton:disabled {{
    background-color: {COLOR_MUTED};
    color: {COLOR_BORDER};
}}

QPushButton#SendButton {{
    background-color: {COLOR_ACCENT};
    color: {COLOR_ON_PRIMARY};
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}}
QPushButton#SendButton:hover {{
    background-color: #16A34A;
}}
QPushButton#SendButton:pressed {{
    background-color: #15803D;
}}
QPushButton#SendButton:disabled {{
    background-color: {COLOR_MUTED};
    color: {COLOR_BORDER};
}}

/* ===== 工具栏 ===== */
QToolBar {{
    background-color: {COLOR_PRIMARY};
    border: none;
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 4px 8px;
    spacing: 4px;
}}
QToolBar QToolButton {{
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    color: {COLOR_FOREGROUND};
}}
QToolBar QToolButton:hover {{
    background-color: {COLOR_SECONDARY};
}}
QToolBar QToolButton:pressed {{
    background-color: {COLOR_MUTED};
}}

/* ===== 菜单栏 ===== */
QMenuBar {{
    background-color: {COLOR_PRIMARY};
    color: {COLOR_FOREGROUND};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 2px;
}}
QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {COLOR_SECONDARY};
}}
QMenu {{
    background-color: {COLOR_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {COLOR_SECONDARY};
}}
QMenu::separator {{
    height: 1px;
    background-color: {COLOR_BORDER};
    margin: 4px 8px;
}}

/* ===== 设置面板 ===== */
QFormLayout {{
    spacing: 16px;
    margin: 24px;
}}
QCheckBox {{
    color: {COLOR_FOREGROUND};
    spacing: 8px;
    padding: 6px 0;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    background-color: {COLOR_MUTED};
}}
QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
    image: none;
}}
QComboBox {{
    background-color: {COLOR_MUTED};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    color: {COLOR_FOREGROUND};
    min-width: 120px;
}}
QComboBox:hover {{
    border: 1px solid {COLOR_FOREGROUND};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLOR_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_SECONDARY};
    color: {COLOR_FOREGROUND};
}}
QSpinBox {{
    background-color: {COLOR_MUTED};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    color: {COLOR_FOREGROUND};
    min-width: 80px;
}}
QLabel#SettingsGroupTitle {{
    color: {COLOR_FOREGROUND};
    font-size: 14px;
    font-weight: 600;
    padding-bottom: 8px;
}}

/* ===== 状态栏 ===== */
QStatusBar {{
    background-color: {COLOR_PRIMARY};
    color: {COLOR_MUTED};
    border-top: 1px solid {COLOR_BORDER};
}}

/* ===== 滚动条 ===== */
QScrollBar:vertical {{
    background-color: {COLOR_BACKGROUND};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {COLOR_BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {COLOR_SECONDARY};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
    height: 0;
}}

/* ===== 技能 / 记忆 tab 列表 ===== */
QListWidget#SkillList, QListWidget#MemoryList {{
    background-color: {COLOR_BACKGROUND};
    border: none;
    padding: 12px;
}}
QListWidget#SkillList::item, QListWidget#MemoryList::item {{
    color: {COLOR_FOREGROUND};
    padding: 10px 14px;
    border-bottom: 1px solid {COLOR_BORDER};
}}
QListWidget#SkillList::item:hover, QListWidget#MemoryList::item:hover {{
    background-color: {COLOR_PRIMARY};
}}
QListWidget#SkillList::item:selected, QListWidget#MemoryList::item:selected {{
    background-color: {COLOR_SECONDARY};
    color: {COLOR_FOREGROUND};
}}

/* ===== 焦点环（keyboard nav 友好，UX 规范要求） ===== */
QAbstractButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QListWidget:focus {{
    outline: 2px solid {COLOR_RING};
}}
"""


def apply_theme(app: Any) -> None:
    """把 DARK_QSS 应用到 QApplication 实例。"""
    app.setStyleSheet(DARK_QSS)
