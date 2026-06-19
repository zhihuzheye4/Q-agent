"""
Q-agent 思维导图渲染脚本

输入：memory/思维导图数据.jsonl  （L1 append-only 数据源）
输出：memory/思维导图.md          （脚本生成，AI 不直接 Edit）

调用方式：
    python scripts/update_mindmap.py

jsonl 每行一个事件，支持两种 action：
    {"action":"add","time":"YYYY-MM-DD","name":"功能名","tech":"技术路线","idea":"技术思路"}
    {"action":"del","time":"YYYY-MM-DD","name":"功能名","reason":"删除原因"}

双线制渲染：
- 主线：当前存活的功能块，按添加时间正序串联
- 支线：已删除的功能块，向下延伸，可不连续，每块附删除原因
"""

import json
from collections import OrderedDict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "memory" / "思维导图数据.jsonl"
OUT = BASE / "memory" / "思维导图.md"

HEADER = """<!-- 权限：L3 完全权限（由脚本生成，AI 不直接 Edit）
     数据源：memory/思维导图数据.jsonl  （L1 append-only）
     重新渲染：python scripts/update_mindmap.py
     AI 操作：追加 jsonl 一行事件 → 调脚本 → md 自动更新
-->

# Q-agent 思维导图（双线制）

> 主线 = 当前存活功能（按添加时间正序）
> 支线 = 已删除功能（向下延伸，可不连续，附删除原因）

"""


def load_events():
    if not SRC.exists():
        return []
    events = []
    with SRC.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[警告] 第 {line_no} 行解析失败：{e}，已跳过")
    return events


def build_state(events):
    """根据事件序列构建当前状态：name -> {state: alive/dead, add_meta, del_meta}"""
    state = OrderedDict()
    for ev in events:
        action = ev.get("action")
        name = ev.get("name", "")
        if action == "add":
            state[name] = {
                "state": "alive",
                "add": ev,
                "del": None,
            }
        elif action == "del":
            if name in state:
                state[name]["state"] = "dead"
                state[name]["del"] = ev
            else:
                # 删除一个未注册的功能，仍记录
                state[name] = {
                    "state": "dead",
                    "add": None,
                    "del": ev,
                }
    return state


def render(state):
    lines = [HEADER]
    alive = [(n, v) for n, v in state.items() if v["state"] == "alive"]
    dead = [(n, v) for n, v in state.items() if v["state"] == "dead"]

    lines.append("## 主线（当前存活功能）\n")
    if not alive:
        lines.append("（暂无存活功能）\n")
    else:
        for name, v in alive:
            add = v["add"] or {}
            t = add.get("time", "?")
            tech = add.get("tech", "?")
            idea = add.get("idea", "?")
            lines.append(f"- [{t} 新增] {name}")
            lines.append(f"  - 技术路线：{tech}")
            lines.append(f"  - 技术思路：{idea}")
            lines.append("")

    lines.append("## 支线（已删除功能，向下延伸，可不连续）\n")
    if not dead:
        lines.append("（暂无删除记录）\n")
    else:
        for name, v in dead:
            add = v["add"] or {}
            del_ = v["del"] or {}
            add_t = add.get("time", "?")
            del_t = del_.get("time", "?")
            tech = add.get("tech", "?")
            idea = add.get("idea", "?")
            reason = del_.get("reason", "?")
            lines.append(f"- [{add_t} 新增 → {del_t} 删除] {name}")
            lines.append(f"  - 技术路线：{tech}")
            lines.append(f"  - 技术思路：{idea}")
            lines.append(f"  - 删除原因：{reason}")
            lines.append("")

    return "\n".join(lines) + "\n"


def main():
    events = load_events()
    state = build_state(events)
    md = render(state)
    OUT.write_text(md, encoding="utf-8")
    alive_count = sum(1 for v in state.values() if v["state"] == "alive")
    dead_count = sum(1 for v in state.values() if v["state"] == "dead")
    print(f"[完成] 已渲染 {OUT}")
    print(f"  存活功能：{alive_count}")
    print(f"  已删除功能：{dead_count}")
    print(f"  总事件数：{len(events)}")


if __name__ == "__main__":
    main()
