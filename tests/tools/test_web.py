"""M3 web.py 2 工具测试：web_get / web_fetch + URL 白名单 + SSRF。

注：真实网络请求用 mock，避免依赖外网。
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from q_agent.tools.web import web_fetch, web_get

# ---------- web_get：URL 校验 ----------


def test_web_get_http_rejected() -> None:
    """HTTP 非 localhost 应被拒绝。"""
    with pytest.raises(PermissionError, match="仅允许 HTTPS"):
        web_get("http://github.com/repo")


def test_web_get_non_allowlisted_rejected() -> None:
    """白名单外域名应被拒绝。"""
    with pytest.raises(PermissionError, match="域名不在白名单"):
        web_get("https://evil.com/exfil")


def test_web_get_ssrf_private_rejected() -> None:
    """私网段 IP 应被拦截（白名单先抛或 SSRF 先抛均可）。"""
    with pytest.raises(PermissionError, match="私网段|白名单"):
        web_get("https://10.0.0.1/")


# ---------- web_get：mock 真实请求 ----------


class _FakeResponse:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body.encode("utf-8")
        self.status = status

    def read(self, size: int = -1) -> bytes:
        return self._body[:size] if size > 0 else self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        pass


@patch("q_agent.tools.web.urllib.request.urlopen")
def test_web_get_happy(mock_urlopen: patch) -> None:
    """白名单 HTTPS 应返回 status + body。"""
    mock_urlopen.return_value = _FakeResponse('{"key": "value"}', status=200)
    result = web_get("https://pypi.org/project/pytest/")
    assert "status=200" in result
    assert "key" in result and "value" in result


@patch("q_agent.tools.web.urllib.request.urlopen")
def test_web_get_truncates_body(mock_urlopen: patch) -> None:
    """body 应截断到 2000 字符。"""
    mock_urlopen.return_value = _FakeResponse("x" * 5000, status=200)
    result = web_get("https://github.com/user/repo")
    body_part = result.split("body:\n")[1]
    assert len(body_part) <= 2000


@patch("q_agent.tools.web.urllib.request.urlopen", side_effect=Exception("network error"))
def test_web_get_http_error(mock_urlopen: patch) -> None:
    """URLError 应返回 HTTPError JSON。"""
    # Exception 不被 except urllib.error.URLError 捕获，会传播
    # 改用 URLError
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("network error")
    result = web_get("https://github.com/user/repo")
    data = json.loads(result)
    assert data["error"] == "HTTPError"
    assert data["recoverable"] is True


# ---------- web_fetch ----------


@patch("q_agent.tools.web.urllib.request.urlopen")
def test_web_fetch_happy(mock_urlopen: patch) -> None:
    """web_fetch 应返回 markdown 文本。"""
    html = "<html><body><h1>标题</h1><p>段落</p></body></html>"
    mock_urlopen.return_value = _FakeResponse(html, status=200)
    result = web_fetch("https://docs.python.org/3/")
    assert "标题" in result
    assert "段落" in result


@patch("q_agent.tools.web.urllib.request.urlopen")
def test_web_fetch_strips_script_style(mock_urlopen: patch) -> None:
    """script/style 内容应被剥离。"""
    html = "<script>alert(1)</script><style>x{}</style><p>visible</p>"
    mock_urlopen.return_value = _FakeResponse(html, status=200)
    result = web_fetch("https://huggingface.co/models")
    assert "visible" in result
    assert "alert" not in result
    assert "x{}" not in result


def test_web_fetch_http_rejected() -> None:
    """web_fetch HTTP 应被拒绝。"""
    with pytest.raises(PermissionError, match="仅允许 HTTPS"):
        web_fetch("http://github.com/repo")
