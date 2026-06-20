"""顶部工具栏：左侧图标按钮（新建对话/清空/关于）+ 右侧模型下拉框与刷新。

行为：
    - 左侧 3 个 QToolButton（活 UI 空壳行为，仅状态栏回显）
    - 右侧"模型:"标签 + QComboBox（模型列表）+ 刷新 QToolButton
    - 启动时由 MainWindow 触发 refresh_models()，异步检测 Ollama
    - 下拉框分组：本地（Ollama）/ 云端（占位，未接 API）
    - 检测中：下拉显示"检测中..."
    - 检测成功有模型：填本地组 + 云端预置组
    - 检测成功无模型：本地组占位"未发现本地模型" + 云端组照常
    - 检测失败：下拉显示"未发现本地 LLM"占位项（不加云端组）
    - 用户选模型：emit model_selected(str)
    - 用户点刷新：再触发一次 refresh_models()

异步检测：
    - ModelRefreshWorker(QThread) 后台跑 list_models，避免阻塞 UI 主线程
    - 信号 models_found(list[str]) / refresh_failed(str) 回主线程更新 UI
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QToolBar,
    QWidget,
)

from q_agent.llm.ollama import OllamaError, list_models
from q_agent.ui.icons import load_icon

# 下拉框占位文案
PLACEHOLDER_DETECTING = "检测中..."
PLACEHOLDER_EMPTY = "未发现本地 LLM"
PLACEHOLDER_NO_LOCAL_MODEL = "未发现本地模型"

# 分组头文案
HEADER_LOCAL = "本地（Ollama）"
HEADER_CLOUD = "云端（占位，未接 API）"

# 云端预置模型（每家代表 1 个；后续真接 API 时改为动态拉取，ADR-020+）
CLOUD_PRESET: list[tuple[str, str]] = [
    ("gpt-4o (OpenAI)", "cloud"),
    ("claude-opus-4-7 (Anthropic)", "cloud"),
    ("gemini-2.5-pro (Google)", "cloud"),
]

# itemData 角色：标记 header（值"header"）/ group 名（"local"/"cloud"）
ITEM_ROLE = Qt.ItemDataRole.UserRole


class ModelRefreshWorker(QThread):
    """后台跑 list_models，避免网络请求阻塞 UI 主线程。"""

    models_found = Signal(list)
    refresh_failed = Signal(str)

    def __init__(self, host: str = "http://localhost:11434", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._host = host

    def run(self) -> None:
        try:
            models = list_models(self._host)
        except OllamaError as e:
            self.refresh_failed.emit(str(e))
            return
        self.models_found.emit(models)


class Toolbar(QToolBar):
    """顶部工具栏。"""

    model_selected = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__("main", parent)
        self._status_callback = status_callback or (lambda _: None)
        self._worker: ModelRefreshWorker | None = None
        self.setMovable(False)
        self._build_actions()
        self._build_model_group()

    def _build_actions(self) -> None:
        new_chat = self.addAction(load_icon("new-chat"), "新建对话")
        new_chat.setToolTip("新建对话（清空当前消息流，开始新对话）")
        new_chat.setStatusTip("新建对话")
        new_chat.triggered.connect(
            lambda: self._status_callback("已点击：新建对话（活 UI 空壳，无实际行为）")
        )

        clear = self.addAction(load_icon("clear"), "清空")
        clear.setToolTip("清空当前对话消息流")
        clear.setStatusTip("清空对话")
        clear.triggered.connect(
            lambda: self._status_callback("已点击：清空（活 UI 空壳，无实际行为）")
        )

        about = self.addAction(load_icon("about"), "关于")
        about.setToolTip("关于 Q-agent（版本信息与功能说明）")
        about.setStatusTip("关于 Q-agent")
        about.triggered.connect(
            lambda: self._status_callback("已点击：关于（活 UI 空壳，无实际行为）")
        )

    def _build_model_group(self) -> None:
        """右侧：[模型:][下拉框][刷新按钮]，靠右对齐。"""
        self.addSeparator()

        right_container = QWidget(self)
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(8, 0, 8, 0)
        right_layout.setSpacing(8)

        label = QLabel("模型:", right_container)
        right_layout.addWidget(label)

        # 用 QStandardItemModel 支持单 item disabled（分组头）
        self.model_combo = QComboBox(right_container)
        self.model_combo.setMinimumWidth(240)
        self._combo_model = QStandardItemModel(self.model_combo)
        self.model_combo.setModel(self._combo_model)
        self.model_combo.addItem(PLACEHOLDER_DETECTING)
        self.model_combo.setEnabled(False)
        self.model_combo.setToolTip("本地 Ollama 可用模型 + 云端预置（占位），点击刷新重新检测本地")
        self.model_combo.currentIndexChanged.connect(self._on_combo_changed)
        right_layout.addWidget(self.model_combo)

        self.refresh_btn = self.addAction(load_icon("refresh"), "刷新")
        self.refresh_btn.setToolTip("重新检测本地 Ollama 可用模型")
        self.refresh_btn.setStatusTip("刷新模型列表")
        self.refresh_btn.triggered.connect(self.refresh_models)

        self.addWidget(right_container)

    def refresh_models(self) -> None:
        """触发一次异步检测。重复触发时取消旧 worker。"""
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(1000)

        self._combo_model.clear()
        placeholder = QStandardItem(PLACEHOLDER_DETECTING)
        placeholder.setEnabled(False)
        self._combo_model.appendRow(placeholder)
        self.model_combo.setCurrentIndex(0)
        self.model_combo.setEnabled(False)
        self._status_callback("正在检测本地 Ollama 模型...")

        self._worker = ModelRefreshWorker(parent=self)
        self._worker.models_found.connect(self._on_models_found)
        self._worker.refresh_failed.connect(self._on_refresh_failed)
        self._worker.start()

    def _on_models_found(self, models: list[str]) -> None:
        """worker 成功返回。构造本地组 + 云端组。"""
        self._combo_model.clear()

        # 本地组头
        self._add_header(HEADER_LOCAL)
        if not models:
            self._add_placeholder(PLACEHOLDER_NO_LOCAL_MODEL)
        else:
            for name in models:
                self._add_selectable_item(name, group="local")

        # 云端组头
        self._add_header(HEADER_CLOUD)
        for name, group in CLOUD_PRESET:
            self._add_selectable_item(name, group=group)

        # 启用下拉（即使本地空，云端组也可选）
        self.model_combo.setEnabled(True)
        # 默认选中第一个可选项（本地首个模型 或 云端首个）
        first_selectable = self._first_selectable_index()
        if first_selectable >= 0:
            self.model_combo.setCurrentIndex(first_selectable)
        if models:
            msg = f"已发现 {len(models)} 个本地模型 + {len(CLOUD_PRESET)} 个云端预置"
        else:
            msg = f"本地 Ollama 无模型，已显示云端 {len(CLOUD_PRESET)} 个预置"
        self._status_callback(msg)

    def _on_refresh_failed(self, msg: str) -> None:
        """worker 失败：仅占位，不加云端组（让用户先解决本地连接问题）。"""
        self._combo_model.clear()
        item = QStandardItem(PLACEHOLDER_EMPTY)
        item.setEnabled(False)
        self._combo_model.appendRow(item)
        self.model_combo.setCurrentIndex(0)
        self.model_combo.setEnabled(False)
        self._status_callback(f"未发现本地 LLM，请启动 Ollama 服务后点击刷新（{msg}）")

    def _add_header(self, text: str) -> None:
        """加分组头（不可选 disabled item，灰色粗体）。"""
        item = QStandardItem(text)
        item.setEnabled(False)
        item.setData("header", ITEM_ROLE)
        item.setForeground(QBrush(QColor("#94A3B8")))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        self._combo_model.appendRow(item)

    def _add_placeholder(self, text: str) -> None:
        """加占位项（不可选，灰色）。"""
        item = QStandardItem(text)
        item.setEnabled(False)
        item.setData("placeholder", ITEM_ROLE)
        item.setForeground(QBrush(QColor("#64748B")))
        self._combo_model.appendRow(item)

    def _add_selectable_item(self, text: str, group: str = "") -> None:
        """加可选模型项。group 标记到 ITEM_ROLE。"""
        item = QStandardItem(text)
        item.setData(group, ITEM_ROLE)
        self._combo_model.appendRow(item)

    def _first_selectable_index(self) -> int:
        """返回第一个 enabled 项的索引。无则 -1。"""
        for i in range(self._combo_model.rowCount()):
            item = self._combo_model.item(i)
            if item is not None and item.isEnabled():
                return i
        return -1

    def _on_combo_changed(self, index: int) -> None:
        """用户切换模型选择。header / placeholder 项不 emit。"""
        if index < 0:
            return
        item = self._combo_model.item(index)
        if item is None or not item.isEnabled():
            return
        text = item.text()
        if text in (PLACEHOLDER_DETECTING, PLACEHOLDER_EMPTY, PLACEHOLDER_NO_LOCAL_MODEL):
            return
        self.model_selected.emit(text)

    def current_model(self) -> str | None:
        """当前选中模型名，未选中 / 占位 / header 时返回 None。"""
        idx = self.model_combo.currentIndex()
        if idx < 0:
            return None
        item = self._combo_model.item(idx)
        if item is None or not item.isEnabled():
            return None
        text = item.text()
        if text in (PLACEHOLDER_DETECTING, PLACEHOLDER_EMPTY, PLACEHOLDER_NO_LOCAL_MODEL, ""):
            return None
        return text
