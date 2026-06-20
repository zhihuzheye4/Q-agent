"""LLM Client 体系单测：覆盖 base / local / ollama / cloud/{openai,anthropic,gemini}。

验证目标：
    - 所有 LLMClient 子类都能被构造（不立即抛 NotImplementedError）
    - 所有子类的 chat() / complete() 抛 NotImplementedError（待下一阶段填充）
    - 构造参数正确存到实例属性
    - list_models()（独立检测函数）与 OllamaClient 客户端共存，互不干扰
"""

from __future__ import annotations

import pytest

from q_agent.llm.base import LLMClient
from q_agent.llm.cloud.anthropic import AnthropicClient
from q_agent.llm.cloud.gemini import GeminiClient
from q_agent.llm.cloud.openai import OpenAIClient
from q_agent.llm.local import LocalLLMClient
from q_agent.llm.ollama import OllamaClient


def test_llmclient_is_abstract() -> None:
    """LLMClient 是 ABC，不能直接实例化。"""
    with pytest.raises(TypeError):
        LLMClient()  # type: ignore[abstract]


def test_ollama_client_constructs_and_stores_args() -> None:
    """OllamaClient 构造成功 + model/host 存到属性。"""
    c = OllamaClient(model="qwen2.5:7b")
    assert c.model == "qwen2.5:7b"
    assert c.host == "http://localhost:11434"

    c2 = OllamaClient(model="llama3:8b", host="http://my-host:11434")
    assert c2.model == "llama3:8b"
    assert c2.host == "http://my-host:11434"


def test_ollama_client_chat_raises_not_implemented() -> None:
    """OllamaClient.chat 待实现，抛 NotImplementedError。"""
    c = OllamaClient(model="qwen2.5:7b")
    with pytest.raises(NotImplementedError):
        c.chat([{"role": "user", "content": "hi"}])


def test_ollama_client_complete_raises_not_implemented() -> None:
    """OllamaClient.complete 待实现，抛 NotImplementedError。"""
    c = OllamaClient(model="qwen2.5:7b")
    with pytest.raises(NotImplementedError):
        c.complete("hi")


def test_openai_client_constructs() -> None:
    """OpenAIClient 默认参数 + 自定义参数都构造成功。"""
    c = OpenAIClient()
    assert c.model == "gpt-4o"
    assert c.api_key == ""
    assert c.base_url == "https://api.openai.com/v1"

    c2 = OpenAIClient(model="gpt-4o-mini", api_key="sk-xxx", base_url="http://proxy/v1")
    assert c2.model == "gpt-4o-mini"
    assert c2.api_key == "sk-xxx"
    assert c2.base_url == "http://proxy/v1"


def test_openai_client_chat_raises_not_implemented() -> None:
    """OpenAIClient.chat 待实现。"""
    with pytest.raises(NotImplementedError):
        OpenAIClient().chat([{"role": "user", "content": "hi"}])


def test_openai_client_complete_raises_not_implemented() -> None:
    """OpenAIClient.complete 待实现。"""
    with pytest.raises(NotImplementedError):
        OpenAIClient().complete("hi")


def test_anthropic_client_constructs() -> None:
    """AnthropicClient 构造 + 参数存属性。"""
    c = AnthropicClient()
    assert c.model == "claude-opus-4-7"
    assert c.api_key == ""
    assert c.base_url == "https://api.anthropic.com/v1"

    c2 = AnthropicClient(model="claude-sonnet-4-6", api_key="sk-ant-xxx")
    assert c2.model == "claude-sonnet-4-6"
    assert c2.api_key == "sk-ant-xxx"


def test_anthropic_client_chat_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        AnthropicClient().chat([{"role": "user", "content": "hi"}])


def test_anthropic_client_complete_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        AnthropicClient().complete("hi")


def test_gemini_client_constructs() -> None:
    """GeminiClient 构造 + 参数存属性。"""
    c = GeminiClient()
    assert c.model == "gemini-2.5-pro"
    assert c.api_key == ""
    assert c.base_url.startswith("https://generativelanguage.googleapis.com")

    c2 = GeminiClient(model="gemini-2.5-flash", api_key="AIza-xxx")
    assert c2.model == "gemini-2.5-flash"
    assert c2.api_key == "AIza-xxx"


def test_gemini_client_chat_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        GeminiClient().chat([{"role": "user", "content": "hi"}])


def test_gemini_client_complete_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        GeminiClient().complete("hi")


def test_all_clients_are_llmclient_subclasses() -> None:
    """所有 client 都是 LLMClient 子类，编排层可统一调度。"""
    assert issubclass(OllamaClient, LLMClient)
    assert issubclass(LocalLLMClient, LLMClient)
    assert issubclass(OpenAIClient, LLMClient)
    assert issubclass(AnthropicClient, LLMClient)
    assert issubclass(GeminiClient, LLMClient)


def test_llm_module_exports_all_clients() -> None:
    """q_agent.llm 顶层导出所有 client，编排层一处 import 即可。"""
    from q_agent.llm import (
        AnthropicClient as ExportedAnthropic,
    )
    from q_agent.llm import (
        GeminiClient as ExportedGemini,
    )
    from q_agent.llm import (
        LLMClient as ExportedBase,
    )
    from q_agent.llm import (
        LocalLLMClient as ExportedLocal,
    )
    from q_agent.llm import (
        OllamaClient as ExportedOllama,
    )
    from q_agent.llm import (
        OpenAIClient as ExportedOpenAI,
    )

    assert ExportedBase is LLMClient
    assert ExportedOllama is OllamaClient
    assert ExportedLocal is LocalLLMClient
    assert ExportedOpenAI is OpenAIClient
    assert ExportedAnthropic is AnthropicClient
    assert ExportedGemini is GeminiClient
