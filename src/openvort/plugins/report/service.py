"""
汇报业务层

模板/规则/汇报实例的 CRUD + 汇报生成 + 分发逻辑。
"""

import json
from datetime import date, datetime

from sqlalchemy import select, delete, func as sa_func
from sqlalchemy.orm import selectinload

from openvort.plugins.report.models import Report, ReportRule, ReportRuleMember, ReportTemplate
from openvort.utils.logging import get_logger

log = get_logger("plugins.report.service")

_DOW_CN = {0: "周日", 1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六"}


def _parse_cron_display(cron: str) -> str:
    """将 5 段式 cron 表达式转为可读中文，如 '0 18 * * 1-5' -> '每周一至周五 18:00'"""
    parts = cron.strip().split()
    if len(parts) != 5:
        return cron

    minute, hour, _dom, _month, dow = parts

    time_str = f"{int(hour):02d}:{int(minute):02d}" if hour.isdigit() and minute.isdigit() else f"{hour}:{minute}"

    if dow == "*":
        return f"每天 {time_str}"

    if "-" in dow:
        lo, hi = dow.split("-", 1)
        if lo.isdigit() and hi.isdigit():
            return f"每{_DOW_CN.get(int(lo), lo)}至{_DOW_CN.get(int(hi), hi)} {time_str}"

    if "," in dow:
        days = [_DOW_CN.get(int(d), d) for d in dow.split(",") if d.isdigit()]
        return f"每{'、'.join(days)} {time_str}" if days else f"{dow} {time_str}"

    if dow.isdigit():
        return f"每{_DOW_CN.get(int(dow), dow)} {time_str}"

    return f"{dow} {time_str}"


class ReportService:
    """汇报管理服务"""

    def __init__(self, session_factory):
        self._sf = session_factory

    # ---- Template CRUD ----

    async def create_template(
        self,
        name: str,
        report_type: str,
        description: str = "",
        content_schema: dict | None = None,
        auto_collect: dict | None = None,
        owner_id: str | None = None,
    ) -> dict:
        tmpl = ReportTemplate(
            name=name,
            description=description,
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

            for key in ("name", "description", "report_type", "owner_id"):
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
        from sqlalchemy import update
        async with self._sf() as session:
            stmt = select(ReportTemplate).where(ReportTemplate.id == template_id)
            result = await session.execute(stmt)
            tmpl = result.scalar_one_or_none()
            if not tmpl:
                return False
            await session.execute(
                update(Report).where(Report.template_id == template_id).values(template_id=None)
            )
            await session.delete(tmpl)
            await session.commit()
        return True

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
        member_ids: list[str],
        name: str = "",
        reviewer_id: str | None = None,
        deadline_cron: str = "0 18 * * 1-5",
        workdays_only: bool = True,
        reminder_minutes: int = 30,
        escalation_minutes: int = 120,
        enabled: bool = True,
    ) -> dict:
        from openvort.contacts.models import Member

        rule = ReportRule(
            name=name,
            template_id=template_id,
            reviewer_id=reviewer_id,
            deadline_cron=deadline_cron,
            workdays_only=workdays_only,
            reminder_minutes=reminder_minutes,
            escalation_minutes=escalation_minutes,
            enabled=enabled,
        )
        async with self._sf() as session:
            session.add(rule)
            await session.flush()

            valid_ids = [mid for mid in member_ids if mid]
            for mid in valid_ids:
                session.add(ReportRuleMember(rule_id=rule.id, member_id=mid))

            await session.commit()

            stmt = (
                select(ReportRule)
                .options(selectinload(ReportRule.template), selectinload(ReportRule.members))
                .where(ReportRule.id == rule.id)
            )
            result = await session.execute(stmt)
            rule = result.scalar_one()

            member_names = await self._resolve_member_names(session, valid_ids)
            log.info(f"创建规则: {rule.id[:8]} members={len(valid_ids)}")
            return self._rule_to_dict(rule, member_names)

    async def update_rule(self, rule_id: str, **fields) -> dict | None:
        from openvort.contacts.models import Member

        async with self._sf() as session:
            stmt = select(ReportRule).where(ReportRule.id == rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            if not rule:
                return None

            for key in ("name", "reviewer_id", "deadline_cron",
                        "workdays_only", "reminder_minutes", "escalation_minutes", "enabled"):
                if key in fields:
                    setattr(rule, key, fields[key])

            if "member_ids" in fields:
                await session.execute(
                    delete(ReportRuleMember).where(ReportRuleMember.rule_id == rule_id)
                )
                valid_ids = [mid for mid in fields["member_ids"] if mid]
                for mid in valid_ids:
                    session.add(ReportRuleMember(rule_id=rule_id, member_id=mid))

            await session.commit()

            stmt = (
                select(ReportRule)
                .options(selectinload(ReportRule.template), selectinload(ReportRule.members))
                .where(ReportRule.id == rule_id)
            )
            result = await session.execute(stmt)
            rule = result.scalar_one()

            mids = [rm.member_id for rm in rule.members]
            member_names = await self._resolve_member_names(session, mids)
            return self._rule_to_dict(rule, member_names)

    async def delete_rule(self, rule_id: str) -> bool:
        async with self._sf() as session:
            stmt = select(ReportRule).where(ReportRule.id == rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            if not rule:
                return False
            await session.delete(rule)
            await session.commit()
        return True

    async def list_rules(self, template_id: str | None = None) -> list[dict]:
        async with self._sf() as session:
            stmt = (
                select(ReportRule)
                .options(selectinload(ReportRule.template), selectinload(ReportRule.members))
            )
            if template_id:
                stmt = stmt.where(ReportRule.template_id == template_id)
            stmt = stmt.order_by(ReportRule.created_at.desc())
            result = await session.execute(stmt)
            rules = result.scalars().all()

            all_mids = set()
            for r in rules:
                for rm in r.members:
                    all_mids.add(rm.member_id)

            member_names = await self._resolve_member_names(session, list(all_mids)) if all_mids else {}

            return [self._rule_to_dict(r, member_names) for r in rules]

    async def get_rule(self, rule_id: str) -> dict | None:
        async with self._sf() as session:
            stmt = (
                select(ReportRule)
                .options(selectinload(ReportRule.template), selectinload(ReportRule.members))
                .where(ReportRule.id == rule_id)
            )
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            if not rule:
                return None
            mids = [rm.member_id for rm in rule.members]
            member_names = await self._resolve_member_names(session, mids)
            return self._rule_to_dict(rule, member_names)

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
            stmt = (
                select(ReportRule)
                .options(selectinload(ReportRule.members))
                .where(ReportRule.id == rule_id)
            )
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            if not rule:
                return []

            today = date.today()
            member_ids = [rm.member_id for rm in rule.members]

            if not member_ids:
                return []

            submitted_stmt = select(Report.reporter_id).where(
                Report.reporter_id.in_(member_ids),
                Report.report_date == today,
                Report.status.in_(["submitted", "reviewed"]),
            )
            result = await session.execute(submitted_stmt)
            submitted_ids = {r[0] for r in result.all()}

            return [mid for mid in member_ids if mid not in submitted_ids]

    async def get_reviewer_for_member(self, member_id: str) -> str | None:
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
        async with self._sf() as session:
            stmt = (
                select(ReportRule)
                .options(selectinload(ReportRule.template), selectinload(ReportRule.members))
                .where(ReportRule.enabled == True)  # noqa: E712
            )
            result = await session.execute(stmt)
            rules = result.scalars().all()
            all_mids = set()
            for r in rules:
                for rm in r.members:
                    all_mids.add(rm.member_id)
            member_names = await self._resolve_member_names(session, list(all_mids)) if all_mids else {}
            return [self._rule_to_dict(r, member_names) for r in rules]

    # ---- Test Send ----

    async def test_send_rule(self, rule_id: str) -> dict:
        """对指定规则触发一次测试通知，向所有成员发送提醒"""
        from openvort.plugins.vortflow.aggregator import send_im_to_member

        rule = await self.get_rule(rule_id)
        if not rule:
            return {"ok": False, "error": "规则不存在"}

        member_ids = rule.get("member_ids", [])
        if not member_ids:
            return {"ok": False, "error": "规则未关联任何成员"}

        template_name = rule.get("template_name", "未知模板")
        deadline_cron = rule.get("deadline_cron", "")
        workdays_only = rule.get("workdays_only", False)

        template = await self.get_template(rule.get("template_id", ""))
        report_type = template.get("report_type", "daily") if template else "daily"
        type_label = {"daily": "日报", "weekly": "周报", "monthly": "月报", "quarterly": "季报"}.get(report_type, "汇报")
        deadline_display = _parse_cron_display(deadline_cron)
        workday_tag = "（仅工作日）" if workdays_only else ""

        async with self._sf() as session:
            member_names = await self._resolve_member_names(session, member_ids)

        now = datetime.now()
        weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        date_str = now.strftime("%Y-%m-%d")
        weekday = weekday_cn[now.weekday()]

        try:
            from openvort.config.settings import get_settings
            site_url = (get_settings().web.site_url or "").rstrip("/")
        except Exception:
            site_url = ""

        sent, failed = 0, 0
        for mid in member_ids:
            name = member_names.get(mid, "")
            lines = [
                f"## [测试通知] {type_label}提醒 · {date_str} {weekday}",
                "",
                f"{name}，请按时提交{type_label}：",
                "",
                f"- 汇报模板：**{template_name}**",
                f"- 截止时间：**{deadline_display}**{workday_tag}",
            ]

            pending = await self.get_pending_reporters(rule_id)
            pending_names = [member_names.get(pid, pid[:8]) for pid in pending]
            if pending_names:
                lines.append(f"- 待提交：{', '.join(pending_names[:5])}" + (f" 等 {len(pending_names)} 人" if len(pending_names) > 5 else ""))

            if site_url:
                lines.extend(["", f"[前往提交汇报]({site_url}/reports)"])

            lines.extend(["", "---", "*此为测试消息，实际提醒将按规则设定的时间发送。*"])

            text = "\n".join(lines)
            try:
                await send_im_to_member(mid, text)
                sent += 1
            except Exception as e:
                log.warning(f"测试发送失败 member={mid}: {e}")
                failed += 1

        log.info(f"测试发送规则 {rule_id[:8]}: sent={sent} failed={failed}")
        return {
            "ok": True,
            "sent": sent,
            "failed": failed,
            "total": len(member_ids),
        }

    # ---- Helpers ----

    @staticmethod
    async def _resolve_member_names(session, member_ids: list[str]) -> dict[str, str]:
        if not member_ids:
            return {}
        from openvort.contacts.models import Member
        result = await session.execute(
            select(Member.id, Member.name).where(Member.id.in_(member_ids))
        )
        return {mid: mname for mid, mname in result.all()}

    @staticmethod
    def _template_to_dict(t: ReportTemplate) -> dict:
        return {
            "id": t.id,
            "name": t.name,
            "description": t.description or "",
            "report_type": t.report_type,
            "content_schema": json.loads(t.content_schema) if t.content_schema else {},
            "auto_collect": json.loads(t.auto_collect) if t.auto_collect else {},
            "owner_id": t.owner_id or "",
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }

    @staticmethod
    def _rule_to_dict(r: ReportRule, member_names: dict[str, str] | None = None) -> dict:
        member_names = member_names or {}
        mids = [rm.member_id for rm in r.members] if hasattr(r, "members") and r.members else []
        return {
            "id": r.id,
            "name": r.name or "",
            "template_id": r.template_id,
            "template_name": r.template.name if hasattr(r, "template") and r.template else "",
            "reviewer_id": r.reviewer_id or "",
            "deadline_cron": r.deadline_cron,
            "workdays_only": r.workdays_only,
            "reminder_minutes": r.reminder_minutes,
            "escalation_minutes": r.escalation_minutes,
            "enabled": r.enabled,
            "member_ids": mids,
            "member_count": len(mids),
            "member_names": [member_names.get(mid, mid[:8]) for mid in mids],
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
