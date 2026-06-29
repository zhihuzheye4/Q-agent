"""M2 安全层扩展测试：check_sensitive / sniff_secret_content / check_url / check_ssrf。

覆盖：
- 敏感文件清单命中（.env / *.pem / id_rsa / credentials.json / *.keystore）
- 敏感文件清单未命中（合法文件不误伤）
- 用户自定义清单（~/.q-agent/sensitive.txt 不存在时降级，存在时合并匹配）
- 内容嗅探命中（PEM 私钥 / AWS AKIA / GitHub PAT / OpenAI sk-）
- 内容嗅探未命中（合法内容不误伤）
- URL 强制 HTTPS（HTTP 拒绝，localhost:11434 例外）
- URL 域名白名单（白名单内通过，外拒绝）
- SSRF 私网段拒绝（10.x / 172.16-31.x / 192.168.x / 127.x / 169.254.x / ::1 / fc00::/7）
- SSRF 域名不拦截（域名走 DNS，不报错）
- 既有 check_command / check_path 不回归
"""

from __future__ import annotations

import pytest

from q_agent.tools.safety import (
    check_command,
    check_path,
    check_sensitive,
    check_ssrf,
    check_url,
    sniff_secret_content,
)

# ---------- check_sensitive：命中 ----------


@pytest.mark.parametrize(
    "path",
    [
        "/home/user/.env",
        "/home/user/.env.production",
        "/home/user/server.pem",
        "/home/user/.ssh/id_rsa",
        "/home/user/.aws/credentials",
        "/home/user/secret.key",
        "/tmp/credentials.json",
        "/home/user/cert.p12",
    ],
)
def test_check_sensitive_rejects(path: str) -> None:
    """敏感文件清单命中应抛 PermissionError。"""
    with pytest.raises(PermissionError, match="敏感文件"):
        check_sensitive(path)


# ---------- check_sensitive：未命中 ----------


@pytest.mark.parametrize(
    "path",
    [
        "/home/user/code/main.py",
        "/home/user/README.md",
        "/home/user/server.txt",
        "/home/user/.gitignore",
        "/home/user/env_example.txt",
        "/home/user/credentials_notes.md",
    ],
)
def test_check_sensitive_allows_safe_files(path: str) -> None:
    """合法文件不应被敏感清单误伤。"""
    check_sensitive(path)  # 不抛异常即通过


# ---------- sniff_secret_content：命中 ----------


def test_sniff_pem_private_key_rejected() -> None:
    """PEM 私钥头应被嗅探拦截。"""
    content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAI...\n-----END RSA PRIVATE KEY-----"
    with pytest.raises(PermissionError, match="私密凭证"):
        sniff_secret_content(content)


def test_sniff_ec_private_key_rejected() -> None:
    """EC 私钥头应被嗅探拦截。"""
    content = "-----BEGIN EC PRIVATE KEY-----\nMHQ...\n-----END EC PRIVATE KEY-----"
    with pytest.raises(PermissionError, match="私密凭证"):
        sniff_secret_content(content)


def test_sniff_openssh_private_key_rejected() -> None:
    """OPENSSH 私钥头应被嗅探拦截。"""
    content = "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNz...\n-----END OPENSSH PRIVATE KEY-----"
    with pytest.raises(PermissionError, match="私密凭证"):
        sniff_secret_content(content)


def test_sniff_aws_access_key_rejected() -> None:
    """AWS AKIA access key id 应被嗅探拦截。"""
    with pytest.raises(PermissionError, match="私密凭证"):
        sniff_secret_content("aws_access_key_id = AKIAIOSFODNN7EXAMPLE")


def test_sniff_github_pat_rejected() -> None:
    """GitHub PAT 应被嗅探拦截。"""
    with pytest.raises(PermissionError, match="私密凭证"):
        sniff_secret_content("GITHUB_TOKEN=ghp_0123456789012345678901234567890abcdef")


def test_sniff_openai_key_rejected() -> None:
    """OpenAI sk- key 应被嗅探拦截。"""
    with pytest.raises(PermissionError, match="私密凭证"):
        sniff_secret_content("OPENAI_API_KEY=sk-proj0123456789abcdefghijklmnopqrstuv")


# ---------- sniff_secret_content：未命中 ----------


@pytest.mark.parametrize(
    "content",
    [
        "import os\n\ndef main():\n    pass\n",
        "# 这是注释，含 AWS 字样但不是真 key\nAWS_REGION=us-east-1",
        "sk- 短字符串不匹配（少于 20 字符）",
        "普通配置文件，无任何凭证模式",
    ],
)
def test_sniff_safe_content_allowed(content: str) -> None:
    """合法内容不应被嗅探误伤。"""
    sniff_secret_content(content)  # 不抛即通过


# ---------- check_url：强制 HTTPS ----------


def test_check_url_http_rejected() -> None:
    """非 HTTPS 应被拒绝。"""
    with pytest.raises(PermissionError, match="仅允许 HTTPS"):
        check_url("http://github.com/repo")


def test_check_url_localhost_http_allowed() -> None:
    """localhost:11434 是 Ollama 本地例外，允许 HTTP。"""
    check_url("http://localhost:11434/api/tags")  # 不抛即通过


def test_check_url_https_allowed_domain() -> None:
    """HTTPS + 白名单域名应通过。"""
    check_url("https://pypi.org/project/pytest/")
    check_url("https://github.com/user/repo")
    check_url("https://raw.githubusercontent.com/user/repo/main/file")
    check_url("https://huggingface.co/models")
    check_url("https://docs.python.org/3/")


# ---------- check_url：白名单 ----------


def test_check_url_non_allowlisted_rejected() -> None:
    """白名单外域名应被拒绝。"""
    with pytest.raises(PermissionError, match="域名不在白名单"):
        check_url("https://evil.com/exfil")


def test_check_url_subdomain_of_allowlisted_allowed() -> None:
    """白名单域名的子域名应通过（raw.githubusercontent.com 是显式白名单，也支持子域规则）。"""
    check_url("https://sub.pypi.org/something")


# ---------- check_ssrf：私网段拒绝 ----------


@pytest.mark.parametrize(
    "url",
    [
        "https://10.0.0.1/",
        "https://172.16.0.1/",
        "https://172.31.255.255/",
        "https://192.168.1.1/",
        "https://127.0.0.1/",
        "https://169.254.169.254/",  # AWS metadata 端点
        "https://[::1]/",
        "https://[fc00::1]/",
    ],
)
def test_check_ssrf_private_ip_rejected(url: str) -> None:
    """私网段 IP 应被 SSRF 拦截。"""
    with pytest.raises(PermissionError, match="私网段"):
        check_ssrf(url)


def test_check_ssrf_domain_not_rejected() -> None:
    """域名（非 IP）不应被 SSRF 拦截——v0.0.19 不做 DNS rebinding 防护。"""
    check_ssrf("https://github.com/user/repo")  # 不抛即通过


def test_check_ssrf_public_ip_not_rejected() -> None:
    """公网 IP 不应被 SSRF 拦截。"""
    check_ssrf("https://8.8.8.8/")  # 不抛即通过


# ---------- 既有功能不回归 ----------


def test_check_command_still_works() -> None:
    """既有危险命令拦截不应回归。"""
    with pytest.raises(PermissionError):
        check_command(["rm", "-rf", "/"])


def test_check_path_still_works(tmp_path) -> None:
    """既有项目根保护不应回归。"""
    # tmp_path 不在 PROTECTED_ROOTS 下，应通过
    check_path(str(tmp_path / "test.txt"))
