"""顶部工具栏：图标按钮（新建对话 / 清空 / 关于）。

行为（活 UI 空壳）：
    - 3 个 QToolButton 图标按钮
    - 按下只显示状态消息到主窗口状态栏（无实际行为）
    - 通过 setStatusBar_callback 注入主窗口的状态栏写方法
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from PySide6.QtWidgets import QToolBar

from q_agent.ui.icons import load_icon


class Toolbar(QToolBar):
    """顶部工具栏。"""

    def __init__(
        self,
        parent: QWidget | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__("main", parent)
        self._status_callback = status_callback or (lambda _: None)
        self.setMovable(False)
        self._build_actions()

    def _build_actions(self) -> None:
        new_chat = self.addAction(load_icon("new-chat"), "新建对话")
        new_chat.triggered.connect(
            lambda: self._status_callback("已点击：新建对话（活 UI 空壳，无实际行为）")
        )

        clear = self.addAction(load_icon("clear"), "清空")
        clear.triggered.connect(
            lambda: self._status_callback("已点击：清空（活 UI 空壳，无实际行为）")
        )

        about = self.addAction(load_icon("about"), "关于")
        about.triggered.connect(
            lambda: self._status_callback("已点击：关于（活 UI 空壳，无实际行为）")
        )
