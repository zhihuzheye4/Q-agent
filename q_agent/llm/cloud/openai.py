"""OpenAI 云端 LLM 后端 stub。

待实现：POST https://api.openai.com/v1/chat/completions
依赖：urllib 标准库（不引入 openai SDK，坚守 ADR-015）
API key 管理：用户在设置页填，存 QSettings 或环境变量 OPENAI_API_KEY（待持久化需求）
"""

from __future__ import annotations

from typing import Any

from q_agent.llm.base import LLMClient


class OpenAIClient(LLMClient):
    """OpenAI 云端 LLM 客户端骨架。

    已实现：构造（model + api_key + 可选 base_url）
    待实现：chat() / complete() 调用 OpenAI Chat Completions API
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def chat(self, messages: list[dict[str, Any]]) -> str:
        raise NotImplementedError(
            "OpenAI chat 待实现，需用户在设置页填 API key 后启用（urllib 标准库调用）"
        )

    def complete(self, prompt: str) -> str:
        raise NotImplementedError("OpenAI complete 待实现，需 API key 配置后填充方法体")
