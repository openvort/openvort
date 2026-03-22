"""
report_query — 查询汇报
"""

from datetime import date

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.report.tools.query")


class ReportQueryTool(BaseTool):
    """查询汇报（我的汇报/下属汇报/团队汇总）"""

    name = "report_query"
    description = (
        "查询汇报。"
        "支持查看自己提交的汇报历史、下属提交的汇报、汇报详情。"
        "管理者可以审阅汇报并添加批注。"
    )

    def __init__(self, session_factory_getter):
        self._sf_getter = session_factory_getter

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["my_reports", "subordinate_reports", "report_detail", "review", "stats", "team_summary"],
                    "description": (
                        "查询类型："
                        "my_reports 查看我的汇报，"
                        "subordinate_reports 查看下属汇报，"
                        "report_detail 查看单个汇报详情，"
                        "review 审阅汇报（添加批注），"
                        "stats 汇报统计，"
                        "team_summary 聚合多份下属汇报为管理层摘要"
                    ),
                },
                "member_name": {"type": "string", "description": "成员姓名（用于定位 member_id）"},
                "report_id": {"type": "string", "description": "汇报 ID（详情/审阅时需要）"},
                "report_type": {
                    "type": "string", "enum": ["daily", "weekly", "monthly", "quarterly"],
                    "description": "按类型筛选",
                },
                "status": {
                    "type": "string", "enum": ["draft", "submitted", "reviewed", "rejected"],
                    "description": "按状态筛选",
                },
                "since": {"type": "string", "description": "起始日期（YYYY-MM-DD）"},
                "until": {"type": "string", "description": "结束日期（YYYY-MM-DD）"},
                "review_status": {
                    "type": "string", "enum": ["reviewed", "rejected"],
                    "description": "审阅结果（review 时需要）",
                },
                "comment": {"type": "string", "description": "审阅批注（review 时需要）"},
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
        elif query_type == "subordinate_reports":
            result = await self._subordinate_reports(service, params)
        elif query_type == "report_detail":
            result = await self._report_detail(service, params)
        elif query_type == "review":
            result = await self._review(service, params)
        elif query_type == "stats":
            result = await self._stats(service, params)
        elif query_type == "team_summary":
            result = await self._team_summary(service, params)
        else:
            result = {"ok": False, "error": f"未知查询类型: {query_type}"}
        return json.dumps(result, ensure_ascii=False, default=str)

    async def _my_reports(self, service, kwargs: dict) -> dict:
        member_name = kwargs.get("member_name", "")
        member_id = await self._resolve_member_id(member_name) if member_name else ""

        since = date.fromisoformat(kwargs["since"]) if kwargs.get("since") else None
        until = date.fromisoformat(kwargs["until"]) if kwargs.get("until") else None

        reports = await service.list_reports(
            reporter_id=member_id or None,
            report_type=kwargs.get("report_type"),
            status=kwargs.get("status"),
            since=since,
            until=until,
            limit=kwargs.get("limit", 20),
        )
        return {"ok": True, "reports": reports, "count": len(reports)}

    async def _subordinate_reports(self, service, kwargs: dict) -> dict:
        member_name = kwargs.get("member_name", "")
        member_id = await self._resolve_member_id(member_name) if member_name else ""

        since = date.fromisoformat(kwargs["since"]) if kwargs.get("since") else None
        until = date.fromisoformat(kwargs["until"]) if kwargs.get("until") else None

        reports = await service.list_reports(
            reviewer_id=member_id or None,
            report_type=kwargs.get("report_type"),
            status=kwargs.get("status"),
            since=since,
            until=until,
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

        # Resolve names
        reporter_name = await self._resolve_member_name(report["reporter_id"])
        reviewer_name = await self._resolve_member_name(report["reviewer_id"]) if report["reviewer_id"] else ""
        report["reporter_name"] = reporter_name
        report["reviewer_name"] = reviewer_name

        return {"ok": True, "report": report}

    async def _review(self, service, kwargs: dict) -> dict:
        report_id = kwargs.get("report_id", "")
        review_status = kwargs.get("review_status", "reviewed")
        comment = kwargs.get("comment", "")

        if not report_id:
            return {"ok": False, "error": "需要 report_id"}
        if review_status not in ("reviewed", "rejected"):
            return {"ok": False, "error": "review_status 必须是 reviewed 或 rejected"}

        result = await service.update_report(
            report_id,
            status=review_status,
            reviewer_comment=comment,
        )
        if not result:
            return {"ok": False, "error": "汇报不存在"}

        action_label = "通过" if review_status == "reviewed" else "退回"
        return {"ok": True, "report": result, "message": f"汇报已{action_label}"}

    async def _stats(self, service, kwargs: dict) -> dict:
        member_name = kwargs.get("member_name", "")
        member_id = await self._resolve_member_id(member_name) if member_name else ""

        since = date.fromisoformat(kwargs["since"]) if kwargs.get("since") else None
        until = date.fromisoformat(kwargs["until"]) if kwargs.get("until") else None

        stats = await service.get_report_stats(
            reviewer_id=member_id or None,
            since=since,
            until=until,
        )
        return {"ok": True, "stats": stats}

    async def _team_summary(self, service, kwargs: dict) -> dict:
        """聚合多份下属汇报，生成管理层摘要"""
        member_name = kwargs.get("member_name", "")
        member_id = await self._resolve_member_id(member_name) if member_name else ""

        since = date.fromisoformat(kwargs["since"]) if kwargs.get("since") else None
        until = date.fromisoformat(kwargs["until"]) if kwargs.get("until") else None

        # Get subordinate reports
        reports = await service.list_reports(
            reviewer_id=member_id or None,
            status="submitted",
            since=since,
            until=until,
            limit=50,
        )

        if not reports:
            return {"ok": True, "summary": "暂无下属汇报可聚合", "reports_count": 0}

        # Build aggregated summary data for AI to further process
        reporters: dict[str, list[str]] = {}
        blockers: list[str] = []
        highlights: list[str] = []

        for r in reports:
            reporter_name = await self._resolve_member_name(r["reporter_id"])
            reporter_key = reporter_name or r["reporter_id"][:8]
            if reporter_key not in reporters:
                reporters[reporter_key] = []
            reporters[reporter_key].append(r.get("title", "无标题"))

            content = r.get("content", "").lower()
            if any(kw in content for kw in ["阻塞", "blocked", "问题", "风险", "延期"]):
                blockers.append(f"{reporter_key}: {r.get('title', '')}")

        summary_parts = []
        summary_parts.append(f"共收到 {len(reports)} 份汇报，来自 {len(reporters)} 位下属。\n")

        summary_parts.append("### 各成员汇报")
        for name, titles in reporters.items():
            summary_parts.append(f"- **{name}**: {len(titles)} 份 — {', '.join(titles[:3])}")

        if blockers:
            summary_parts.append("\n### 需要关注（含阻塞/风险关键词）")
            for b in blockers:
                summary_parts.append(f"- {b}")

        summary_parts.append(
            "\n（以上为自动聚合摘要，你可以让 AI 进一步分析每份汇报的具体内容，"
            "标注优先级和需要决策的事项。）"
        )

        return {
            "ok": True,
            "summary": "\n".join(summary_parts),
            "reports_count": len(reports),
            "reporters_count": len(reporters),
            "blockers_count": len(blockers),
            "reports": reports,
        }

    async def _resolve_member_id(self, name: str) -> str:
        from sqlalchemy import select
        from openvort.contacts.models import Member

        async with self._sf_getter()() as session:
            stmt = select(Member).where(Member.name == name).limit(1)
            result = await session.execute(stmt)
            member = result.scalar_one_or_none()
            return member.id if member else ""

    async def _resolve_member_name(self, member_id: str) -> str:
        if not member_id:
            return ""
        from sqlalchemy import select
        from openvort.contacts.models import Member

        async with self._sf_getter()() as session:
            stmt = select(Member).where(Member.id == member_id).limit(1)
            result = await session.execute(stmt)
            member = result.scalar_one_or_none()
            return member.name if member else ""
