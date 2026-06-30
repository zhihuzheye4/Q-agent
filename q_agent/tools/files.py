"""文件操作工具：file_read / file_write / file_edit / file_list_dir / file_move。

5 工具按域聚集。写操作（file_write/file_edit/file_move）集成：
- safety.check_path（项目根保护）
- safety.check_sensitive（敏感文件拦截）
- safety.sniff_secret_content（写入内容嗅探）
- undo.snapshot_before_write/move（写前快照备份）
"""

from pathlib import Path

from q_agent.tools._helpers import error_json
from q_agent.tools.registry import tool
from q_agent.tools.safety import check_path, check_sensitive, sniff_secret_content
from q_agent.tools.undo import snapshot_before_move, snapshot_before_write


@tool(
    name="file_read",
    desc=(
        "读取文本文件内容并返回字符串。"
        "何时用：需要查看源代码、配置文件、文档内容时。"
        "何时不用：读取二进制文件（图片/音频/可执行）、读取超过 1MB 的大文件、读取敏感凭证文件。"
        "参数约束：path 必须为绝对路径或相对 cwd 的路径；命中敏感清单返回 PermissionError。"
        "返回格式：文件全文（超 2000 字符触发预算降级）。"
    ),
    version="1.0.0",
    timeout=15.0,
    permission_level="read_only",
)
def file_read(path: str, encoding: str = "utf-8") -> str:
    check_path(path)
    check_sensitive(path)
    p = Path(path)
    if not p.exists():
        return error_json("FileNotFound", f"文件不存在: {path}")
    if p.stat().st_size > 1_000_000:
        return error_json("FileTooLarge", f"文件超过 1MB: {p.stat().st_size} bytes")
    return p.read_text(encoding=encoding)


@tool(
    name="file_write",
    desc=(
        "将字符串内容写入文件（覆盖模式）。"
        "何时用：创建新文件、修改源代码、生成配置文件。"
        "何时不用：追加内容（v0.0.20 再加 file_append）、写二进制、"
        "精确替换既有内容（用 file_edit）。"
        "参数约束：path + content；命中敏感文件或内容含 PRIVATE KEY/AKIA 模式拒绝。"
        "返回格式：写入字节数 + 落盘备份路径。"
    ),
    version="1.0.0",
    timeout=10.0,
    permission_level="write",
)
def file_write(path: str, content: str, encoding: str = "utf-8") -> str:
    check_path(path)
    check_sensitive(path)
    sniff_secret_content(content)
    backup = snapshot_before_write(path)
    Path(path).write_text(content, encoding=encoding)
    return f"写入 {len(content.encode(encoding))} bytes; backup={backup}"


@tool(
    name="file_edit",
    desc=(
        "在既有文件中做精确字符串替换（首次匹配替换）。"
        "何时用：修改源代码中某个函数 / 改配置文件某行 / 重命名变量。"
        "何时不用：全覆盖写（用 file_write）、追加内容、批量同字符串替换。"
        "参数约束：path + old_string + new_string；old_string 必须唯一出现，"
        "否则返回 AmbiguousMatch。"
        "返回格式：替换成功字节数 + 落盘快照路径 + 命中行号。"
    ),
    version="1.0.0",
    timeout=10.0,
    permission_level="write",
)
def file_edit(path: str, old_string: str, new_string: str, encoding: str = "utf-8") -> str:
    if old_string == "":
        return error_json("EmptyOldString", "old_string 不能为空")
    if old_string == new_string:
        return error_json("NoOp", "old_string 与 new_string 相同，无需替换")
    check_path(path)
    check_sensitive(path)
    sniff_secret_content(new_string)
    p = Path(path)
    if not p.exists():
        return error_json("FileNotFound", f"文件不存在: {path}")
    content = p.read_text(encoding=encoding)
    occurrences = content.count(old_string)
    if occurrences == 0:
        return error_json("StringNotFound", "old_string 未在文件中找到")
    if occurrences > 1:
        return error_json(
            "AmbiguousMatch",
            f"old_string 在文件中出现 {occurrences} 次，需提供更多上下文行",
        )
    backup = snapshot_before_write(path)
    new_content = content.replace(old_string, new_string, 1)
    p.write_text(new_content, encoding=encoding)
    hit_line = content[: content.index(old_string)].count("\n") + 1
    return f"替换 1 处; hit_line={hit_line}; backup={backup}"


@tool(
    name="file_list_dir",
    desc=(
        "列出目录下的文件与子目录（不递归）。"
        "何时用：浏览项目结构、查找某目录下文件清单。"
        "何时不用：递归查找（用 search_glob）、读取文件内容（用 file_read）。"
        "参数约束：path 必须存在且为目录。"
        "返回格式：每行一项，目录后缀 /，文件后缀无。"
    ),
    version="1.0.0",
    timeout=15.0,
    permission_level="read_only",
)
def file_list_dir(path: str) -> str:
    check_path(path)
    p = Path(path)
    if not p.is_dir():
        return error_json("NotADirectory", f"非目录: {path}")
    lines = []
    for child in sorted(p.iterdir()):
        lines.append(f"{child.name}/" if child.is_dir() else child.name)
    return "\n".join(lines)


@tool(
    name="file_move",
    desc=(
        "移动或重命名文件/目录。"
        "何时用：重构时改名、整理文件位置。"
        "何时不用：跨盘符移动大目录（用 copy+delete）、删除文件（v0.0.20 再加 file_delete）。"
        "参数约束：src 必须存在，dst 父目录必须存在；命中受保护根拒绝。"
        "返回格式：移动成功字节数 + 落盘快照。"
    ),
    version="1.0.0",
    timeout=10.0,
    permission_level="destructive",
)
def file_move(src: str, dst: str) -> str:
    check_path(src)
    check_path(dst)
    check_sensitive(src)
    check_sensitive(dst)
    import shutil

    src_path = Path(src)
    if not src_path.exists():
        return error_json("FileNotFound", f"源文件不存在: {src}")
    backup = snapshot_before_move(src, dst)
    size = src_path.stat().st_size
    shutil.move(str(src_path), dst)
    return f"moved {src} -> {dst}; size={size} bytes; backup={backup}"
