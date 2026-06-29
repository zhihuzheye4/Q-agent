"""网络工具：web_get / web_fetch。

2 工具按域聚集。read_only 权限，过 check_url + check_ssrf。
零第三方依赖：urllib + html.parser（HTML→markdown）。
"""

import urllib.error
import urllib.request

from q_agent.tools._helpers import error_json, html_to_markdown
from q_agent.tools.registry import tool
from q_agent.tools.safety import check_ssrf, check_url


@tool(
    name="web_get",
    desc=(
        "对白名单域名发起 HTTP GET，返回原始响应体（前 2000 字符）。"
        "何时用：拉取 API JSON、查询文档站、检查连通性。"
        "何时不用：抓取 HTML 转 markdown（用 web_fetch）、上传数据、访问私网。"
        "参数约束：url 必须 HTTPS 且域名在白名单；私网段拒绝（SSRF 防护）。"
        "返回格式：status_code + body 前 2000 字符。"
    ),
    version="1.0.0",
    timeout=30.0,
    permission_level="read_only",
)
def web_get(url: str) -> str:
    check_url(url)
    check_ssrf(url)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = r.read(1_000_000).decode("utf-8", errors="ignore")
        return f"status={r.status}\nbody:\n{body[:2000]}"
    except urllib.error.URLError as e:
        return error_json("HTTPError", str(e))
    except TimeoutError as e:
        return error_json("Timeout", str(e))


@tool(
    name="web_fetch",
    desc=(
        "抓取 URL 内容并转为 markdown（1MB 截断）。"
        "何时用：阅读网页文档、抓取博客文章、获取在线教程。"
        "何时不用：JSON API（用 web_get）、需要原始 HTML。"
        "参数约束：同 web_get（HTTPS + 白名单 + SSRF）。"
        "返回格式：markdown 文本（前 2000 字符，落盘完整版）。"
    ),
    version="1.0.0",
    timeout=30.0,
    permission_level="read_only",
)
def web_fetch(url: str) -> str:
    check_url(url)
    check_ssrf(url)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            html_raw = r.read(1_000_000).decode("utf-8", errors="ignore")
    except urllib.error.URLError as e:
        return error_json("HTTPError", str(e))
    except TimeoutError as e:
        return error_json("Timeout", str(e))
    text = html_to_markdown(html_raw)
    return text[:2000]
