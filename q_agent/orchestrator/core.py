"""编排核心：意图 → 技能选择 → 执行。"""

from typing import Any

from q_agent.memory.base import MemoryStore
from q_agent.skills.base import SkillMeta
from q_agent.skills.registry import all_skills, lookup


class Orchestrator:
    """主循环协调器。当前策略为直通匹配，未来交 LLM 做意图识别。"""

    def __init__(self, memory: MemoryStore, llm: Any = None) -> None:
        self.memory = memory
        self.llm = llm

    def handle(self, user_input: str) -> str:
        """处理用户输入：首词匹配技能名，未来交给 LLM 做意图识别。"""
        self.memory.add("user", user_input)
        tokens = user_input.split(maxsplit=1)
        if not tokens:
            reply = ""
            self.memory.add("assistant", reply)
            return reply
        skill_name = tokens[0]
        rest = tokens[1] if len(tokens) > 1 else ""
        meta = lookup(skill_name)
        reply = f"[未注册技能: {skill_name}]" if meta is None else str(meta.fn(rest))
        self.memory.add("assistant", reply)
        return reply

    def list_skills(self) -> list[SkillMeta]:
        """列出所有已注册技能。"""
        return all_skills()
