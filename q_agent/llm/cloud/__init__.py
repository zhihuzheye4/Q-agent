"""云端 LLM 后端 stub 集合（OpenAI / Anthropic / Gemini）。

设计：
    - 三个 LLMClient 子类骨架，构造成功但 chat/complete 抛 NotImplementedError
    - 后期接真 API 时只填方法体，不动构造与接口
    - 依赖管理坚守 ADR-015：urllib 标准库零新运行时依赖
    - 不引入 openai/anthropic/google-generativeai 等 SDK
"""

from q_agent.llm.cloud.anthropic import AnthropicClient
from q_agent.llm.cloud.gemini import GeminiClient
from q_agent.llm.cloud.openai import OpenAIClient

__all__ = ["AnthropicClient", "GeminiClient", "OpenAIClient"]
