"""
汇报业务层

模板/规则/汇报实例的 CRUD + 汇报生成 + 分发逻辑。
"""

import json
from datetime import date, datetime

from sqlalchemy import select, delete, func as sa_func
from sqlalchemy.orm import selectinload

from openvort.plugins.report.models import Report, ReportRule, ReportTemplate
from openvort.utils.logging import get_logger

log = get_logger("plugins.report.service")


class ReportService:
    """汇报管理服务"""

    def __init__(self, session_factory):
        self._sf = session_factory

    # ---- Template CRUD ----

    async def create_template(
        self,
        name: str,
        report_type: str,
        content_schema: dict | None = None,
        auto_collect: dict | None = None,
        owner_id: str | None = None,
    ) -> dict:
        tmpl = ReportTemplate(
            name=name,
            report_type=report_type,
            content_schema=json.dumps(content_schema or {}),
            auto_collect=json.dumps(auto_collect or {"git": True, "vortflow": True}),
            owner_id=owner_id,
        )
        async with self._sf() as session:
            session.add(tmpl)
            await session.commit()
            await session.refresh(tmpl)
        log.info(f"创建模板: {tmpl.id[:8]} ({name})")
        return self._template_to_dict(tmpl)

    async def update_template(self, template_id: str, **fields) -> dict | None:
        async with self._sf() as session:
            stmt = select(ReportTemplate).where(ReportTemplate.id == template_id)
            result = await session.execute(stmt)
            tmpl = result.scalar_one_or_none()
            if not tmpl:
                return None

            for key in ("name", "report_type", "owner_id"):
                if key in fields:
                    setattr(tmpl, key, fields[key])
            if "content_schema" in fields:
                tmpl.content_schema = json.dumps(fields["content_schema"])
            if "auto_collect" in fields:
                tmpl.auto_collect = json.dumps(fields["auto_collect"])

            await session.commit()
            await session.refresh(tmpl)
        return self._template_to_dict(tmpl)

    async def delete_template(self, template_id: str) -> bool:
        async with self._sf() as session:
            stmt = delete(ReportTemplate).where(ReportTemplate.id == template_id)
            result = await session.execute(stmt)
            await session.commit()
        return result.rowcount > 0

    async def list_templates(self) -> list[dict]:
        async with self._sf() as session:
            stmt = select(ReportTemplate).order_by(ReportTemplate.created_at.desc())
            result = await session.execute(stmt)
            return [self._template_to_dict(t) for t in result.scalars().all()]

    async def get_template(self, template_id: str) -> dict | None:
        async with self._sf() as session:
            stmt = select(ReportTemplate).where(ReportTemplate.id == template_id)
            result = await session.execute(stmt)
            tmpl = result.scalar_one_or_none()
            return self._template_to_dict(tmpl) if tmpl else None

    # ---- Rule CRUD ----

    async def create_rule(
        self,
        template_id: str,
        scope: str,
        target_id: str,
        reviewer_id: str | None = None,
        deadline_cron: str = "0 18 * * 1-5",
        reminder_minutes: int = 30,
        escalation_minutes: int = 120,
        enabled: bool = True,
    ) -> dict:
        rule = ReportRule(
            template_id=template_id,
            scope=scope,
            target_id=target_id,
            reviewer_id=reviewer_id,
            deadline_cron=deadline_cron,
            reminder_minutes=reminder_minutes,
            escalation_minutes=escalation_minutes,
            enabled=enabled,
        )
        async with self._sf() as session:
            session.add(rule)
            await session.commit()
            await session.refresh(rule)
        log.info(f"创建规则: {rule.id[:8]} scope={scope} target={target_id}")
        return self._rule_to_dict(rule)

    async def update_rule(self, rule_id: str, **fields) -> dict | None:
        async with self._sf() as session:
            stmt = select(ReportRule).where(ReportRule.id == rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            if not rule:
                return None

            for key in ("scope", "target_id", "reviewer_id", "deadline_cron",
                        "reminder_minutes", "escalation_minutes", "enabled"):
                if key in fields:
                    setattr(rule, key, fields[key])

            await session.commit()
            await session.refresh(rule)
        return self._rule_to_dict(rule)

    async def delete_rule(self, rule_id: str) -> bool:
        async with self._sf() as session:
            stmt = delete(ReportRule).where(ReportRule.id == rule_id)
            result = await session.execute(stmt)
            await session.commit()
        return result.rowcount > 0

    async def list_rules(self, template_id: str | None = None) -> list[dict]:
        async with self._sf() as session:
            stmt = select(ReportRule).options(selectinload(ReportRule.template))
            if template_id:
                stmt = stmt.where(ReportRule.template_id == template_id)
            stmt = stmt.order_by(ReportRule.created_at.desc())
            result = await session.execute(stmt)
            return [self._rule_to_dict(r) for r in result.scalars().all()]

    # ---- Report CRUD ----

    async def create_report(
        self,
        reporter_id: str,
        report_type: str,
        report_date: date,
        title: str = "",
        content: str = "",
        status: str = "draft",
        auto_generated: bool = False,
        template_id: str | None = None,
        rule_id: str | None = None,
        reviewer_id: str | None = None,
    ) -> dict:
        report = Report(
            reporter_id=reporter_id,
            report_type=report_type,
            report_date=report_date,
            title=title,
            content=content,
            status=status,
            auto_generated=auto_generated,
            template_id=template_id,
            rule_id=rule_id,
            reviewer_id=reviewer_id,
        )
        async with self._sf() as session:
            session.add(report)
            await session.commit()
            await session.refresh(report)
        log.info(f"创建汇报: {report.id[:8]} type={report_type} date={report_date}")
        return self._report_to_dict(report)

    async def update_report(self, report_id: str, **fields) -> dict | None:
        async with self._sf() as session:
            stmt = select(Report).where(Report.id == report_id)
            result = await session.execute(stmt)
            report = result.scalar_one_or_none()
            if not report:
                return None

            for key in ("title", "content", "status", "reviewer_id", "reviewer_comment"):
                if key in fields:
                    setattr(report, key, fields[key])

            if fields.get("status") == "submitted" and not report.submitted_at:
                report.submitted_at = datetime.now()
            if fields.get("status") in ("reviewed", "rejected") and not report.reviewed_at:
                report.reviewed_at = datetime.now()

            await session.commit()
            await session.refresh(report)
        return self._report_to_dict(report)

    async def get_report(self, report_id: str) -> dict | None:
        async with self._sf() as session:
            stmt = select(Report).where(Report.id == report_id)
            result = await session.execute(stmt)
            report = result.scalar_one_or_none()
            return self._report_to_dict(report) if report else None

    async def list_reports(
        self,
        reporter_id: str | None = None,
        reporter_ids: list[str] | None = None,
        reviewer_id: str | None = None,
        report_type: str | None = None,
        status: str | None = None,
        since: date | None = None,
        until: date | None = None,
        limit: int = 50,
    ) -> list[dict]:
        async with self._sf() as session:
            stmt = select(Report)
            if reporter_ids is not None:
                if not reporter_ids:
                    return []
                stmt = stmt.where(Report.reporter_id.in_(reporter_ids))
            elif reporter_id:
                stmt = stmt.where(Report.reporter_id == reporter_id)
            if reviewer_id:
                stmt = stmt.where(Report.reviewer_id == reviewer_id)
            if report_type:
                stmt = stmt.where(Report.report_type == report_type)
            if status:
                stmt = stmt.where(Report.status == status)
            if since:
                stmt = stmt.where(Report.report_date >= since)
            if until:
                stmt = stmt.where(Report.report_date <= until)
            stmt = stmt.order_by(Report.report_date.desc()).limit(limit)
            result = await session.execute(stmt)
            return [self._report_to_dict(r) for r in result.scalars().all()]

    async def get_subordinate_ids(self, member_id: str) -> list[str]:
        """Get all subordinate member IDs from reporting relations"""
        from openvort.contacts.models import ReportingRelation

        async with self._sf() as session:
            stmt = select(ReportingRelation.reporter_id).where(
                ReportingRelation.supervisor_id == member_id
            )
            result = await session.execute(stmt)
            return [r[0] for r in result.all()]

    async def get_report_stats(
        self,
        reviewer_id: str | None = None,
        since: date | None = None,
        until: date | None = None,
    ) -> dict:
        """汇报统计：总数、各状态数"""
        async with self._sf() as session:
            stmt = select(Report.status, sa_func.count(Report.id))
            if reviewer_id:
                stmt = stmt.where(Report.reviewer_id == reviewer_id)
            if since:
                stmt = stmt.where(Report.report_date >= since)
            if until:
                stmt = stmt.where(Report.report_date <= until)
            stmt = stmt.group_by(Report.status)
            result = await session.execute(stmt)
            rows = result.all()

            stats = {"total": 0, "draft": 0, "submitted": 0, "reviewed": 0, "rejected": 0}
            for status, count in rows:
                stats[status] = count
                stats["total"] += count
            return stats

    # ---- Reminder & Delivery ----

    async def get_pending_reporters(self, rule_id: str) -> list[str]:
        """获取某规则下尚未提交汇报的成员 ID 列表"""
        async with self._sf() as session:
            # Get the rule
            stmt = select(ReportRule).where(ReportRule.id == rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            if not rule:
                return []

            today = date.today()

            if rule.scope == "member":
                # Check if this member has submitted today
                stmt = select(Report).where(
                    Report.reporter_id == rule.target_id,
                    Report.report_date == today,
                    Report.status.in_(["submitted", "reviewed"]),
                )
                result = await session.execute(stmt)
                if not result.scalar_one_or_none():
                    return [rule.target_id]
                return []

            elif rule.scope == "department":
                # Get all members in this department
                from openvort.contacts.models import MemberDepartment
                stmt = select(MemberDepartment.member_id).where(
                    MemberDepartment.department_id == int(rule.target_id)
                )
                result = await session.execute(stmt)
                member_ids = [r[0] for r in result.all()]

                # Find who hasn't submitted
                pending = []
                for mid in member_ids:
                    stmt = select(Report).where(
                        Report.reporter_id == mid,
                        Report.report_date == today,
                        Report.status.in_(["submitted", "reviewed"]),
                    )
                    result = await session.execute(stmt)
                    if not result.scalar_one_or_none():
                        pending.append(mid)
                return pending

        return []

    async def get_reviewer_for_member(self, member_id: str) -> str | None:
        """根据汇报关系获取成员的主要上级"""
        from openvort.contacts.models import ReportingRelation

        async with self._sf() as session:
            stmt = (
                select(ReportingRelation)
                .where(
                    ReportingRelation.reporter_id == member_id,
                    ReportingRelation.is_primary == True,  # noqa: E712
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            rel = result.scalar_one_or_none()
            return rel.supervisor_id if rel else None

    async def get_enabled_rules(self) -> list[dict]:
        """获取所有启用的规则"""
        async with self._sf() as session:
            stmt = (
                select(ReportRule)
                .options(selectinload(ReportRule.template))
                .where(ReportRule.enabled == True)  # noqa: E712
            )
            result = await session.execute(stmt)
            return [self._rule_to_dict(r) for r in result.scalars().all()]

    # ---- Helpers ----

    @staticmethod
    def _template_to_dict(t: ReportTemplate) -> dict:
        return {
            "id": t.id,
            "name": t.name,
            "report_type": t.report_type,
            "content_schema": json.loads(t.content_schema) if t.content_schema else {},
            "auto_collect": json.loads(t.auto_collect) if t.auto_collect else {},
            "owner_id": t.owner_id or "",
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }

    @staticmethod
    def _rule_to_dict(r: ReportRule) -> dict:
        return {
            "id": r.id,
            "template_id": r.template_id,
            "template_name": r.template.name if hasattr(r, "template") and r.template else "",
            "scope": r.scope,
            "target_id": r.target_id,
            "reviewer_id": r.reviewer_id or "",
            "deadline_cron": r.deadline_cron,
            "reminder_minutes": r.reminder_minutes,
            "escalation_minutes": r.escalation_minutes,
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

    @staticmethod
    def _report_to_dict(r: Report) -> dict:
        return {
            "id": r.id,
            "rule_id": r.rule_id or "",
            "template_id": r.template_id or "",
            "reporter_id": r.reporter_id,
            "reviewer_id": r.reviewer_id or "",
            "report_date": r.report_date.isoformat() if r.report_date else "",
            "report_type": r.report_type,
            "title": r.title,
            "content": r.content,
            "status": r.status,
            "auto_generated": r.auto_generated,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "reviewer_comment": r.reviewer_comment,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
