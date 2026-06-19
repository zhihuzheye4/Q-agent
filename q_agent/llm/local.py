"""本地 LLM 后端 stub。后续接 llama.cpp / ollama / LM Studio。"""

from typing import Any

from q_agent.llm.base import LLMClient


class LocalLLMClient(LLMClient):
    """本地 LLM 后端占位，待具体需求驱动后实现。"""

    def __init__(self, model_path: str = "") -> None:
        self.model_path = model_path
        raise NotImplementedError("本地 LLM 后端待实现，下一步由用户提出后讨论")

    def chat(self, messages: list[dict[str, Any]]) -> str:
        raise NotImplementedError

    def complete(self, prompt: str) -> str:
        raise NotImplementedError
