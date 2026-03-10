"""
群聊上下文管理

管理群聊与项目的关联关系，为群聊会话构建项目上下文 prompt。
"""

import json
from datetime import datetime

from sqlalchemy import select, text

from openvort.db.engine import get_session_factory
from openvort.db.models import GroupChat
from openvort.utils.logging import get_logger

log = get_logger("core.group_context")


class GroupContextManager:
    """Group chat context manager — CRUD and prompt building."""

    async def get_or_create(self, chat_id: str, platform: str) -> GroupChat:
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(
                select(GroupChat).where(GroupChat.chat_id == chat_id)
            )
            group = result.scalar_one_or_none()
            if group:
                return group

            group = GroupChat(chat_id=chat_id, platform=platform)
            session.add(group)
            await session.commit()
            await session.refresh(group)
            log.info(f"新建群聊记录: chat_id={chat_id}, platform={platform}")
            return group

    async def get_by_chat_id(self, chat_id: str) -> GroupChat | None:
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(
                select(GroupChat).where(GroupChat.chat_id == chat_id)
            )
            return result.scalar_one_or_none()

    async def bind_project(self, chat_id: str, project_id: str, member_id: str = "") -> dict:
        """Bind a group chat to a VortFlow project. Returns status dict."""
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(
                select(GroupChat).where(GroupChat.chat_id == chat_id)
            )
            group = result.scalar_one_or_none()
            if not group:
                return {"ok": False, "message": "群聊记录不存在"}

            proj_row = await session.execute(
                text("SELECT id, name FROM flow_projects WHERE id = :pid"),
                {"pid": project_id},
            )
            proj = proj_row.mappings().first()
            if not proj:
                return {"ok": False, "message": f"项目 {project_id} 不存在"}

            group.project_id = project_id
            group.bound_by = member_id or None
            group.bound_at = datetime.now()
            await session.commit()

            project_name = proj["name"]
            log.info(f"群聊 {chat_id} 已绑定项目: {project_name} ({project_id})")
            return {"ok": True, "message": f"已将此群关联到项目「{project_name}」", "project_name": project_name}

    async def unbind_project(self, chat_id: str) -> dict:
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(
                select(GroupChat).where(GroupChat.chat_id == chat_id)
            )
            group = result.scalar_one_or_none()
            if not group:
                return {"ok": False, "message": "群聊记录不存在"}
            if not group.project_id:
                return {"ok": False, "message": "此群未关联任何项目"}

            group.project_id = None
            group.bound_by = None
            group.bound_at = None
            await session.commit()

            log.info(f"群聊 {chat_id} 已解绑项目")
            return {"ok": True, "message": "已解除此群的项目关联"}

    async def update_name(self, chat_id: str, name: str) -> dict:
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(
                select(GroupChat).where(GroupChat.chat_id == chat_id)
            )
            group = result.scalar_one_or_none()
            if not group:
                return {"ok": False, "message": "群聊记录不存在"}

            group.name = name
            await session.commit()
            return {"ok": True, "message": f"群名已更新为「{name}」"}

    async def build_group_prompt(self, chat_id: str) -> str:
        """Build the system prompt fragment for a group chat session."""
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(
                select(GroupChat).where(GroupChat.chat_id == chat_id)
            )
            group = result.scalar_one_or_none()
            if not group:
                return ""

            if group.project_id:
                return await self._build_bound_prompt(session, group)
            else:
                return self._build_unbound_prompt(group)

    async def _build_bound_prompt(self, session, group: GroupChat) -> str:
        proj_row = await session.execute(
            text("SELECT name, description FROM flow_projects WHERE id = :pid"),
            {"pid": group.project_id},
        )
        proj = proj_row.mappings().first()
        if not proj:
            return self._build_unbound_prompt(group)

        name_line = f"群名: {group.name}\n" if group.name else ""
        desc_line = f"项目描述: {proj['description']}\n" if proj["description"] else ""

        return (
            f"# 群聊上下文\n"
            f"当前对话发生在一个 IM 群聊中（群聊ID: {group.chat_id}）。\n"
            f"{name_line}"
            f"已关联项目: {proj['name']} (ID: {group.project_id})\n"
            f"{desc_line}\n"
            f"所有操作默认在此项目上下文中。查询需求/任务/缺陷时自动使用此项目 ID。\n"
            f"如需更换关联项目，可使用 group_bind_project 工具。"
        )

    @staticmethod
    def _build_unbound_prompt(group: GroupChat) -> str:
        name_line = f"群名: {group.name}\n" if group.name else ""

        return (
            f"# 群聊上下文\n"
            f"当前对话发生在一个 IM 群聊中（群聊ID: {group.chat_id}）。\n"
            f"{name_line}"
            f"此群尚未关联任何项目。\n\n"
            f"请在合适的时机（如用户首次提问或涉及项目相关话题时）：\n"
            f"1. 使用 vortflow_query 查询现有项目列表\n"
            f"2. 根据对话内容推测可能关联的项目\n"
            f"3. 如果能确定，使用 group_bind_project 工具完成绑定并告知群成员\n"
            f"4. 如果无法确定，主动询问群成员此群对应哪个项目"
        )


group_context_manager = GroupContextManager()
