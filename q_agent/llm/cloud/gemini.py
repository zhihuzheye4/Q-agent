"""Google Gemini 云端 LLM 后端 stub。

待实现：POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
依赖：urllib 标准库（不引入 google-generativeai SDK，坚守 ADR-015）
API key 管理：环境变量 GOOGLE_API_KEY 或设置页（待持久化需求）
"""

from __future__ import annotations

from typing import Any

from q_agent.llm.base import LLMClient


class GeminiClient(LLMClient):
    """Google Gemini 云端 LLM 客户端骨架。

    已实现：构造（model + api_key + 可选 base_url）
    待实现：chat() / complete() 调用 Gemini generateContent API
    """

    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        api_key: str = "",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def chat(self, messages: list[dict[str, Any]]) -> str:
        raise NotImplementedError(
            "Gemini chat 待实现，需用户在设置页填 API key 后启用（urllib 标准库调用）"
        )

    def complete(self, prompt: str) -> str:
        raise NotImplementedError("Gemini complete 待实现，需 API key 配置后填充方法体")
