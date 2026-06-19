"""Planner stub：未来由本地 LLM 做意图识别与技能规划。"""

from typing import Any


class Planner:
    """规划器占位。当前返回空序列，由 orchestrator 直通处理。"""

    def __init__(self, llm: Any = None) -> None:
        self.llm = llm

    def plan(self, user_input: str) -> list[str]:
        """返回技能调用序列。"""
        return []
