"""异步真摘要 worker（v0.0.18 骨架）。

独立小摘要模型（如 Qwen2.5-3B）+ QThread 后台执行。
主对话不阻塞——用户继续对话，摘要完成后异步合流到上下文。

设计要点：
- SummaryWorker(QThread)：set_chunks 注入待摘要块，run() 后台执行
- summary_completed / summary_failed 信号回主线程
- _summarize_block / _merge_summaries 为占位骨架，v0.0.19 实化真调 Ollama
- 标识符保留指令在 context.py 的 SUMMARY_SYSTEM_PROMPT 中定义
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal


class SummaryWorker(QThread):
    """异步真摘要 worker。

    用法：
        worker = SummaryWorker(summary_model="qwen2.5:3b", host="http://localhost:11434")
        worker.set_chunks([...])
        worker.summary_completed.connect(on_done)
        worker.summary_failed.connect(on_failed)
        worker.start()  # 后台执行，不阻塞主循环

    v0.0.18 骨架：_summarize_block / _merge_summaries 为占位，返回拼接字符串。
    v0.0.19 实化：真调 Ollama /api/chat 流式生成摘要。
    """

    summary_completed = Signal(str)  # summary_text
    summary_failed = Signal(str)  # error_msg

    def __init__(
        self,
        summary_model: str = "qwen2.5:3b",
        host: str = "http://localhost:11434",
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.summary_model = summary_model
        self.host = host
        self._chunks: list[str] = []
        self._stop = False

    def set_chunks(self, chunks: list[str]) -> None:
        """设置待摘要的消息块（每块 ~2000 token）。"""
        self._chunks = list(chunks)

    def stop(self) -> None:
        """请求停止（让线程自然早退，不强制中断）。"""
        self._stop = True

    def run(self) -> None:
        """QThread 入口：分块摘要 + 多块合并。"""
        try:
            block_summaries: list[str] = []
            for chunk in self._chunks:
                if self._stop:
                    return
                summary = self._summarize_block(chunk)
                block_summaries.append(summary)

            if self._stop:
                return

            if not block_summaries:
                self.summary_completed.emit("")
                return

            if len(block_summaries) == 1:
                final_summary = block_summaries[0]
            else:
                final_summary = self._merge_summaries(block_summaries)

            if self._stop:
                return
            self.summary_completed.emit(final_summary)
        except Exception as e:  # noqa: BLE001 - worker 顶层兜底
            self.summary_failed.emit(f"{type(e).__name__}: {e}")

    def _summarize_block(self, chunk: str) -> str:
        """单块摘要。

        v0.0.18 骨架：返回 chunk 的前 200 字符 + "[骨架占位摘要]"标记。
        v0.0.19 实化：调 Ollama /api/chat，system 用 SUMMARY_SYSTEM_PROMPT。
        """
        if self._stop:
            return ""
        # 骨架实现：截断 + 标记。真摘要模型待 v0.0.19 接 Ollama。
        return f"[骨架占位摘要 v0.0.18]\n{chunk[:200]}"

    def _merge_summaries(self, block_summaries: list[str]) -> str:
        """多块摘要合并。

        v0.0.18 骨架：用换行分隔拼接，加 "[合并摘要]" 标记。
        v0.0.19 实化：再次调摘要模型做合并摘要。
        """
        if self._stop:
            return ""
        joined = "\n\n---\n\n".join(block_summaries)
        return f"[骨架合并摘要 v0.0.18]\n{joined}"
