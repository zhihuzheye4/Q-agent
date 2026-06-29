"""工具历史独立窗口：从 sqlite tool_calls 表重建。

参照 hardware_monitor_window.py 模式：独立 QMainWindow，由 MenuBar 菜单项触发打开。
不修改 Sidebar 4 tab 结构（既有模块永不动原则）。

列：call_id / tool_name / status / started_at / duration_ms / 操作
v0.0.19 编排层未接通，tool_calls 表只写不读，本窗口可独立显示既有记录。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from q_agent.orchestrator.persistence import SessionStore


class ToolHistoryWindow(QMainWindow):
    """工具历史独立窗口。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("工具历史")
        self.setObjectName("ToolHistoryWindow")
        self.resize(720, 480)

        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)

        # 操作栏
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._reload)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch(1)
        v.addLayout(btn_row)

        # 表格
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["call_id", "工具", "状态", "开始时间", "耗时(ms)", "操作"]
        )
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 100)
        v.addWidget(self.table)

        self._store: SessionStore | None = None
        self._reload()

    def _reload(self) -> None:
        """从 sqlite 重建表格行。"""
        from q_agent.orchestrator.persistence import SessionStore

        db_path = Path.home() / ".q-agent" / "q-agent.db"
        if not db_path.exists():
            self.table.setRowCount(0)
            return

        if self._store is None:
            self._store = SessionStore(db_path)

        rows = self._store.load_all_tool_calls()
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(str(row["call_id"])))
            self.table.setItem(r, 1, QTableWidgetItem(str(row["tool_name"])))
            self.table.setItem(r, 2, QTableWidgetItem(str(row["status"])))
            self.table.setItem(r, 3, QTableWidgetItem(str(row["started_at"])))
            dur = row["duration_ms"] if row["duration_ms"] is not None else ""
            self.table.setItem(r, 4, QTableWidgetItem(str(dur)))
            view_btn = QPushButton("查看")
            self.table.setCellWidget(r, 5, view_btn)

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭时清理 store 连接。"""
        if self._store is not None:
            self._store.close()
            self._store = None
        super().closeEvent(event)
