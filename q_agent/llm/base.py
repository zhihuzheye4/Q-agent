"""LLM 抽象基类。本地优先，云端后端按需启用。"""

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """LLM 客户端接口。"""

    @abstractmethod
    def chat(self, messages: list[dict[str, Any]]) -> str:
        """多轮对话。"""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """单轮补全。"""
