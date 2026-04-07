"""
report_query — 查询汇报
"""

from datetime import date

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.report.tools.query")


class ReportQueryTool(BaseTool):
    """查询汇报（我的汇报/收到的汇报/详情/统计）"""

    name = "report_query"
    description = (
        "查询汇报。"
        "支持查看自己提交的汇报历史、收到的汇报、汇报详情和统计。"
    )

    def __init__(self, session_factory_getter):
        self._sf_getter = session_factory_getter

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["my_reports", "received_reports", "report_detail", "stats"],
                    "description": "查询类型",
                },
                "member_name": {"type": "string", "description": "成员姓名（用于定位 member_id）"},
                "report_id": {"type": "string", "description": "汇报 ID（详情时需要）"},
                "report_type": {"type": "string", "enum": ["daily", "weekly", "monthly", "quarterly"]},
                "status": {"type": "string", "enum": ["draft", "submitted"]},
                "since": {"type": "string", "description": "起始日期（YYYY-MM-DD）"},
                "until": {"type": "string", "description": "结束日期（YYYY-MM-DD）"},
                "limit": {"type": "integer", "description": "返回数量限制，默认 20"},
            },
            "required": ["query_type"],
        }

    async def execute(self, params: dict) -> str:
        import json
        from openvort.plugins.report.service import ReportService

        query_type = params.get("query_type", "")
        service = ReportService(self._sf_getter())

        if query_type == "my_reports":
            result = await self._my_reports(service, params)
        elif query_type == "received_reports":
            result = await self._received_reports(service, params)
        elif query_type == "report_detail":
            result = await self._report_detail(service, params)
        elif query_type == "stats":
            result = await self._stats(service, params)
        else:
            result = {"ok": False, "error": f"未知查询类型: {query_type}"}
        return json.dumps(result, ensure_ascii=False, default=str)

    async def _my_reports(self, service, kwargs: dict) -> dict:
        member_name = kwargs.get("member_name", "")
        member_id = await self._resolve_member_id(member_name) if member_name else ""
        reports = await service.list_reports(
            reporter_id=member_id or None,
            report_type=kwargs.get("report_type"),
            status=kwargs.get("status"),
            since=date.fromisoformat(kwargs["since"]) if kwargs.get("since") else None,
            until=date.fromisoformat(kwargs["until"]) if kwargs.get("until") else None,
            limit=kwargs.get("limit", 20),
        )
        return {"ok": True, "reports": reports, "count": len(reports)}

    async def _received_reports(self, service, kwargs: dict) -> dict:
        member_name = kwargs.get("member_name", "")
        member_id = await self._resolve_member_id(member_name) if member_name else ""
        if not member_id:
            return {"ok": False, "error": "需要 member_name"}
        reports = await service.list_received_reports(
            member_id,
            report_type=kwargs.get("report_type"),
            since=date.fromisoformat(kwargs["since"]) if kwargs.get("since") else None,
            until=date.fromisoformat(kwargs["until"]) if kwargs.get("until") else None,
            limit=kwargs.get("limit", 20),
        )
        return {"ok": True, "reports": reports, "count": len(reports)}

    async def _report_detail(self, service, kwargs: dict) -> dict:
        report_id = kwargs.get("report_id", "")
        if not report_id:
            return {"ok": False, "error": "需要 report_id"}
        report = await service.get_report(report_id)
        if not report:
            return {"ok": False, "error": "汇报不存在"}
        return {"ok": True, "report": report}

    async def _stats(self, service, kwargs: dict) -> dict:
        member_name = kwargs.get("member_name", "")
        member_id = await self._resolve_member_id(member_name) if member_name else ""
        stats = await service.get_report_stats(
            reporter_id=member_id or None,
            since=date.fromisoformat(kwargs["since"]) if kwargs.get("since") else None,
            until=date.fromisoformat(kwargs["until"]) if kwargs.get("until") else None,
        )
        return {"ok": True, "stats": stats}

    async def _resolve_member_id(self, name: str) -> str:
        from sqlalchemy import select
        from openvort.contacts.models import Member
        async with self._sf_getter()() as session:
            stmt = select(Member).where(Member.name == name).limit(1)
            result = await session.execute(stmt)
            member = result.scalar_one_or_none()
            return member.id if member else ""
