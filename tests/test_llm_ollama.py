"""Ollama 客户端单测。

覆盖：
    - happy path：返回 ModelEntry 列表
    - 空模型列表
    - 本地模型 is_remote=False
    - Ollama Cloud 转发模型 is_remote=True（remote_model 字段）
    - Ollama Cloud 转发模型 is_remote=True（remote_host 字段）
    - 连接拒绝（URLError）
    - 超时（URLError.reason = socket.timeout 或 "timed out"）
    - HTTP 错误
    - JSON 解析失败
    - models 字段非列表
"""

from __future__ import annotations

import io
import urllib.error
from unittest.mock import patch

import pytest

from q_agent.llm.ollama import ModelEntry, OllamaError, list_models


class _FakeResponse:
    """urlopen context manager 替身。"""

    def __init__(self, body: bytes) -> None:
        self._buf = io.BytesIO(body)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self._buf.close()

    def read(self) -> bytes:
        return self._buf.getvalue()


def test_list_models_happy() -> None:
    """正常返回 ModelEntry 列表，本地模型 is_remote=False。"""
    body = b'{"models": [{"name": "qwen2.5:7b"}, {"name": "llama3:8b"}]}'
    with patch("q_agent.llm.ollama.urllib.request.urlopen", return_value=_FakeResponse(body)):
        result = list_models()
    assert result == [
        ModelEntry(name="qwen2.5:7b", is_remote=False, remote_host=""),
        ModelEntry(name="llama3:8b", is_remote=False, remote_host=""),
    ]


def test_list_models_empty() -> None:
    """Ollama 在跑但无模型 → 空列表。"""
    body = b'{"models": []}'
    with patch("q_agent.llm.ollama.urllib.request.urlopen", return_value=_FakeResponse(body)):
        result = list_models()
    assert result == []


def test_list_models_uses_model_field_fallback() -> None:
    """name 缺失时退回 model 字段。"""
    body = b'{"models": [{"model": "phi3:mini"}]}'
    with patch("q_agent.llm.ollama.urllib.request.urlopen", return_value=_FakeResponse(body)):
        result = list_models()
    assert result == [ModelEntry(name="phi3:mini", is_remote=False, remote_host="")]


def test_list_models_skips_non_dict_entries() -> None:
    """models 数组含非 dict 项时跳过。"""
    body = b'{"models": [{"name": "ok:1"}, "garbage", 42, null]}'
    with patch("q_agent.llm.ollama.urllib.request.urlopen", return_value=_FakeResponse(body)):
        result = list_models()
    assert result == [ModelEntry(name="ok:1", is_remote=False, remote_host="")]


def test_list_models_remote_via_remote_model_field() -> None:
    """remote_model 字段非空 → is_remote=True（Ollama Cloud 转发模型）。"""
    body = b"""{"models": [
        {"name": "minimax-m3:latest", "remote_model": "minimax/m3", "remote_host": "https://ollama.com"},
        {"name": "qwen2.5:7b"}
    ]}"""
    with patch("q_agent.llm.ollama.urllib.request.urlopen", return_value=_FakeResponse(body)):
        result = list_models()
    assert result[0].is_remote is True
    assert result[0].remote_host == "https://ollama.com"
    assert result[1].is_remote is False


def test_list_models_remote_via_remote_host_only() -> None:
    """仅 remote_host 字段非空也判定为 cloud 转发。"""
    body = b'{"models": [{"name": "deepseek-v4-pro", "remote_host": "https://ollama.com"}]}'
    with patch("q_agent.llm.ollama.urllib.request.urlopen", return_value=_FakeResponse(body)):
        result = list_models()
    assert result[0].is_remote is True
    assert result[0].remote_host == "https://ollama.com"


def test_list_models_remote_model_empty_string_is_local() -> None:
    """remote_model 为空字符串 → is_remote=False（graceful，不误判）。"""
    body = b'{"models": [{"name": "qwen2.5:7b", "remote_model": "", "remote_host": ""}]}'
    with patch("q_agent.llm.ollama.urllib.request.urlopen", return_value=_FakeResponse(body)):
        result = list_models()
    assert result[0].is_remote is False


def test_list_models_connection_refused() -> None:
    """URLError（连接拒绝）→ OllamaError 含友好提示。"""
    err = urllib.error.URLError(ConnectionRefusedError("Connection refused"))
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=err),
        pytest.raises(OllamaError) as exc,
    ):
        list_models()
    assert "无法连接" in str(exc.value) or "Ollama" in str(exc.value)


def test_list_models_timeout_via_urlerror_reason() -> None:
    """URLError.reason 为 socket.timeout → OllamaError 含超时提示。"""
    err = urllib.error.URLError(TimeoutError("timed out"))
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=err),
        pytest.raises(OllamaError) as exc,
    ):
        list_models(timeout=1.0)
    assert "超时" in str(exc.value)


def test_list_models_timeout_via_socket_timeout() -> None:
    """直接抛 socket.timeout → OllamaError。"""
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=TimeoutError("timed out")),
        pytest.raises(OllamaError) as exc,
    ):
        list_models(timeout=1.0)
    assert "超时" in str(exc.value)


def test_list_models_http_error() -> None:
    """HTTPError → OllamaError 含状态码。"""
    err = urllib.error.HTTPError(
        url="http://localhost:11434/api/tags",
        code=500,
        msg="Internal Server Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=err),
        pytest.raises(OllamaError) as exc,
    ):
        list_models()
    assert "HTTP 500" in str(exc.value)


def test_list_models_invalid_json() -> None:
    """响应非合法 JSON → OllamaError。"""
    body = b"not json at all"
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", return_value=_FakeResponse(body)),
        pytest.raises(OllamaError) as exc,
    ):
        list_models()
    assert "JSON" in str(exc.value)


def test_list_models_models_not_list() -> None:
    """models 字段非列表 → OllamaError。"""
    body = b'{"models": "should_be_list"}'
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", return_value=_FakeResponse(body)),
        pytest.raises(OllamaError) as exc,
    ):
        list_models()
    assert "非列表" in str(exc.value)


def test_list_models_url_built_from_host() -> None:
    """host 末尾斜杠被正确剥离。"""
    captured: list[str] = []
    body = b'{"models": []}'

    def fake_urlopen(url: str, **kw: object) -> _FakeResponse:
        captured.append(url)
        return _FakeResponse(body)

    with patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=fake_urlopen):
        list_models(host="http://localhost:11434/")
    assert captured == ["http://localhost:11434/api/tags"]
