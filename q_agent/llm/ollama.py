"""Ollama 本地 LLM 后端客户端（首版仅检测模型列表）。

设计：
    - 使用标准库 urllib.request，零新运行时依赖（坚守 CLAUDE.md 第二十节）
    - 仅实现 list_models()——供 UI 下拉框填充
    - chat()/complete() 留待下一阶段（用户提需求后讨论）

API 参考（Ollama 0.1.x+）：
    GET http://localhost:11434/api/tags
    返回：{"models": [{"name": "qwen2.5:7b", "model": "qwen2.5:7b", ...}, ...]}
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass


class OllamaError(Exception):
    """Ollama 后端调用失败统一异常。message 已是面向用户的友好描述。"""


@dataclass(frozen=True)
class OllamaModel:
    """Ollama 模型条目。首版仅用 name，其余字段留作后续扩展。"""

    name: str


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
