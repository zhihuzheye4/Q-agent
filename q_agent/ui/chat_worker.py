"""对话流式调用 worker（QThread）。

设计：
    - 后台跑 OllamaClient.chat_stream，避免阻塞 UI 主线程
    - 批量刷新策略（混合）：buffer 攒满 500 字 OR 距上次 flush 满 500ms，任一触发就 emit
      避免纯 token 流式"一秒一字让用户崩溃"的体验
    - 信号 chunk_received(str) / chat_failed(str) / chat_done() 回主线程更新气泡
    - stop() 接口留作未来取消按钮使用（v0.0.8 未接 UI）
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
        """跑流式 chat，buffer 攒到阈值或超时即 emit，结束 emit 剩余 + chat_done。"""
        try:
            client = OllamaClient(self._model, self._host)
            buffer = ""
            last_flush = time.monotonic()
            for text in client.chat_stream(self._messages):
                if self._stop:
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
        """请求停止（下次循环检查 _stop 后早退）。v0.0.8 未接 UI 取消按钮。"""
        self._stop = True
