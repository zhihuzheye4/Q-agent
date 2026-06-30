"""基本输入校验（不是沙箱）：危险命令黑名单 + 项目根目录保护 + 敏感文件/内容/URL/SSRF 防护。

实现要点：
- 路径校验用「前缀归属」判断（target.is_relative_to(root)），
  而非精确相等——否则 G:\\agent\\子目录 不命中，保护被绕过。
- 命令校验用 token 化匹配（连续子序列），而非裸子串——
  否则多空格 / 等价 flag / 误报（"information" 含 "format"）都会出问题。
- 敏感文件用 fnmatch glob 匹配（*.pem / .env / id_rsa 等）。
- 内容嗅探用正则匹配 PRIVATE KEY / AWS AKIA / GitHub PAT / OpenAI sk- key 模式。
- URL 校验：强制 HTTPS + 域名白名单 + 私网段 SSRF 拦截。
"""

import fnmatch
import ipaddress
import re
import urllib.parse
from pathlib import Path

# 项目根目录保护：禁止以这些路径或其子路径作为操作目标
PROTECTED_ROOTS: tuple[str, ...] = (r"G:\agent", "G:/agent", ".")

# 危险命令黑名单（绝对禁止）——以 token 元组形式定义，按连续子序列匹配。
# 这样天然规避多空格绕过；"format" 作为单 token 精确匹配，不再误伤 "information"。
DANGER_PATTERNS: tuple[tuple[str, ...], ...] = (
    # Linux/macOS 递归强删根或家目录
    ("rm", "-rf", "/"),
    ("rm", "-rf", "~"),
    ("rm", "-rf", "/*"),
    ("rm", "-rf", "~/*"),
    ("rm", "-r", "-f", "/"),
    ("rm", "-r", "-f", "~"),
    ("rm", "--recursive", "--force", "/"),
    ("rm", "--recursive", "--force", "~"),
    ("rm", "-fr", "/"),
    ("rm", "-fr", "~"),
    # Windows 递归强删
    ("del", "/s", "/q"),
    ("rmdir", "/s"),
    ("rd", "/s"),
    # Windows 格式化
    ("format",),
)

# 敏感文件清单（命中即拒绝 read/write）——glob 模式，匹配文件名或路径子串
SENSITIVE_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_rsa.*",
    "credentials.json",
    "credentials",
    ".aws/credentials",
    ".git-credentials",
    "*.keystore",
    "*.p12",
)

# 用户自定义敏感文件 glob 清单（运行时加载，每行一个 glob）
SENSITIVE_USER_FILE = Path.home() / ".q-agent" / "sensitive.txt"

# 写入内容嗅探正则：命中私密凭证模式 → PermissionError
SECRET_CONTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"ghp_[0-9A-Za-z]{36}"),  # GitHub PAT
    re.compile(r"sk-[0-9A-Za-z]{20,}"),  # OpenAI key 风格
)

# URL 域名白名单——仅允许 HTTPS 访问这些域名（localhost:11434 是 Ollama 本地例外）
URL_ALLOWLIST: set[str] = {
    "pypi.org",
    "github.com",
    "raw.githubusercontent.com",
    "huggingface.co",
    "docs.python.org",
    "localhost:11434",
}

# 私网段——SSRF 拦截目标
PRIVATE_RANGES: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
)


def _tokenize(cmd: str | list[str]) -> list[str]:
    """统一为 token 列表。list 直接用，str 按空白拆分（多空格自动归一）。"""
    if isinstance(cmd, list):
        return list(cmd)
    return cmd.split()


def check_command(cmd: str | list[str]) -> None:
    """检查命令是否含危险模式。命中则抛 PermissionError。

    匹配规则：危险 token 元组作为连续子序列出现在命令 token 中。
    """
    tokens = _tokenize(cmd)
    n = len(tokens)
    for danger in DANGER_PATTERNS:
        L = len(danger)
        if L == 0 or n < L:
            continue
        for i in range(n - L + 1):
            if tuple(tokens[i : i + L]) == danger:
                raise PermissionError(f"危险命令被拦截: {' '.join(danger)}")


def check_path(path: str) -> None:
    """检查路径是否落入受保护根目录（含子路径）。命中则抛 PermissionError。

    匹配规则：target 路径解析后位于任一受保护根目录之下（含根本身）。
    """
    target = Path(path).resolve()
    for root in PROTECTED_ROOTS:
        try:
            root_resolved = Path(root).resolve()
        except OSError:
            continue
        if target.is_relative_to(root_resolved):
            raise PermissionError(f"目标落入受保护根目录: {path}")


def _glob_match(pattern: str, name: str) -> bool:
    """fnmatch glob 匹配，支持 * 和 ? 通配符。"""
    return fnmatch.fnmatch(name, pattern)


def check_sensitive(path: str) -> None:
    """命中敏感文件清单 → PermissionError（不回喂 recoverable，零重试）。

    匹配规则：文件名匹配 SENSITIVE_PATTERNS 任一 glob，或路径含模式子串。
    用户自定义清单 ~/.q-agent/sensitive.txt 若存在也参与匹配。
    """
    p = Path(path).resolve()
    name = p.name
    for pat in SENSITIVE_PATTERNS:
        if _glob_match(pat, name):
            raise PermissionError(f"敏感文件被拦截: {path}")
    if SENSITIVE_USER_FILE.exists():
        for line in SENSITIVE_USER_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and _glob_match(line, name):
                raise PermissionError(f"用户自定义敏感文件被拦截: {path}")


def sniff_secret_content(content: str) -> None:
    """写入内容嗅探：命中私密凭证模式 → PermissionError。

    匹配模式：PEM 私钥头 / AWS AKIA / GitHub PAT / OpenAI sk- key。
    """
    for rx in SECRET_CONTENT_PATTERNS:
        if rx.search(content):
            raise PermissionError("写入内容含私密凭证模式，拒绝")


def check_url(url: str) -> None:
    """强制 HTTPS + 域名白名单。命中则抛 PermissionError。

    例外：localhost:11434（Ollama 本地）允许 HTTP。
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" and parsed.netloc != "localhost:11434":
        raise PermissionError(f"仅允许 HTTPS: {url}")
    host = parsed.hostname or ""
    # 白名单条目可能带端口（localhost:11434）或不带，取域名部分比较
    allowed = any(
        host == h.split(":")[0] or host.endswith("." + h.split(":")[0]) for h in URL_ALLOWLIST
    )
    if not allowed:
        raise PermissionError(f"域名不在白名单: {host}")


def check_ssrf(url: str) -> None:
    """私网段拒绝（SSRF 防护）。命中则抛 PermissionError。

    匹配规则：URL hostname 解析为 IP 后落入 PRIVATE_RANGES 任一网段。
    域名（非 IP）走 DNS，由 urllib 自行解析；v0.0.19 不做 DNS rebinding 防护。
    """
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    for net in PRIVATE_RANGES:
        if ip in net:
            raise PermissionError(f"私网段被拦截: {ip}")
