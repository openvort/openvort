"""本地适配器 — 纯本地模式，不对接外部系统"""

from openvort.plugins.vortflow.adapters.base import PMAdapter


class LocalAdapter(PMAdapter):
    """纯本地适配器，所有数据只存在 OpenVort DB 中"""

    name = "local"

    async def create_story(self, story: dict) -> str:
        return ""  # 无外部 ID

    async def update_story(self, external_id: str, fields: dict) -> bool:
        return True

    async def create_task(self, task: dict) -> str:
        return ""

    async def update_task(self, external_id: str, fields: dict) -> bool:
        return True

    async def create_bug(self, bug: dict) -> str:
        return ""

    async def update_bug(self, external_id: str, fields: dict) -> bool:
        return True
