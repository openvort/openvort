"""PM 适配器抽象接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChangeEvent:
    """外部系统变更事件"""

    entity_type: str  # story/task/bug
    external_id: str
    action: str  # created/updated/deleted/state_changed
    fields: dict = field(default_factory=dict)
    timestamp: datetime | None = None


class PMAdapter(ABC):
    """项目管理工具适配器基类"""

    name: str = ""

    @abstractmethod
    async def create_story(self, story: dict) -> str:
        """创建需求，返回 external_id"""
        ...

    @abstractmethod
    async def update_story(self, external_id: str, fields: dict) -> bool:
        ...

    @abstractmethod
    async def create_task(self, task: dict) -> str:
        ...

    @abstractmethod
    async def update_task(self, external_id: str, fields: dict) -> bool:
        ...

    @abstractmethod
    async def create_bug(self, bug: dict) -> str:
        ...

    @abstractmethod
    async def update_bug(self, external_id: str, fields: dict) -> bool:
        ...

    async def fetch_changes(self, since_cursor: str) -> list[ChangeEvent]:
        """拉取增量变更（可选，LocalAdapter 不需要）"""
        return []

    async def resolve_conflict(self, local: dict, remote: dict, strategy: str = "remote_wins") -> dict:
        """解决冲突（可选）"""
        return remote if strategy == "remote_wins" else local
