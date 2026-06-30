"""落盘管理：call_id 生成 + .txt + .meta.json 写入 + 老旧清理。

大工具结果（>2000 字符）落盘到 ~/.q-agent/tool-results/{session_id}/{call_id}.txt，
回喂占位符 + 文件路径。
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

RESULTS_DIR = Path.home() / ".q-agent" / "tool-results"
RESULTS_BUDGET = 2000  # 超过此长度触发落盘
MAX_AGE_DAYS = 30


def gen_call_id() -> str:
    """生成 12 位 hex 调用 ID。"""
    return uuid.uuid4().hex[:12]


def spill(
    session_id: str,
    call_id: str,
    tool_name: str,
    output: str,
    input_args: dict[str, object] | None = None,
    duration_ms: int | None = None,
    status: str = "success",
    bytes_written: int | None = None,
) -> Path:
    """落盘工具输出到 .txt + .meta.json，返回 .txt 路径。"""
    session_dir = RESULTS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    txt_path = session_dir / f"{call_id}.txt"
    meta_path = session_dir / f"{call_id}.meta.json"

    txt_path.write_text(output, encoding="utf-8")
    meta = {
        "call_id": call_id,
        "tool_name": tool_name,
        "input_args": input_args or {},
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "duration_ms": duration_ms,
        "status": status,
        "bytes": bytes_written if bytes_written is not None else len(output.encode("utf-8")),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return txt_path


def placeholder(tool_name: str, call_id: str, path: Path) -> str:
    """生成占位回喂字符串（替代完整输出回喂给 LLM）。"""
    return f"[tool:{tool_name} output 已落盘 {path}]"


def cleanup_old(max_age_days: int = MAX_AGE_DAYS) -> int:
    """清理超过 max_age_days 天的落盘文件，返回清理数量。"""
    if not RESULTS_DIR.exists():
        return 0
    cutoff = time.time() - max_age_days * 86400
    count = 0
    for f in RESULTS_DIR.rglob("*.txt"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
            count += 1
    for f in RESULTS_DIR.rglob("*.meta.json"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
    # 清理空目录
    for d in sorted(RESULTS_DIR.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    return count
