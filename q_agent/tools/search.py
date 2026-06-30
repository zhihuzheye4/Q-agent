"""搜索工具：search_content / search_glob。

2 工具按域聚集。read_only 权限，仅过 check_path。
"""

import re
from pathlib import Path

from q_agent.tools._helpers import error_json
from q_agent.tools.registry import tool
from q_agent.tools.safety import check_path


@tool(
    name="search_content",
    desc=(
        "在文件内容中搜索正则或字面量（递归）。"
        "何时用：查找某函数定义、某变量引用、某字符串出现位置。"
        "何时不用：按文件名查找（用 search_glob）、单文件内搜索（用 file_read 后自处理）。"
        "参数约束：root 必须为目录；pattern 为正则；max_results 默认 50。"
        "返回格式：每行 path:line:matched_text。"
    ),
    version="1.0.0",
    timeout=15.0,
    permission_level="read_only",
)
def search_content(root: str, pattern: str, max_results: int = 50) -> str:
    check_path(root)
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return error_json("InvalidPattern", f"正则编译失败: {e}")
    hits: list[str] = []
    for p in Path(root).rglob("*"):
        if not p.is_file() or p.stat().st_size > 500_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except (PermissionError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{p}:{i}:{line[:120]}")
                if len(hits) >= max_results:
                    return "\n".join(hits) + f"\n[截断：达 max_results={max_results}]"
    return "\n".join(hits) if hits else "无匹配"


@tool(
    name="search_glob",
    desc=(
        "按文件名 glob 模式查找文件（递归）。"
        "何时用：查找所有 .py 文件、查找 test_* 文件、定位某配置文件。"
        "何时不用：按内容查找（用 search_content）。"
        "参数约束：root 必须为目录；pattern 为 glob（**/*.py）。"
        "返回格式：每行一个绝对路径。"
    ),
    version="1.0.0",
    timeout=15.0,
    permission_level="read_only",
)
def search_glob(root: str, pattern: str) -> str:
    check_path(root)
    if not Path(root).is_dir():
        return error_json("NotADirectory", f"非目录: {root}")
    hits = [str(p) for p in Path(root).glob(pattern) if p.is_file()]
    return "\n".join(hits) if hits else "无匹配"
