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
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from q_agent.llm.ollama import (
    ModelEntry,
    OllamaClient,
    OllamaError,
    list_models,
    release_model,
)


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


class _FakeStreamResponse:
    """urlopen context manager 替身，支持行迭代（chat_stream 用）。"""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def __enter__(self) -> _FakeStreamResponse:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def __iter__(self) -> Iterator[bytes]:
        yield from self._lines


def test_chat_stream_happy() -> None:
    """chat_stream 流式 yield chunks 的 message.content 拼接为完整文本。"""
    lines = [
        '{"model":"qwen2.5:7b","message":{"role":"assistant","content":"你好"},"done":false}\n'.encode(),
        '{"model":"qwen2.5:7b","message":{"role":"assistant","content":"，世界"},"done":false}\n'.encode(),
        b'{"model":"qwen2.5:7b","message":{"role":"assistant","content":""},"done":true}\n',
    ]
    with patch(
        "q_agent.llm.ollama.urllib.request.urlopen",
        return_value=_FakeStreamResponse(lines),
    ):
        client = OllamaClient(model="qwen2.5:7b")
        chunks = list(client.chat_stream([{"role": "user", "content": "打招呼"}]))
    assert chunks == ["你好", "，世界"]


def test_chat_stream_stops_on_done() -> None:
    """遇到 done=true 即返回，后续 chunk 不再 yield。"""
    lines = [
        b'{"message":{"content":"a"},"done":false}\n',
        b'{"message":{"content":"b"},"done":true}\n',
        b'{"message":{"content":"should_not_yield"},"done":false}\n',
    ]
    with patch(
        "q_agent.llm.ollama.urllib.request.urlopen",
        return_value=_FakeStreamResponse(lines),
    ):
        client = OllamaClient(model="m")
        chunks = list(client.chat_stream([]))
    assert chunks == ["a", "b"]


def test_chat_stream_skips_invalid_json_line() -> None:
    """单行 JSON 解析失败跳过，继续读后续 chunk（不致命）。"""
    lines = [
        b'{"message":{"content":"ok"}}\n',
        b"not json\n",
        b'{"message":{"content":"again"},"done":true}\n',
    ]
    with patch(
        "q_agent.llm.ollama.urllib.request.urlopen",
        return_value=_FakeStreamResponse(lines),
    ):
        client = OllamaClient(model="m")
        chunks = list(client.chat_stream([]))
    assert chunks == ["ok", "again"]


def test_chat_stream_http_error() -> None:
    """HTTPError → OllamaError 含状态码。"""
    err = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat",
        code=500,
        msg="Internal Server Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=err),
        pytest.raises(OllamaError) as exc,
    ):
        client = OllamaClient(model="m")
        list(client.chat_stream([]))
    assert "HTTP 500" in str(exc.value)


def test_chat_stream_connection_refused() -> None:
    """URLError（连接拒绝）→ OllamaError 含友好提示。"""
    err = urllib.error.URLError(ConnectionRefusedError("Connection refused"))
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=err),
        pytest.raises(OllamaError) as exc,
    ):
        client = OllamaClient(model="m")
        list(client.chat_stream([]))
    assert "无法连接" in str(exc.value) or "Ollama" in str(exc.value)


def test_chat_full_via_stream() -> None:
    """chat() = "".join(chat_stream())，同步返回完整文本。"""
    lines = [
        b'{"message":{"content":"Hello"},"done":false}\n',
        b'{"message":{"content":", "},"done":false}\n',
        b'{"message":{"content":"world!"},"done":true}\n',
    ]
    with patch(
        "q_agent.llm.ollama.urllib.request.urlopen",
        return_value=_FakeStreamResponse(lines),
    ):
        client = OllamaClient(model="m")
        result = client.chat([{"role": "user", "content": "hi"}])
    assert result == "Hello, world!"


def test_release_model_happy() -> None:
    """release_model POST /api/generate keep_alive=0 正常调用不抛错（verify=False 跳过验证）。"""
    captured: list[bytes] = []

    def fake_urlopen(req: object, **kw: object) -> _FakeResponse:
        captured.append(req.data if hasattr(req, "data") else b"")  # type: ignore[arg-type]
        return _FakeResponse(b'{"done":true}')

    with patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=fake_urlopen):
        release_model("qwen2.5:7b", verify=False)
    # 验证 payload 含 keep_alive=0
    assert len(captured) == 1
    import json as _json

    payload = _json.loads(captured[0].decode("utf-8"))
    assert payload == {"model": "qwen2.5:7b", "keep_alive": 0}


def test_release_model_verifies_unload_success() -> None:
    """v0.0.11 verify=True：generate OK + /api/ps 返回空 → 通过（不抛错）。"""
    calls: list[str] = []

    def fake_urlopen(req: object, **kw: object) -> _FakeResponse:
        # req 可能是 Request 对象（generate，有 full_url）或字符串（/api/ps）
        url = req if isinstance(req, str) else req.full_url  # type: ignore[union-attr]
        calls.append(url)
        if "/api/ps" in url:
            return _FakeResponse(b'{"models":[]}')
        return _FakeResponse(b'{"done":true,"done_reason":"unload"}')

    with patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=fake_urlopen):
        release_model("qwen2.5:7b")  # verify=True 默认
    # 应该有 2 次调用：generate + ps
    assert any("/api/generate" in c for c in calls)
    assert any("/api/ps" in c for c in calls)


def test_release_model_verifies_unload_still_loaded() -> None:
    """v0.0.11 verify=True：generate OK + /api/ps 仍含该模型（3 次轮询后）→ OllamaError。"""

    def fake_urlopen(req: object, **kw: object) -> _FakeResponse:
        url = req if isinstance(req, str) else req.full_url  # type: ignore[union-attr]
        if "/api/ps" in url:
            # 模型仍在内存
            return _FakeResponse(b'{"models":[{"name":"qwen2.5:7b"}]}')
        return _FakeResponse(b'{"done":true,"done_reason":"unload"}')

    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=fake_urlopen),
        patch("q_agent.llm.ollama.time.sleep", return_value=None),  # 跳过 sleep 加速测试
        pytest.raises(OllamaError) as exc,
    ):
        release_model("qwen2.5:7b", verify_attempts=3, verify_interval=0.0)
    assert "仍在内存" in str(exc.value) or "卸载" in str(exc.value)


def test_release_model_verify_retries_until_success() -> None:
    """v0.0.11 verify 轮询：前 2 次 /api/ps 含模型，第 3 次空 → 通过。"""
    ps_responses = [
        b'{"models":[{"name":"qwen2.5:7b"}]}',
        b'{"models":[{"name":"qwen2.5:7b"}]}',
        b'{"models":[]}',
    ]
    ps_idx = {"i": 0}

    def fake_urlopen(req: object, **kw: object) -> _FakeResponse:
        url = req if isinstance(req, str) else req.full_url  # type: ignore[union-attr]
        if "/api/ps" in url:
            i = ps_idx["i"]
            ps_idx["i"] += 1
            return _FakeResponse(ps_responses[min(i, len(ps_responses) - 1)])
        return _FakeResponse(b'{"done":true,"done_reason":"unload"}')

    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=fake_urlopen),
        patch("q_agent.llm.ollama.time.sleep", return_value=None),
    ):
        release_model("qwen2.5:7b", verify_attempts=3, verify_interval=0.0)
    # 第 3 次 /api/ps 才返回空 → 通过（不抛错）
    assert ps_idx["i"] == 3


def test_release_model_verify_disabled_skips_ps() -> None:
    """v0.0.11 verify=False：只调 generate，不调 /api/ps。"""
    urls: list[str] = []

    def fake_urlopen(req: object, **kw: object) -> _FakeResponse:
        url = req if isinstance(req, str) else req.full_url  # type: ignore[union-attr]
        urls.append(url)
        return _FakeResponse(b'{"done":true}')

    with patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=fake_urlopen):
        release_model("m", verify=False)
    assert all("/api/ps" not in u for u in urls)
    assert any("/api/generate" in u for u in urls)


def test_release_model_http_error() -> None:
    """HTTPError → OllamaError 含状态码。"""
    err = urllib.error.HTTPError(
        url="http://localhost:11434/api/generate",
        code=500,
        msg="Internal Server Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=err),
        pytest.raises(OllamaError) as exc,
    ):
        release_model("m")
    assert "HTTP 500" in str(exc.value)


def test_release_model_connection_refused() -> None:
    """URLError（连接拒绝）→ OllamaError 含友好提示。"""
    err = urllib.error.URLError(ConnectionRefusedError("Connection refused"))
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=err),
        pytest.raises(OllamaError) as exc,
    ):
        release_model("m")
    assert "无法连接" in str(exc.value) or "Ollama" in str(exc.value)


def test_release_model_timeout() -> None:
    """TimeoutError → OllamaError 含超时提示。"""
    with (
        patch("q_agent.llm.ollama.urllib.request.urlopen", side_effect=TimeoutError("timed out")),
        pytest.raises(OllamaError) as exc,
    ):
        release_model("m", timeout=1.0)
    assert "超时" in str(exc.value)
