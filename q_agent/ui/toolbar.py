"""顶部工具栏：左侧图标按钮（新建对话/清空/关于）+ 右侧模型下拉框与刷新与释放。

行为：
    - 左侧 3 个 QToolButton（活 UI 空壳行为，仅状态栏回显）
    - 右侧"模型:"标签 + QComboBox（模型列表）+ 刷新 QToolButton + 释放 QToolButton
    - 启动时由 MainWindow 触发 refresh_models()，异步检测 Ollama
    - 下拉框分组（v0.0.7 起三组）：
        本地（Ollama）       — Ollama 上真正装在本地的模型（is_remote=False）
        Ollama Cloud（转发）  — Ollama Cloud 转发的云端模型（is_remote=True）
        云端（占位，未接 API） — CLOUD_PRESET 三家预置，未接 API
    - 检测中：下拉显示"检测中..."
    - 检测成功：填本地组 +（如有）Ollama Cloud 组 + 云端预置组
    - 检测成功本地空但 cloud 转发有：本地组占位"未发现本地模型"
    - 检测失败：下拉显示"未发现本地 LLM"占位项（不加任何后续组）
    - 用户选模型：emit model_selected(str) + model_group_changed(group)
    - 用户点刷新：再触发一次 refresh_models()
    - 用户点释放：调 release_model POST /api/generate keep_alive=0 卸载模型出 RAM，
      仅在选中 local/ollama-cloud 模型时启用，cloud 预置未接 API 不需要释放

异步检测：
    - ModelRefreshWorker(QThread) 后台跑 list_models，避免阻塞 UI 主线程
    - ModelReleaseWorker(QThread) 后台跑 release_model，避免阻塞 UI 主线程
    - 信号 models_found(list[ModelEntry]) / refresh_failed(str) 回主线程更新 UI
    - 信号 released(str) / release_failed(str) 回主线程更新状态栏
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

from q_agent.llm.ollama import ModelEntry, OllamaError, list_models, release_model
from q_agent.ui.icons import load_icon

# 下拉框占位文案
PLACEHOLDER_DETECTING = "检测中..."
PLACEHOLDER_EMPTY = "未发现本地 LLM"
PLACEHOLDER_NO_LOCAL_MODEL = "未发现本地模型"

# 分组头文案
HEADER_LOCAL = "本地（Ollama）"
HEADER_OLLAMA_CLOUD = "Ollama Cloud（转发）"
HEADER_CLOUD = "云端（占位，未接 API）"

# 云端预置模型（每家代表 1 个；后续真接 API 时改为动态拉取，ADR-020+）
CLOUD_PRESET: list[tuple[str, str]] = [
    ("gpt-4o (OpenAI)", "cloud"),
    ("claude-opus-4-7 (Anthropic)", "cloud"),
    ("gemini-2.5-pro (Google)", "cloud"),
]

# itemData 角色：标记 header（值"header"）/ group 名（"local"/"ollama-cloud"/"cloud"）
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


class ModelReleaseWorker(QThread):
    """后台跑 release_model，避免网络请求阻塞 UI 主线程。

    完成后 emit released(model_name)；失败 emit release_failed(str)。
    """

    released = Signal(str)
    release_failed = Signal(str)

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._host = host

    def run(self) -> None:
        try:
            release_model(self._model, self._host)
        except OllamaError as e:
            self.release_failed.emit(str(e))
            return
        self.released.emit(self._model)


class Toolbar(QToolBar):
    """顶部工具栏。"""

    model_selected = Signal(str)
    model_group_changed = Signal(object)  # str | None，"local"/"ollama-cloud"/"cloud"/None
    model_released = Signal(str)  # 释放成功的模型名（v0.0.9 新增，chat_page 可监听清空 pending）
    # v0.0.16 新增：新建对话 / 清空 按钮的请求信号（MainWindow 连接到 chat_page._clear_messages）
    new_chat_requested = Signal()
    clear_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__("main", parent)
        self._status_callback = status_callback or (lambda _: None)
        self._worker: ModelRefreshWorker | None = None
        self._release_worker: ModelReleaseWorker | None = None
        # 抑制首次自动选择触发的 model_selected 信号（避免 _on_models_found 自动选首个模型时
        # chat_page 误清空初始问候消息；仅 group_changed 仍要 emit 以同步发送按钮状态）
        self._suppress_select_emit = False
        self.setMovable(False)
        self._build_actions()
        self._build_model_group()

    def _build_actions(self) -> None:
        new_chat = self.addAction(load_icon("new-chat"), "新建对话")
        new_chat.setToolTip("新建对话（清空当前消息流，开始新对话）")
        new_chat.setStatusTip("新建对话")
        # v0.0.16：从 status_callback 占位改为 emit new_chat_requested 信号
        new_chat.triggered.connect(self.new_chat_requested.emit)

        clear = self.addAction(load_icon("clear"), "清空")
        clear.setToolTip("清空当前对话消息流")
        clear.setStatusTip("清空对话")
        # v0.0.16：从 status_callback 占位改为 emit clear_requested 信号
        clear.triggered.connect(self.clear_requested.emit)

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

        # 释放按钮：仅 local/ollama-cloud 启用，调 /api/generate keep_alive=0 卸载模型出 RAM
        self.release_btn = self.addAction(load_icon("release"), "释放")
        self.release_btn.setToolTip("释放当前模型内存（卸载出 Ollama RAM，下次需要时重新加载）")
        self.release_btn.setStatusTip("释放当前模型内存")
        self.release_btn.setEnabled(False)  # 启动时无选中模型，禁用
        self.release_btn.triggered.connect(self._on_release_clicked)

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

    def _on_models_found(self, models: list[ModelEntry]) -> None:
        """worker 成功返回。构造本地组 + Ollama Cloud 组（如有）+ 云端预置组。"""
        self._combo_model.clear()

        # 拆分真正本地 vs Ollama Cloud 转发
        local_entries = [m for m in models if not m.is_remote]
        cloud_entries = [m for m in models if m.is_remote]

        # 本地组头
        self._add_header(HEADER_LOCAL)
        if not local_entries:
            self._add_placeholder(PLACEHOLDER_NO_LOCAL_MODEL)
        else:
            for entry in local_entries:
                self._add_selectable_item(entry.name, group="local")

        # Ollama Cloud 转发组（仅有 cloud 转发模型时才显示）
        if cloud_entries:
            self._add_header(HEADER_OLLAMA_CLOUD)
            for entry in cloud_entries:
                self._add_selectable_item(entry.name, group="ollama-cloud")

        # 云端 API 预置组头（CLOUD_PRESET 占位）
        self._add_header(HEADER_CLOUD)
        for name, group in CLOUD_PRESET:
            self._add_selectable_item(name, group=group)

        # 启用下拉（即使本地空，后续组也可选）
        self.model_combo.setEnabled(True)
        # 默认选中第一个可选项（本地首个 或 Ollama Cloud 首个 或 云端预置首个）
        # 抑制首次自动选择触发的 model_selected（避免 chat_page 清空初始问候）
        first_selectable = self._first_selectable_index()
        if first_selectable >= 0:
            self._suppress_select_emit = True
            self.model_combo.setCurrentIndex(first_selectable)
            self._suppress_select_emit = False  # 防御：若未触发 currentIndexChanged 则手动复位

        # 状态栏汇总
        parts: list[str] = [f"{len(local_entries)} 个本地模型"]
        if cloud_entries:
            parts.append(f"{len(cloud_entries)} 个 Ollama Cloud 转发")
        parts.append(f"{len(CLOUD_PRESET)} 个云端预置")
        msg = "已发现 " + " + ".join(parts)
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
        # 取分组 + 同步 release_btn 状态（每次都做，无论是否抑制）
        group = item.data(ITEM_ROLE)
        self.model_group_changed.emit(group)
        self.release_btn.setEnabled(group in ("local", "ollama-cloud"))
        # 抑制首次自动选择触发的 model_selected（避免 chat_page 清空初始问候）
        if self._suppress_select_emit:
            self._suppress_select_emit = False
            return
        self.model_selected.emit(text)

    def _on_release_clicked(self) -> None:
        """用户点释放按钮 → 弹确认 → 启动 ModelReleaseWorker 后台卸载。"""
        from PySide6.QtWidgets import QMessageBox

        model = self.current_model()
        if not model:
            return
        # 防御性：cloud 分组未接 API 无内存可释放
        if self.current_model_group() not in ("local", "ollama-cloud"):
            return
        # 弹确认对话框
        reply = QMessageBox.question(
            self,
            "释放模型内存",
            f"将卸载模型 {model} 出 Ollama 内存（RAM），"
            "下次需要时在下拉框重新选择即可加载。\n\n确认释放？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        # 重复触发时取消旧 worker
        if self._release_worker is not None and self._release_worker.isRunning():
            self._release_worker.quit()
            self._release_worker.wait(1000)
        self.release_btn.setEnabled(False)
        self._status_callback(f"正在释放 {model} 内存...")
        self._release_worker = ModelReleaseWorker(model, parent=self)
        self._release_worker.released.connect(self._on_released)
        self._release_worker.release_failed.connect(self._on_release_failed)
        self._release_worker.start()

    def _on_released(self, model: str) -> None:
        """释放成功 → 状态栏提示 + emit model_released（chat_page 可监听清 pending）。

        v0.0.11 起 release_model 内部用 /api/ps 验证模型确实卸载，状态栏文案明确说明
        "Ollama API 验证通过"，避免用户看到"已释放"但任务管理器 GPU 占用未变的疑惑
        （Ollama 进程级 CUDA context 不立即归还 OS 是已知行为，不影响实际卸载）。
        """
        self._status_callback(
            f"已卸载 {model} 出 Ollama（API 验证通过，VRAM 已归还；"
            "任务管理器进程级 GPU 内存可能延迟显示）"
        )
        self.model_released.emit(model)
        # 释放后下拉框不再选中此模型（用户需重新选择）；保留 combo 选中态以维持 group 信号
        # 但发送按钮需要重新评估——当前 group 仍是 local/ollama-cloud，输入框非空仍可发送
        # 实际下次发送会重新触发 Ollama 加载模型，所以无需禁用发送
        group = self.current_model_group()
        self.release_btn.setEnabled(group in ("local", "ollama-cloud"))

    def _on_release_failed(self, msg: str) -> None:
        """释放失败 → 状态栏错误提示。

        v0.0.11 起 release_model 卸载未生效（/api/ps 仍含该模型）也走此分支，
        文案区分"连接失败"与"卸载未生效"两种语义。
        """
        self._status_callback(f"释放失败：{msg}")
        group = self.current_model_group()
        self.release_btn.setEnabled(group in ("local", "ollama-cloud"))

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

    def current_model_group(self) -> str | None:
        """当前选中模型的分组名（"local"/"ollama-cloud"/"cloud"）。

        未选中 / 占位 / header 时返回 None。供 chat_page 判断是否允许发送。
        """
        idx = self.model_combo.currentIndex()
        if idx < 0:
            return None
        item = self._combo_model.item(idx)
        if item is None or not item.isEnabled():
            return None
        text = item.text()
        if text in (PLACEHOLDER_DETECTING, PLACEHOLDER_EMPTY, PLACEHOLDER_NO_LOCAL_MODEL, ""):
            return None
        group = item.data(ITEM_ROLE)
        return group if isinstance(group, str) else None
