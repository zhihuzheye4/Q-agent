"""侧边栏：4 tab 切换 + 底部硬件监控曲线（v0.0.12）。

结构（v0.0.12 改造）：
    +----------------+
    | QListWidget    |  ← 4 tab：对话/技能/记忆/设置
    | (tab 列表)     |
    +----------------+
    | HardwareMonitor|  ← 4 条折线（CPU/GPU/VRAM/RAM）60s 历史
    | (常驻)         |
    +----------------+

行为：
    - QListWidget 点击切换主内容区（QStackedWidget index），tab_changed 信号保留
    - HardwareMonitor 后台 1s 采集一次样本，自绘 4 条折线
    - 整个 sidebar 宽度固定 200px

v0.0.12 改动原因：用户要求"在左侧工具栏增加硬件占用曲线 CPU 和 GPU 实时显示"。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QListWidget, QListWidgetItem, QVBoxLayout

from q_agent.ui.hardware_monitor import HardwareMonitor
from q_agent.ui.icons import load_icon

# tab 元数据：(name, label, icon_name, tooltip)
TABS: list[tuple[str, str, str, str]] = [
    ("chat", "对话", "chat", "对话 tab：与 AI 交互的消息流"),
    ("skills", "技能", "skills", "技能 tab：已注册技能列表（当前为占位）"),
    ("memory", "记忆", "memory", "记忆 tab：运行期记忆条目（当前为占位）"),
    ("settings", "设置", "settings", "设置 tab：通用 / LLM 后端 / 工具调用层配置"),
]

# sidebar 固定宽度（含 tab 列表 + 硬件监控）
SIDEBAR_WIDTH = 200


class Sidebar(QFrame):
    """侧边栏容器：QListWidget tab 切换 + 底部 HardwareMonitor 硬件监控曲线。

    v0.0.12 起从 QListWidget 改为 QFrame 容器，保留 tab_changed 信号。
    HardwareMonitor 启动由 MainWindow 在 show 后调用 sidebar.hardware_monitor.start()。
    """

    tab_changed = Signal(int)  # 切换时发信号，参数为 tab 索引

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 上方：tab 列表
        self._list = QListWidget(self)
        self._list.setObjectName("SidebarList")
        self._list.setIconSize(QSize(20, 20))
        self._list.setCurrentRow(0)
        self._list.currentRowChanged.connect(self.tab_changed.emit)
        self._build_items()
        layout.addWidget(self._list, stretch=1)

        # 下方：硬件监控曲线（常驻）
        self.hardware_monitor = HardwareMonitor(self)
        layout.addWidget(self.hardware_monitor)

        self.setLayout(layout)

    def _build_items(self) -> None:
        for _name, label, icon_name, tooltip in TABS:
            icon: QIcon = load_icon(icon_name)
            item = QListWidgetItem(icon, label)
            item.setToolTip(tooltip)
            self._list.addItem(item)
