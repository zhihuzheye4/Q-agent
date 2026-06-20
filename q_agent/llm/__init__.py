"""LLM 层：多模型抽象，本地优先，云端后端按需启用。

模块结构（v0.0.6 起对称骨架，v0.0.7 起 list_models 返回 ModelEntry 区分本地/云端转发）：

    base.py                  LLMClient 抽象基类（chat + complete）
    local.py                 LocalLLMClient stub（llama.cpp 占位，未实现）
    ollama.py                OllamaClient(LLMClient) 子类骨架
                            + list_models() -> list[ModelEntry] 检测函数
                            + ModelEntry NamedTuple（name + is_remote + remote_host）
    cloud/
        openai.py            OpenAIClient(LLMClient) stub
        anthropic.py         AnthropicClient(LLMClient) stub
        gemini.py            GeminiClient(LLMClient) stub

后端分类：local（Ollama + llama.cpp 占位）+ cloud（OpenAI / Anthropic / Gemini）。
所有 client 构造成功，chat/complete 抛 NotImplementedError，待下一阶段填充方法体。
"""

from q_agent.llm.base import LLMClient  # noqa: F401
from q_agent.llm.cloud import (  # noqa: F401
    AnthropicClient,
    GeminiClient,
    OpenAIClient,
)
from q_agent.llm.local import LocalLLMClient  # noqa: F401
from q_agent.llm.ollama import (  # noqa: F401
    ModelEntry,
    OllamaClient,
    OllamaError,
    list_models,
)
