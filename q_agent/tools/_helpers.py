"""工具内部辅助函数：统一错误 JSON 输出 + HTML 转 markdown（零依赖）。"""

import json
import re
from html.parser import HTMLParser


def error_json(error: str, message: str, recoverable: bool = True) -> str:
    """统一错误回喂 JSON 字符串。

    recoverable=True 表示 LLM 可自愈重试（改路径 / 改参数）。
    recoverable=False 表示 PermissionError 类硬拦截（零重试）。
    """
    return json.dumps(
        {"error": error, "message": message, "recoverable": recoverable},
        ensure_ascii=False,
    )


class _MarkdownExtractor(HTMLParser):
    """简易 HTML → markdown 抽取器：去标签 + 保留 a/code/pre/标题。

    零第三方依赖，仅用标准库 html.parser。
    """

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._in_pre = False
        self._in_code = False
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip = True
        elif tag == "pre":
            self._in_pre = True
            self.parts.append("\n```\n")
        elif tag == "code":
            self._in_code = True
            self.parts.append("`")
        elif tag == "a":
            href = dict(attrs).get("href", "")
            if href:
                self.parts.append("[")
        elif tag == "h1":
            self.parts.append("\n# ")
        elif tag == "h2":
            self.parts.append("\n## ")
        elif tag == "h3":
            self.parts.append("\n### ")
        elif tag == "p":
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False
        elif tag == "pre":
            self._in_pre = False
            self.parts.append("\n```\n")
        elif tag == "code":
            self._in_code = False
            self.parts.append("`")
        elif tag == "a":
            self.parts.append("]")
        elif tag in ("h1", "h2", "h3", "p"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def get_markdown(self) -> str:
        text = "".join(self.parts)
        # 压缩多余空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_markdown(html: str) -> str:
    """HTML 转 markdown（简易版，零依赖）。"""
    extractor = _MarkdownExtractor()
    extractor.feed(html)
    return extractor.get_markdown()
