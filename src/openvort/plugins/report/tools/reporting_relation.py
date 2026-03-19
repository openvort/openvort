"""
reporting_relation — manage reporting relationships (who reports to whom)
"""

import json

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.report.tools.reporting_relation")


class ReportingRelationTool(BaseTool):
    """管理汇报关系（谁向谁汇报）"""

    name = "reporting_relation"
    description = (
        "管理成员之间的汇报关系。"
        "可以创建、删除、查询汇报关系，以及查看某人的下属或上级。"
        "汇报关系类型：direct（直属）、dotted（虚线）、functional（职能）。"
    )

    def __init__(self, session_factory_getter):
        self._sf_getter = session_factory_getter

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "delete", "list", "subordinates", "supervisors"],
                    "description": (
                        "操作类型："
                        "create 创建汇报关系，"
                        "delete 删除汇报关系，"
                        "list 列出所有汇报关系，"
                        "subordinates 查看某人的下属，"
                        "supervisors 查看某人的上级"
                    ),
                },
                "reporter_name": {
                    "type": "string",
                    "description": "汇报人（下级）姓名，create 时必填",
                },
                "supervisor_name": {
                    "type": "string",
                    "description": "上级姓名，create 时必填",
                },
                "relation_type": {
                    "type": "string",
                    "enum": ["direct", "dotted", "functional"],
                    "description": "关系类型：direct 直属（默认）、dotted 虚线、functional 职能",
                },
                "relation_id": {
                    "type": "integer",
                    "description": "汇报关系 ID，delete 时需要",
                },
                "member_name": {
                    "type": "string",
                    "description": "成员姓名，查询 subordinates/supervisors 时使用",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        action = params.get("action", "")

        if action == "create":
            result = await self._create(params)
        elif action == "delete":
            result = await self._delete(params)
        elif action == "list":
            result = await self._list(params)
        elif action == "subordinates":
            result = await self._get_subordinates(params)
        elif action == "supervisors":
            result = await self._get_supervisors(params)
        else:
            result = {"ok": False, "error": f"未知操作: {action}"}

        return json.dumps(result, ensure_ascii=False, default=str)

    async def _resolve_member(self, name: str) -> tuple[str, str]:
        """Resolve member name to (id, name). Returns ("", "") if not found."""
        from sqlalchemy import select
        from openvort.contacts.models import Member

        async with self._sf_getter()() as session:
            stmt = select(Member).where(Member.name == name).limit(1)
            result = await session.execute(stmt)
            member = result.scalar_one_or_none()
            if member:
                return member.id, member.name
        return "", ""

    async def _create(self, params: dict) -> dict:
        from openvort.contacts.models import ReportingRelation

        reporter_name = params.get("reporter_name", "")
        supervisor_name = params.get("supervisor_name", "")
        relation_type = params.get("relation_type", "direct")

        if not reporter_name or not supervisor_name:
            return {"ok": False, "error": "需要提供汇报人和上级的姓名"}

        reporter_id, r_name = await self._resolve_member(reporter_name)
        if not reporter_id:
            return {"ok": False, "error": f"未找到成员: {reporter_name}"}

        supervisor_id, s_name = await self._resolve_member(supervisor_name)
        if not supervisor_id:
            return {"ok": False, "error": f"未找到成员: {supervisor_name}"}

        if reporter_id == supervisor_id:
            return {"ok": False, "error": "不能向自己汇报"}

        async with self._sf_getter()() as session:
            rel = ReportingRelation(
                reporter_id=reporter_id,
                supervisor_id=supervisor_id,
                relation_type=relation_type,
                is_primary=True,
            )
            session.add(rel)
            try:
                await session.commit()
                await session.refresh(rel)
                return {
                    "ok": True,
                    "message": f"已创建汇报关系: {r_name} → {s_name} ({relation_type})",
                    "relation": {
                        "id": rel.id,
                        "reporter": r_name,
                        "supervisor": s_name,
                        "type": relation_type,
                    },
                }
            except Exception:
                await session.rollback()
                return {"ok": False, "error": "汇报关系已存在或数据无效"}

    async def _delete(self, params: dict) -> dict:
        from sqlalchemy import delete
        from openvort.contacts.models import ReportingRelation

        relation_id = params.get("relation_id")
        if not relation_id:
            return {"ok": False, "error": "需要 relation_id"}

        async with self._sf_getter()() as session:
            stmt = delete(ReportingRelation).where(ReportingRelation.id == relation_id)
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount > 0:
                return {"ok": True, "message": "汇报关系已删除"}
            return {"ok": False, "error": "汇报关系不存在"}

    async def _list(self, params: dict) -> dict:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from openvort.contacts.models import ReportingRelation

        async with self._sf_getter()() as session:
            stmt = (
                select(ReportingRelation)
                .options(
                    selectinload(ReportingRelation.reporter),
                    selectinload(ReportingRelation.supervisor),
                )
                .order_by(ReportingRelation.created_at.desc())
            )
            result = await session.execute(stmt)
            relations = result.scalars().all()

            type_labels = {"direct": "直属", "dotted": "虚线", "functional": "职能"}
            items = []
            for r in relations:
                items.append({
                    "id": r.id,
                    "reporter": r.reporter.name if r.reporter else r.reporter_id,
                    "supervisor": r.supervisor.name if r.supervisor else r.supervisor_id,
                    "type": type_labels.get(r.relation_type, r.relation_type),
                    "is_primary": r.is_primary,
                })

            return {"ok": True, "relations": items, "count": len(items)}

    async def _get_subordinates(self, params: dict) -> dict:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from openvort.contacts.models import ReportingRelation

        member_name = params.get("member_name", "")
        if not member_name:
            return {"ok": False, "error": "需要 member_name"}

        member_id, _ = await self._resolve_member(member_name)
        if not member_id:
            return {"ok": False, "error": f"未找到成员: {member_name}"}

        async with self._sf_getter()() as session:
            stmt = (
                select(ReportingRelation)
                .options(selectinload(ReportingRelation.reporter))
                .where(ReportingRelation.supervisor_id == member_id)
            )
            result = await session.execute(stmt)
            relations = result.scalars().all()

            subordinates = [
                {
                    "name": r.reporter.name if r.reporter else r.reporter_id,
                    "relation_type": r.relation_type,
                    "is_primary": r.is_primary,
                }
                for r in relations
            ]
            return {"ok": True, "subordinates": subordinates, "count": len(subordinates)}

    async def _get_supervisors(self, params: dict) -> dict:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from openvort.contacts.models import ReportingRelation

        member_name = params.get("member_name", "")
        if not member_name:
            return {"ok": False, "error": "需要 member_name"}

        member_id, _ = await self._resolve_member(member_name)
        if not member_id:
            return {"ok": False, "error": f"未找到成员: {member_name}"}

        async with self._sf_getter()() as session:
            stmt = (
                select(ReportingRelation)
                .options(selectinload(ReportingRelation.supervisor))
                .where(ReportingRelation.reporter_id == member_id)
            )
            result = await session.execute(stmt)
            relations = result.scalars().all()

            supervisors = [
                {
                    "name": r.supervisor.name if r.supervisor else r.supervisor_id,
                    "relation_type": r.relation_type,
                    "is_primary": r.is_primary,
                }
                for r in relations
            ]
            return {"ok": True, "supervisors": supervisors, "count": len(supervisors)}
