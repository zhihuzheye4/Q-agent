"""工具调用审批弹窗 widget。

两套弹窗：
- ApprovalDialog：auto/once/always/deny 四档，含"本次会话相同参数不再追问"勾选
- SandboxRiskDialog：永不沙箱风险知情一次性弹窗，首次使用 destructive 工具前显示

模块化：独立 widget，由编排层 v0.0.20 接通时实例化调用，不在 v0.0.19 触发。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ApprovalDialog(QDialog):
    """工具调用审批弹窗：auto/once/always/deny 四档。

    destructive 级永不缓存，每次必弹；
    write 级同会话相同 args_hash 缓存一次；
    read_only 级不弹（编排层不实例化本 dialog）。
    """

    approved = Signal(str)  # "always" / "once" / "deny"

    def __init__(
        self,
        tool_name: str,
        permission_level: str,
        args_hash: str,
        args_preview: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("工具调用确认")
        self.setObjectName("ApprovalDialog")
        self._permission_level = permission_level

        v = QVBoxLayout(self)

        title = QLabel(f"工具 <b>{tool_name}</b> 请求执行")
        title.setObjectName("ApprovalDialogTitle")
        v.addWidget(title)

        perm_lbl = QLabel(f"权限级：<b>{permission_level}</b>")
        v.addWidget(perm_lbl)

        preview_lbl = QLabel(f"参数摘要：{args_preview}")
        preview_lbl.setWordWrap(True)
        v.addWidget(preview_lbl)

        hash_lbl = QLabel(f"指纹：{args_hash[:8]}")
        v.addWidget(hash_lbl)

        self.cb = QCheckBox("本次会话相同参数不再追问")
        if permission_level == "destructive":
            # destructive 永不缓存，勾选禁用
            self.cb.setEnabled(False)
            self.cb.setToolTip("destructive 级永不缓存，每次必弹")
        v.addWidget(self.cb)

        h = QHBoxLayout()
        btn_once = QPushButton("允许一次")
        btn_always = QPushButton("会话内允许")
        btn_deny = QPushButton("拒绝")
        h.addWidget(btn_once)
        h.addWidget(btn_always)
        h.addWidget(btn_deny)
        v.addLayout(h)

        btn_once.clicked.connect(lambda: self._emit("once"))
        btn_always.clicked.connect(lambda: self._emit("always"))
        btn_deny.clicked.connect(lambda: self._emit("deny"))

    def _emit(self, mode: str) -> None:
        if mode == "always" and not self.cb.isChecked():
            mode = "once"
        self.approved.emit(mode)
        self.accept()


class SandboxRiskDialog(QDialog):
    """永不沙箱风险知情一次性弹窗。

    首次使用 destructive 工具前显示，用户勾选"我已了解"后写入 settings，
    后续启动不再出现。
    """

    acknowledged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("永不沙箱风险知情")
        self.setObjectName("SandboxRiskDialog")
        self.setMinimumWidth(480)

        v = QVBoxLayout(self)

        warning = QLabel(
            "Q-agent 永不沙箱：工具调用直接在你的系统上执行，"
            "仅做危险命令黑名单 + 项目根目录保护 + 敏感文件拦截 + 内容嗅探。\n\n"
            "请勿让 LLM 执行来历不明的命令；destructive 级工具每次都会弹窗确认；"
            "write 级工具首次弹窗后会话内缓存。"
        )
        warning.setWordWrap(True)
        warning.setTextFormat(Qt.TextFormat.PlainText)
        v.addWidget(warning)

        self.cb = QCheckBox("我已了解永不沙箱的风险")
        v.addWidget(self.cb)

        btn = QPushButton("确认")
        btn.setEnabled(False)
        v.addWidget(btn)

        self.cb.toggled.connect(btn.setEnabled)
        btn.clicked.connect(self._on_ok)
        self._btn = btn

    def _on_ok(self) -> None:
        if self.cb.isChecked():
            self.acknowledged.emit()
            self.accept()
