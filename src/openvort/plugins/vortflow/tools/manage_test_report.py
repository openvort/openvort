"""
测试报告管理工具 -- vortflow_manage_test_report

创建、编辑、删除测试报告，查询报告列表和详情。
报告基于测试计划自动生成快照数据。
"""

import json

from sqlalchemy import func, select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.manage_test_report")


class ManageTestReportTool(BaseTool):
    name = "vortflow_manage_test_report"
    description = (
        "管理 VortFlow 测试报告。"
        "action=create 基于测试计划生成测试报告（自动快照当前执行数据），需提供 plan_id。"
        "action=update 修改报告标题或总结内容。"
        "action=delete 删除报告。"
        "action=list 查询报告列表，可按 plan_id/project_id 过滤。"
        "action=detail 查询报告详情（含完整快照数据）。"
    )
    required_permission = "vortflow.story"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "delete", "list", "detail"],
                    "description": "操作类型",
                },
                "report_id": {"type": "string", "description": "报告 ID（update/delete/detail 时使用）"},
                "plan_id": {"type": "string", "description": "测试计划 ID（create/list 时使用）"},
                "project_id": {"type": "string", "description": "项目 ID（list 时可选过滤）"},
                "title": {"type": "string", "description": "报告标题（create/update 时可选）"},
                "summary": {"type": "string", "description": "报告总结内容（update 时使用）"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        action = params["action"]
        member_id = params.get("_member_id", "")
        sf = self._get_sf()

        if action == "create":
            return await self._create(params, sf, member_id)
        elif action == "update":
            return await self._update(params, sf)
        elif action == "delete":
            return await self._delete(params, sf)
        elif action == "list":
            return await self._list(params, sf)
        elif action == "detail":
            return await self._detail(params, sf)
        return json.dumps({"ok": False, "message": f"未知操作: {action}"})

    async def _create(self, params, sf, member_id):
        from openvort.plugins.vortflow.models import FlowTestPlan, FlowTestReport
        from openvort.plugins.vortflow.router.test_reports import _build_report_snapshot

        plan_id = params.get("plan_id", "")
        if not plan_id:
            return json.dumps({"ok": False, "message": "create 需要 plan_id"})
        async with sf() as session:
            plan = await session.get(FlowTestPlan, plan_id)
            if not plan:
                return json.dumps({"ok": False, "message": "测试计划不存在"})
            snapshot = await _build_report_snapshot(session, plan)
            title = params.get("title") or f"{plan.title}测试报告"
            report = FlowTestReport(
                plan_id=plan.id, project_id=plan.project_id, title=title, summary="",
                snapshot_json=json.dumps(snapshot, ensure_ascii=False, default=str),
                creator_id=member_id or None,
            )
            session.add(report)
            await session.commit()
            await session.refresh(report)
            overview = snapshot.get("overview", {})
        return json.dumps({"ok": True, "message": f"测试报告「{title}」已生成",
                           "report_id": report.id, "overview": {
                "verdict": overview.get("verdict", ""), "total_cases": overview.get("total_cases", 0),
                "pass_rate": overview.get("pass_rate", 0), "total_bugs": overview.get("total_bugs", 0),
            }}, ensure_ascii=False)

    async def _update(self, params, sf):
        from openvort.plugins.vortflow.models import FlowTestReport
        report_id = params.get("report_id", "")
        if not report_id:
            return json.dumps({"ok": False, "message": "update 需要 report_id"})
        async with sf() as session:
            report = await session.get(FlowTestReport, report_id)
            if not report:
                return json.dumps({"ok": False, "message": "报告不存在"})
            changes = {}
            if "title" in params and params["title"] is not None:
                report.title = params["title"]; changes["title"] = params["title"]
            if "summary" in params and params["summary"] is not None:
                report.summary = params["summary"]; changes["summary"] = f"{len(params['summary'])} chars"
            if not changes:
                return json.dumps({"ok": False, "message": "未提供任何修改字段"})
            await session.commit()
        return json.dumps({"ok": True, "message": f"报告「{report.title}」已更新，修改字段: {'、'.join(changes.keys())}"}, ensure_ascii=False)

    async def _delete(self, params, sf):
        from openvort.plugins.vortflow.models import FlowTestReport
        report_id = params.get("report_id", "")
        if not report_id:
            return json.dumps({"ok": False, "message": "delete 需要 report_id"})
        async with sf() as session:
            report = await session.get(FlowTestReport, report_id)
            if not report:
                return json.dumps({"ok": False, "message": "报告不存在"})
            title = report.title
            await session.delete(report)
            await session.commit()
        return json.dumps({"ok": True, "message": f"报告「{title}」已删除"}, ensure_ascii=False)

    async def _list(self, params, sf):
        from openvort.contacts.models import Member
        from openvort.plugins.vortflow.models import FlowTestPlan, FlowTestReport
        async with sf() as session:
            stmt = select(FlowTestReport).order_by(FlowTestReport.created_at.desc()).limit(50)
            if params.get("plan_id"):
                stmt = stmt.where(FlowTestReport.plan_id == params["plan_id"])
            if params.get("project_id"):
                stmt = stmt.where(FlowTestReport.project_id == params["project_id"])
            rows = (await session.execute(stmt)).scalars().all()
            member_ids = {r.creator_id for r in rows if r.creator_id}
            member_map: dict[str, str] = {}
            if member_ids:
                members = (await session.execute(select(Member).where(Member.id.in_(list(member_ids))))).scalars().all()
                member_map = {m.id: m.name for m in members}
            plan_ids = {r.plan_id for r in rows if r.plan_id}
            plan_map: dict[str, str] = {}
            if plan_ids:
                plans = (await session.execute(select(FlowTestPlan).where(FlowTestPlan.id.in_(list(plan_ids))))).scalars().all()
                plan_map = {p.id: p.title for p in plans}
            items = [{"id": r.id, "plan_id": r.plan_id, "plan_title": plan_map.get(r.plan_id, ""),
                      "project_id": r.project_id, "title": r.title,
                      "creator_name": member_map.get(r.creator_id, "") if r.creator_id else "",
                      "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]
        return json.dumps({"ok": True, "count": len(items), "reports": items}, ensure_ascii=False)

    async def _detail(self, params, sf):
        from openvort.contacts.models import Member
        from openvort.plugins.vortflow.models import FlowTestReport
        report_id = params.get("report_id", "")
        if not report_id:
            return json.dumps({"ok": False, "message": "detail 需要 report_id"})
        async with sf() as session:
            report = await session.get(FlowTestReport, report_id)
            if not report:
                return json.dumps({"ok": False, "message": "报告不存在"})
            creator_name = ""
            if report.creator_id:
                m = await session.get(Member, report.creator_id)
                creator_name = m.name if m else ""
            snapshot = json.loads(report.snapshot_json) if report.snapshot_json else {}
        return json.dumps({"ok": True, "report": {
            "id": report.id, "plan_id": report.plan_id, "project_id": report.project_id,
            "title": report.title, "summary": report.summary, "creator_name": creator_name,
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "snapshot": snapshot,
        }}, ensure_ascii=False)
