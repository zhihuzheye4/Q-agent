"""基本输入校验（不是沙箱）：危险命令黑名单 + 项目根目录保护。

实现要点：
- 路径校验用「前缀归属」判断（target.is_relative_to(root)），
  而非精确相等——否则 G:\\agent\\子目录 不命中，保护被绕过。
- 命令校验用 token 化匹配（连续子序列），而非裸子串——
  否则多空格 / 等价 flag / 误报（"information" 含 "format"）都会出问题。
"""

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
