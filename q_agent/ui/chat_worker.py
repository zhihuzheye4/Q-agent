"""对话流式调用 worker（QThread）。

设计：
    - 后台跑 OllamaClient.chat_stream，避免阻塞 UI 主线程
    - 批量刷新策略（混合）：buffer 攒满 500 字 OR 距上次 flush 满 500ms，任一触发就 emit
      避免纯 token 流式"一秒一字让用户崩溃"的体验
    - 信号 chunk_received(str) / chat_failed(str) / chat_done() / chat_aborted() 回主线程更新气泡
    - stop() 接口 v0.0.17 接通 UI 取消按钮：触发后 run 循环检测 _stop 早退 + emit chat_aborted
"""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from q_agent.llm.ollama import OllamaClient, OllamaError


class ChatWorker(QThread):
    """后台跑 OllamaClient.chat_stream，批量 flush chunk 到主线程。"""

    chunk_received = Signal(str)
    chat_failed = Signal(str)
    chat_done = Signal()
    chat_aborted = Signal()  # v0.0.17 新增：用户取消生成（stop 触发后 emit）

    # 批量刷新阈值：buffer 攒满 CHUNK_SIZE 字 OR 距上次 flush 满 FLUSH_MS 毫秒，任一触发
    CHUNK_SIZE = 500
    FLUSH_MS = 500.0

    def __init__(
        self,
        model: str,
        host: str,
        messages: list[dict[str, Any]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._host = host
        self._messages = messages
        self._stop = False

    def run(self) -> None:
        """跑流式 chat，buffer 攒到阈值或超时即 emit，结束 emit 剩余 + chat_done。

        v0.0.17：检测到 _stop 时 flush 已收到的剩余 buffer + emit chat_aborted（不是 chat_done），
        让 chat_page 区分"正常完成"和"用户取消"两种结束路径。
        """
        try:
            client = OllamaClient(self._model, self._host)
            buffer = ""
            last_flush = time.monotonic()
            for text in client.chat_stream(self._messages):
                if self._stop:
                    if buffer:
                        self.chunk_received.emit(buffer)
                    self.chat_aborted.emit()
                    return
                buffer += text
                now = time.monotonic()
                elapsed_ms = (now - last_flush) * 1000.0
                if len(buffer) >= self.CHUNK_SIZE or elapsed_ms >= self.FLUSH_MS:
                    self.chunk_received.emit(buffer)
                    buffer = ""
                    last_flush = now
            if buffer:
                self.chunk_received.emit(buffer)
            self.chat_done.emit()
        except OllamaError as e:
            self.chat_failed.emit(str(e))
        except Exception as e:
            self.chat_failed.emit(f"未知错误：{e}")

    def stop(self) -> None:
        """请求停止（v0.0.17 接通 UI 取消按钮）。

        主线程调 stop() 设 _stop flag，run 循环下次迭代检查到 _stop 后
        flush 剩余 buffer + emit chat_aborted 早退。
        """
        self._stop = True
