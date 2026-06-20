"""Ollama 本地 LLM 后端客户端。

设计：
    - 使用标准库 urllib.request，零新运行时依赖（坚守 CLAUDE.md 第二十节）
    - list_models()：UI 下拉框填充用，已实现。返回 ModelEntry 列表，
      通过 remote_model / remote_host 字段区分真正本地模型 vs Ollama Cloud 转发模型
    - OllamaClient(LLMClient)：完整客户端骨架，chat/complete 留 NotImplementedError
      待下一阶段接 /api/chat 端点

API 参考（Ollama 0.1.x+）：
    GET  http://localhost:11434/api/tags   → 模型列表（已实现，含本地/云端转发判定）
    POST http://localhost:11434/api/chat   → 多轮对话（待实现）
    POST http://localhost:11434/api/generate → 单轮补全（待实现）

Ollama Cloud 判定：
    /api/tags 每个 model item 含以下字段（部分）：
        - name / model：模型名
        - size：本地磁盘字节数（cloud 转发模型可能为 0）
        - remote_model：上游模型名（仅 cloud 转发模型有）
        - remote_host：上游 Ollama host URL（仅 cloud 转发模型有，如 https://ollama.com）
    is_remote = bool(remote_model) or bool(remote_host)
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any, NamedTuple

from q_agent.llm.base import LLMClient


class OllamaError(Exception):
    """Ollama 后端调用失败统一异常。message 已是面向用户的友好描述。"""


class ModelEntry(NamedTuple):
    """Ollama 上一个模型的元数据。

    Attributes:
        name: 模型名（如 "qwen2.5:7b" / "minimax-m3:latest"）
        is_remote: True 表示该模型是 Ollama Cloud 转发的（非本地权重），
                   False 表示真正装在本地的模型
        remote_host: 上游 Ollama host URL（仅 is_remote=True 时有值，否则空串）
    """

    name: str
    is_remote: bool
    remote_host: str


def list_models(
    host: str = "http://localhost:11434",
    timeout: float = 2.0,
) -> list[ModelEntry]:
    """查询 Ollama 当前可用模型列表（含本地/云端转发判定）。

    Args:
        host: Ollama 服务地址，默认 http://localhost:11434
        timeout: 网络超时秒数，默认 2.0（UI 友好，避免长时间卡死）

    Returns:
        模型条目列表（含 name + is_remote + remote_host），无模型时返回空列表。
        is_remote=True 表示该模型是 Ollama Cloud 转发的（非本地权重）

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

    entries: list[ModelEntry] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if not isinstance(name, str) or not name:
            continue
        remote_model = item.get("remote_model")
        remote_host_val = item.get("remote_host")
        # remote_model 或 remote_host 任一非空 → cloud 转发
        is_remote = bool(remote_model) or bool(remote_host_val)
        remote_host = remote_host_val if isinstance(remote_host_val, str) else ""
        entries.append(ModelEntry(name=name, is_remote=is_remote, remote_host=remote_host))
    return entries


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
        """多轮对话同步返回完整文本。

        内部用 chat_stream 流式读取后拼接。供编排层等不需要流式刷新的场景使用。
        UI 流式刷新应直接用 chat_stream。
        """
        return "".join(self.chat_stream(messages))

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        timeout: float = 120.0,
    ) -> Iterator[str]:
        """多轮对话流式 yield 文本 chunk。

        POST {host}/api/chat body={"model":..., "messages":..., "stream": true}。
        响应是 NDJSON：每行一个 chunk JSON，含 message.content 字段。
        done=true 的末行 content 通常为空，遇到即返回。

        Args:
            messages: Ollama 格式 [{"role": "user"/"assistant", "content": ...}]
            timeout: 网络超时秒数，默认 120s（生成可能慢，比 list_models 的 2s 长）

        Yields:
            每个 chunk 的 message.content 文本片段

        Raises:
            OllamaError: 连接拒绝 / 超时 / HTTP 错误 / JSON 解析失败
        """
        url = self.host.rstrip("/") + "/api/chat"
        payload = json.dumps({"model": self.model, "messages": messages, "stream": True}).encode(
            "utf-8"
        )
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for raw_line in resp:
                    if not raw_line:
                        continue
                    try:
                        chunk = json.loads(raw_line.decode("utf-8"))
                    except json.JSONDecodeError:
                        # 单行解析失败跳过，继续读后续 chunk（不致命）
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    msg = chunk.get("message", {})
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
                        if isinstance(content, str) and content:
                            yield content
                    if chunk.get("done"):
                        return
        except urllib.error.HTTPError as e:
            raise OllamaError(f"Ollama 返回 HTTP {e.code}：{e.reason}") from e
        except urllib.error.URLError as e:
            reason = e.reason
            if isinstance(reason, socket.timeout) or "timed out" in str(reason).lower():
                msg = f"连接 Ollama 超时（{timeout}s）：请确认服务运行于 {self.host}"
                raise OllamaError(msg) from e
            raise OllamaError(f"无法连接 Ollama（{self.host}）：{reason}。请确认服务已启动") from e
        except TimeoutError as e:
            msg = f"连接 Ollama 超时（{timeout}s）：请确认服务运行于 {self.host}"
            raise OllamaError(msg) from e

    def complete(self, prompt: str) -> str:
        """单轮补全。待接 POST /api/generate。"""
        raise NotImplementedError(
            "Ollama complete 调用待实现，下一步用户提'接对话'需求后填充方法体"
        )
