"""技能 tab：已注册技能 + 已开发工具展示。

行为（v0.0.19 起填充真实数据）：
    - 上半：已注册技能表格（从 q_agent.skills.registry.all_skills() 读）
    - 下半：已开发工具表格（从 q_agent.tools.registry.all_tools() 读）
    - 4 列技能：name / desc / signature / 状态
    - 5 列工具：name / permission_level / needs_confirmation / version / desc
    - 进入 tab 时刷新一次（注册表是静态的，无需实时更新）
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# 触发 @skill/@tool 注册（导入即注册到全局 registry）
import q_agent.skills.builtin  # noqa: F401
import q_agent.tools  # noqa: F401
from q_agent.skills.registry import all_skills
from q_agent.tools.registry import all_tools


class SkillsPage(QWidget):
    """技能 tab 主页：展示已注册技能 + 已开发工具。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # ---- 上半：已注册技能 ----
        skills_title = QLabel("已注册技能", self)
        skills_title.setObjectName("SettingsGroupTitle")
        layout.addWidget(skills_title)

        self.skills_table = QTableWidget(0, 4, self)
        self.skills_table.setObjectName("SkillList")
        self.skills_table.setHorizontalHeaderLabels(["名称", "描述", "签名", "状态"])
        self.skills_table.setColumnWidth(0, 140)
        self.skills_table.setColumnWidth(1, 200)
        self.skills_table.setColumnWidth(2, 280)
        self.skills_table.setColumnWidth(3, 80)
        self.skills_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.skills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.skills_table)

        # ---- 下半：已开发工具 ----
        tools_title = QLabel("已开发工具", self)
        tools_title.setObjectName("SettingsGroupTitle")
        layout.addWidget(tools_title)

        self.tools_table = QTableWidget(0, 5, self)
        self.tools_table.setObjectName("ToolList")
        self.tools_table.setHorizontalHeaderLabels(["名称", "权限级", "需确认", "版本", "描述"])
        self.tools_table.setColumnWidth(0, 140)
        self.tools_table.setColumnWidth(1, 100)
        self.tools_table.setColumnWidth(2, 80)
        self.tools_table.setColumnWidth(3, 80)
        self.tools_table.setColumnWidth(4, 360)
        self.tools_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tools_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.tools_table)

        # ---- 底部：提示 ----
        hint_row = QHBoxLayout()
        hint = QLabel(
            "提示：技能/工具来自 @skill/@tool 装饰器注册的函数。"
            "v0.0.20 编排层接通后，LLM 可通过工具调用层执行这些工具。",
            self,
        )
        hint.setStyleSheet("color: #272F42; font-size: 12px;")
        hint.setWordWrap(True)
        hint_row.addWidget(hint)
        hint_row.addStretch(1)
        layout.addLayout(hint_row)

    def _refresh(self) -> None:
        """从注册表刷新两张表。"""
        # 技能表
        skills = all_skills()
        self.skills_table.setRowCount(len(skills))
        for r, s in enumerate(skills):
            self.skills_table.setItem(r, 0, QTableWidgetItem(s.name))
            self.skills_table.setItem(r, 1, QTableWidgetItem(s.desc))
            self.skills_table.setItem(r, 2, QTableWidgetItem(s.signature))
            self.skills_table.setItem(r, 3, QTableWidgetItem("已实现"))

        # 工具表
        tools = all_tools()
        self.tools_table.setRowCount(len(tools))
        perm_lbl = {"read_only": "只读", "write": "写入", "destructive": "破坏性"}
        for r, t in enumerate(tools):
            self.tools_table.setItem(r, 0, QTableWidgetItem(t.name))
            self.tools_table.setItem(
                r, 1, QTableWidgetItem(perm_lbl.get(t.permission_level, t.permission_level))
            )
            self.tools_table.setItem(r, 2, QTableWidgetItem("是" if t.needs_confirmation else "否"))
            self.tools_table.setItem(r, 3, QTableWidgetItem(t.version))
            self.tools_table.setItem(r, 4, QTableWidgetItem(t.desc))
