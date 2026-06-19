"""最小 in-memory 实现：环形对话缓冲，能跑通最小循环。"""

from collections import deque

from q_agent.memory.base import MemoryStore


class RuntimeMemory(MemoryStore):
    """进程内对话缓冲，容量上限后自动丢弃最旧条目。"""

    def __init__(self, capacity: int = 100) -> None:
        self._buf: deque[dict[str, str]] = deque(maxlen=capacity)

    def add(self, role: str, content: str) -> None:
        self._buf.append({"role": role, "content": content})

    def recent(self, n: int = 10) -> list[dict[str, str]]:
        return list(self._buf)[-n:]
