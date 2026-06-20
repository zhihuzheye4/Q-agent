"""Ollama 本地 LLM 后端客户端。

设计：
    - 使用标准库 urllib.request，零新运行时依赖（坚守 CLAUDE.md 第二十节）
    - list_models()：UI 下拉框填充用，已实现
    - OllamaClient(LLMClient)：完整客户端骨架，chat/complete 留 NotImplementedError
      待下一阶段接 /api/chat 端点

API 参考（Ollama 0.1.x+）：
    GET  http://localhost:11434/api/tags   → 模型列表（已实现）
    POST http://localhost:11434/api/chat   → 多轮对话（待实现）
    POST http://localhost:11434/api/generate → 单轮补全（待实现）
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any

from q_agent.llm.base import LLMClient


class OllamaError(Exception):
    """Ollama 后端调用失败统一异常。message 已是面向用户的友好描述。"""


def list_models(
    host: str = "http://localhost:11434",
    timeout: float = 2.0,
) -> list[str]:
    """查询 Ollama 当前可用模型列表。

    Args:
        host: Ollama 服务地址，默认 http://localhost:11434
        timeout: 网络超时秒数，默认 2.0（UI 友好，避免长时间卡死）

    Returns:
        模型名列表（如 ["qwen2.5:7b", "llama3:8b"]），无模型时返回空列表

    Raises:
        OllamaError: 连接拒绝 / 超时 / HTTP 错误 / JSON 解析失败 等所有失败场景
    """
    url = host.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        # HTTPError 是 URLError 子类，必须先于 URLError 捕获
        raise OllamaError(f"Ollama 返回 HTTP {e.code}：{e.reason}") from e
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, socket.timeout) or "timed out" in str(reason).lower():
            msg = f"连接 Ollama 超时（{timeout}s）：请确认服务运行于 {host}"
            raise OllamaError(msg) from e
        raise OllamaError(f"无法连接 Ollama（{host}）：{reason}。请确认服务已启动") from e
    except TimeoutError as e:
        msg = f"连接 Ollama 超时（{timeout}s）：请确认服务运行于 {host}"
        raise OllamaError(msg) from e

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise OllamaError(f"Ollama 响应非合法 JSON：{e}") from e

    raw_models = data.get("models", [])
    if not isinstance(raw_models, list):
        raise OllamaError(f"Ollama 响应字段 models 非列表：{type(raw_models).__name__}")

    names: list[str] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if isinstance(name, str) and name:
            names.append(name)
    return names


class OllamaClient(LLMClient):
    """Ollama 本地 LLM 完整客户端骨架。

    已实现：构造（model + host 参数存好）
    待实现：chat() / complete() 调用 POST /api/chat 和 POST /api/generate

    下一阶段（用户提"接对话"需求后）填充 chat/complete 方法体，不动构造与接口。
    """

    def __init__(self, model: str, host: str = "http://localhost:11434") -> None:
        self.model = model
        self.host = host

    def chat(self, messages: list[dict[str, Any]]) -> str:
        """多轮对话。待接 POST /api/chat（{"model":..., "messages":...}）。"""
        raise NotImplementedError("Ollama chat 调用待实现，下一步用户提'接对话'需求后填充方法体")

    def complete(self, prompt: str) -> str:
        """单轮补全。待接 POST /api/generate。"""
        raise NotImplementedError(
            "Ollama complete 调用待实现，下一步用户提'接对话'需求后填充方法体"
        )
