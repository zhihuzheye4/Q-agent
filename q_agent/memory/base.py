"""运行期记忆抽象基类。与 memory/ 文件层（协作记忆）物理隔离。"""

from abc import ABC, abstractmethod


class MemoryStore(ABC):
    """运行期记忆接口。"""

    @abstractmethod
    def add(self, role: str, content: str) -> None:
        """追加一条消息。"""

    @abstractmethod
    def recent(self, n: int = 10) -> list[dict[str, str]]:
        """返回最近 n 条消息。"""
