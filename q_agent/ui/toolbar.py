"""顶部工具栏：左侧图标按钮（新建对话/清空/关于）+ 右侧模型下拉框与刷新。

行为：
    - 左侧 3 个 QToolButton（活 UI 空壳行为，仅状态栏回显）
    - 右侧"模型:"标签 + QComboBox（模型列表）+ 刷新 QToolButton
    - 启动时由 MainWindow 触发 refresh_models()，异步检测 Ollama
    - 检测中：下拉显示"检测中..."
    - 检测成功有模型：下拉填模型名列表
    - 检测成功无模型 / 检测失败：下拉显示"未发现本地 LLM"，状态栏提示
    - 用户选模型：emit model_selected(str)
    - 用户点刷新：再触发一次 refresh_models()

异步检测：
    - ModelRefreshWorker(QThread) 后台跑 list_models，避免阻塞 UI 主线程
    - 信号 models_found(list[str]) / refresh_failed(str) 回主线程更新 UI
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
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

        self.model_combo = QComboBox(right_container)
        self.model_combo.setMinimumWidth(220)
        self.model_combo.addItem(PLACEHOLDER_DETECTING)
        self.model_combo.setEnabled(False)
        self.model_combo.setToolTip("本地 Ollama 可用模型列表，点击刷新重新检测")
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

        self.model_combo.clear()
        self.model_combo.addItem(PLACEHOLDER_DETECTING)
        self.model_combo.setEnabled(False)
        self._status_callback("正在检测本地 Ollama 模型...")

        self._worker = ModelRefreshWorker(parent=self)
        self._worker.models_found.connect(self._on_models_found)
        self._worker.refresh_failed.connect(self._on_refresh_failed)
        self._worker.start()

    def _on_models_found(self, models: list[str]) -> None:
        """worker 成功返回。"""
        self.model_combo.clear()
        if not models:
            self.model_combo.addItem(PLACEHOLDER_EMPTY)
            self.model_combo.setEnabled(False)
            self._status_callback("未发现本地 LLM（Ollama 在跑但无模型，请用 ollama pull 拉取）")
            return
        for name in models:
            self.model_combo.addItem(name)
        self.model_combo.setEnabled(True)
        self._status_callback(f"已发现 {len(models)} 个本地模型")

    def _on_refresh_failed(self, msg: str) -> None:
        """worker 失败。"""
        self.model_combo.clear()
        self.model_combo.addItem(PLACEHOLDER_EMPTY)
        self.model_combo.setEnabled(False)
        self._status_callback(f"未发现本地 LLM，请启动 Ollama 服务后点击刷新（{msg}）")

    def _on_combo_changed(self, index: int) -> None:
        """用户切换模型选择。占位项不 emit。"""
        if index < 0:
            return
        text = self.model_combo.currentText()
        if text in (PLACEHOLDER_DETECTING, PLACEHOLDER_EMPTY):
            return
        self.model_selected.emit(text)

    def current_model(self) -> str | None:
        """当前选中模型名，未选中或占位时返回 None。"""
        text = self.model_combo.currentText()
        if text in (PLACEHOLDER_DETECTING, PLACEHOLDER_EMPTY, ""):
            return None
        return text
