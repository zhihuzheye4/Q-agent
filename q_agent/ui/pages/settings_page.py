"""设置 tab：开关 + 下拉 + 数值。

行为（活 UI 空壳）：
    - 各种控件状态可切换，但不影响任何功能
    - 不写设置到任何文件（不持久化）
    - 用户提"设置持久化"需求时再实现
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    """设置 tab 主页。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(24)

        # === 通用设置组 ===
        general_title = QLabel("通用", self)
        general_title.setObjectName("SettingsGroupTitle")
        outer.addWidget(general_title)

        general_form = QFormLayout()
        general_form.setSpacing(12)

        self.dark_mode_check = QCheckBox("暗色模式（默认开）", self)
        self.dark_mode_check.setChecked(True)
        general_form.addRow("主题", self.dark_mode_check)

        self.lang_combo = QComboBox(self)
        self.lang_combo.addItems(["简体中文", "English"])
        general_form.addRow("界面语言", self.lang_combo)

        self.font_size_spin = QSpinBox(self)
        self.font_size_spin.setRange(12, 24)
        self.font_size_spin.setValue(14)
        general_form.addRow("字号", self.font_size_spin)
        outer.addLayout(general_form)

        # === LLM 设置组（占位） ===
        llm_title = QLabel("LLM 后端", self)
        llm_title.setObjectName("SettingsGroupTitle")
        outer.addWidget(llm_title)

        llm_form = QFormLayout()
        llm_form.setSpacing(12)

        self.llm_backend_combo = QComboBox(self)
        self.llm_backend_combo.addItems(
            ["本地（Ollama）", "本地（llama.cpp）", "云端（OpenAI）", "云端（Claude）"]
        )
        general_form.addRow("后端", self.llm_backend_combo)

        self.llm_endpoint = QLineEdit(self)
        self.llm_endpoint.setText("http://localhost:11434")
        self.llm_endpoint.setPlaceholderText("LLM 服务端点")
        llm_form.addRow("端点", self.llm_endpoint)

        self.local_first_check = QCheckBox("本地优先（默认开）", self)
        self.local_first_check.setChecked(True)
        llm_form.addRow("默认走本地", self.local_first_check)

        outer.addLayout(llm_form)

        # === 工具调用层设置组（占位） ===
        tools_title = QLabel("工具调用层", self)
        tools_title.setObjectName("SettingsGroupTitle")
        outer.addWidget(tools_title)

        tools_form = QFormLayout()
        tools_form.setSpacing(12)

        self.safety_check = QCheckBox("危险命令黑名单（默认开）", self)
        self.safety_check.setChecked(True)
        tools_form.addRow("基本安全", self.safety_check)

        self.root_protect_check = QCheckBox("项目根目录保护（默认开）", self)
        self.root_protect_check.setChecked(True)
        tools_form.addRow("根目录保护", self.root_protect_check)

        outer.addLayout(tools_form)

        # 占位提示
        hint = QLabel("提示：设置 tab 为占位骨架，状态切换不持久化，重启 UI 状态重置。", self)
        hint.setStyleSheet("color: #272F42; font-size: 12px;")
        outer.addWidget(hint)
        outer.addStretch()
