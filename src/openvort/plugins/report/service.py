"""
汇报业务层 (v2)

Publication CRUD + Report CRUD + IM 通知
"""

import json
from datetime import date, datetime

from sqlalchemy import delete, select, func as sa_func
from sqlalchemy.orm import selectinload

from openvort.plugins.report.models import (
    Report,
    ReportPublication,
    ReportPublicationReceiver,
    ReportPublicationSubmitter,
    ReportPublicationWhitelist,
    ReportReceiverFilter,
)
from openvort.utils.logging import get_logger

log = get_logger("plugins.report.service")

CYCLE_LABELS = {"daily": "按日", "weekly": "按周", "monthly": "按月"}
TYPE_LABELS = {"daily": "日报", "weekly": "周报", "monthly": "月报", "quarterly": "季报"}


class ReportService:
    """汇报管理服务"""

    def __init__(self, session_factory):
        self._sf = session_factory

    # ===================== Publication CRUD =====================

    async def create_publication(self, *, name: str, description: str = "", report_type: str = "daily",
                                 content_schema: dict | None = None, repeat_cycle: str = "daily",
                                 deadline_time: str = "次日 10:00", reminder_enabled: bool = True,
                                 reminder_time: str = "10:00", skip_weekends: bool = True,
                                 skip_holidays: bool = True, allow_multiple: bool = True,
                                 allow_edit: bool = True, notify_summary: bool = True,
                                 notify_on_receive: bool = True, owner_id: str | None = None,
                                 submitter_ids: list[str] | None = None,
                                 whitelist_ids: list[str] | None = None,
                                 receiver_ids: list[str] | None = None,
                                 receiver_filters: dict[str, list[str]] | None = None) -> dict:
        pub = ReportPublication(
            name=name, description=description, report_type=report_type,
            content_schema=json.dumps(content_schema or {}),
            repeat_cycle=repeat_cycle, deadline_time=deadline_time,
            reminder_enabled=reminder_enabled, reminder_time=reminder_time,
            skip_weekends=skip_weekends, skip_holidays=skip_holidays,
            allow_multiple=allow_multiple, allow_edit=allow_edit,
            notify_summary=notify_summary, notify_on_receive=notify_on_receive,
            owner_id=owner_id,
        )
        async with self._sf() as session:
            session.add(pub)
            await session.flush()

            for mid in (submitter_ids or []):
                if mid:
                    session.add(ReportPublicationSubmitter(publication_id=pub.id, member_id=mid))
            for mid in (whitelist_ids or []):
                if mid:
                    session.add(ReportPublicationWhitelist(publication_id=pub.id, member_id=mid))
            for mid in (receiver_ids or []):
                if mid:
                    session.add(ReportPublicationReceiver(publication_id=pub.id, member_id=mid))

            if receiver_filters:
                for rid, sids in receiver_filters.items():
                    for sid in sids:
                        session.add(ReportReceiverFilter(publication_id=pub.id, receiver_id=rid, submitter_id=sid))

            await session.commit()
            return await self._load_publication_dict(session, pub.id)

    async def update_publication(self, publication_id: str, **fields) -> dict | None:
        async with self._sf() as session:
            pub = await self._get_pub(session, publication_id)
            if not pub:
                return None

            scalar_fields = (
                "name", "description", "report_type", "repeat_cycle", "deadline_time",
                "reminder_enabled", "reminder_time", "skip_weekends", "skip_holidays",
                "allow_multiple", "allow_edit", "notify_summary", "notify_on_receive",
                "owner_id", "enabled",
            )
            for key in scalar_fields:
                if key in fields:
                    setattr(pub, key, fields[key])
            if "content_schema" in fields:
                pub.content_schema = json.dumps(fields["content_schema"])

            if "submitter_ids" in fields:
                await self._replace_assoc(session, ReportPublicationSubmitter, publication_id, fields["submitter_ids"])
            if "whitelist_ids" in fields:
                await self._replace_assoc(session, ReportPublicationWhitelist, publication_id, fields["whitelist_ids"])
            if "receiver_ids" in fields:
                await self._replace_assoc(session, ReportPublicationReceiver, publication_id, fields["receiver_ids"])

            if "receiver_filters" in fields:
                await self._replace_receiver_filters(session, publication_id, fields["receiver_filters"] or {})

            await session.commit()
            return await self._load_publication_dict(session, publication_id)

    async def delete_publication(self, publication_id: str) -> bool:
        async with self._sf() as session:
            pub = await self._get_pub(session, publication_id)
            if not pub:
                return False
            await session.delete(pub)
            await session.commit()
        return True

    async def list_publications(self) -> list[dict]:
        async with self._sf() as session:
            stmt = (
                select(ReportPublication)
                .options(
                    selectinload(ReportPublication.submitters),
                    selectinload(ReportPublication.whitelist),
                    selectinload(ReportPublication.receivers),
                    selectinload(ReportPublication.receiver_filters),
                )
                .order_by(ReportPublication.created_at.desc())
            )
            result = await session.execute(stmt)
            pubs = result.scalars().all()

            all_mids = set()
            for p in pubs:
                for s in p.submitters:
                    all_mids.add(s.member_id)
                for w in p.whitelist:
                    all_mids.add(w.member_id)
                for r in p.receivers:
                    all_mids.add(r.member_id)
                for f in p.receiver_filters:
                    all_mids.add(f.receiver_id)
                    all_mids.add(f.submitter_id)

            names = await self._resolve_member_names(session, list(all_mids)) if all_mids else {}
            return [self._pub_to_dict(p, names) for p in pubs]

    async def get_publication(self, publication_id: str) -> dict | None:
        async with self._sf() as session:
            return await self._load_publication_dict(session, publication_id)

    # ===================== Report CRUD =====================

    async def create_report(self, *, reporter_id: str, report_type: str, report_date: date,
                            title: str = "", content: str = "", status: str = "draft",
                            auto_generated: bool = False, publication_id: str | None = None) -> dict:
        report = Report(
            publication_id=publication_id, reporter_id=reporter_id,
            report_type=report_type, report_date=report_date,
            title=title, content=content, status=status, auto_generated=auto_generated,
        )
        if status == "submitted":
            report.submitted_at = datetime.now()
        async with self._sf() as session:
            session.add(report)
            await session.commit()
            await session.refresh(report)

        if status == "submitted" and publication_id:
            await self._notify_receivers_on_submit(report)

        return self._report_to_dict(report)

    async def update_report(self, report_id: str, **fields) -> dict | None:
        async with self._sf() as session:
            stmt = select(Report).where(Report.id == report_id)
            result = await session.execute(stmt)
            report = result.scalar_one_or_none()
            if not report:
                return None

            old_status = report.status
            for key in ("title", "content", "status", "publication_id"):
                if key in fields:
                    setattr(report, key, fields[key])

            if fields.get("status") == "submitted" and old_status != "submitted":
                report.submitted_at = datetime.now()

            await session.commit()
            await session.refresh(report)

        if fields.get("status") == "submitted" and old_status != "submitted" and report.publication_id:
            await self._notify_receivers_on_submit(report)

        return self._report_to_dict(report)

    async def get_report(self, report_id: str) -> dict | None:
        async with self._sf() as session:
            stmt = select(Report).where(Report.id == report_id)
            result = await session.execute(stmt)
            report = result.scalar_one_or_none()
            if not report:
                return None
            info = await self._resolve_member_info(session, [report.reporter_id])
            d = self._report_to_dict(report)
            mi = info.get(report.reporter_id, {})
            d["reporter_name"] = mi.get("name", "")
            d["reporter_avatar_url"] = mi.get("avatar_url", "")

            if report.publication_id:
                pub = await session.get(ReportPublication, report.publication_id)
                if pub:
                    d["publication_name"] = pub.name
                    d["allow_edit"] = pub.allow_edit
            return d

    async def list_reports(self, *, reporter_id: str | None = None,
                           reporter_ids: list[str] | None = None,
                           publication_id: str | None = None,
                           report_type: str | None = None,
                           status: str | None = None,
                           since: date | None = None,
                           until: date | None = None,
                           limit: int = 50) -> list[dict]:
        async with self._sf() as session:
            stmt = select(Report)
            if reporter_ids is not None:
                if not reporter_ids:
                    return []
                stmt = stmt.where(Report.reporter_id.in_(reporter_ids))
            elif reporter_id:
                stmt = stmt.where(Report.reporter_id == reporter_id)
            if publication_id:
                stmt = stmt.where(Report.publication_id == publication_id)
            if report_type:
                stmt = stmt.where(Report.report_type == report_type)
            if status:
                stmt = stmt.where(Report.status == status)
            if since:
                stmt = stmt.where(Report.report_date >= since)
            if until:
                stmt = stmt.where(Report.report_date <= until)
            stmt = stmt.order_by(Report.report_date.desc(), Report.submitted_at.desc()).limit(limit)
            result = await session.execute(stmt)
            reports = result.scalars().all()

            all_mids = list({r.reporter_id for r in reports})
            info = await self._resolve_member_info(session, all_mids) if all_mids else {}
            items = []
            for r in reports:
                d = self._report_to_dict(r)
                mi = info.get(r.reporter_id, {})
                d["reporter_name"] = mi.get("name", "")
                d["reporter_avatar_url"] = mi.get("avatar_url", "")
                items.append(d)
            return items

    async def list_received_reports(self, receiver_id: str, *,
                                    publication_id: str | None = None,
                                    reporter_id: str | None = None,
                                    report_type: str | None = None,
                                    status: str | None = None,
                                    since: date | None = None,
                                    until: date | None = None,
                                    limit: int = 50) -> list[dict]:
        """List reports from publications where receiver_id is a receiver,
        respecting per-receiver submitter filters."""
        from sqlalchemy import or_, exists, and_

        async with self._sf() as session:
            sub = (
                select(ReportPublicationReceiver.publication_id)
                .where(ReportPublicationReceiver.member_id == receiver_id)
            )

            filter_exists = exists().where(
                ReportReceiverFilter.publication_id == Report.publication_id,
                ReportReceiverFilter.receiver_id == receiver_id,
            )
            reporter_in_filter = exists().where(
                ReportReceiverFilter.publication_id == Report.publication_id,
                ReportReceiverFilter.receiver_id == receiver_id,
                ReportReceiverFilter.submitter_id == Report.reporter_id,
            )

            stmt = select(Report).where(
                Report.publication_id.in_(sub),
                Report.status == "submitted",
                or_(~filter_exists, reporter_in_filter),
            )
            if publication_id:
                stmt = stmt.where(Report.publication_id == publication_id)
            if reporter_id:
                stmt = stmt.where(Report.reporter_id == reporter_id)
            if report_type:
                stmt = stmt.where(Report.report_type == report_type)
            if status:
                stmt = stmt.where(Report.status == status)
            if since:
                stmt = stmt.where(Report.report_date >= since)
            if until:
                stmt = stmt.where(Report.report_date <= until)
            stmt = stmt.order_by(Report.report_date.desc(), Report.submitted_at.desc()).limit(limit)
            result = await session.execute(stmt)
            reports = result.scalars().all()

            all_mids = list({r.reporter_id for r in reports})
            info = await self._resolve_member_info(session, all_mids) if all_mids else {}
            items = []
            for r in reports:
                d = self._report_to_dict(r)
                mi = info.get(r.reporter_id, {})
                d["reporter_name"] = mi.get("name", "")
                d["reporter_avatar_url"] = mi.get("avatar_url", "")
                items.append(d)
            return items

    async def get_report_stats(self, *, reporter_id: str | None = None,
                               receiver_id: str | None = None,
                               since: date | None = None,
                               until: date | None = None) -> dict:
        async with self._sf() as session:
            stmt = select(Report.status, sa_func.count(Report.id))
            if reporter_id:
                stmt = stmt.where(Report.reporter_id == reporter_id)
            if receiver_id:
                sub = (
                    select(ReportPublicationReceiver.publication_id)
                    .where(ReportPublicationReceiver.member_id == receiver_id)
                )
                stmt = stmt.where(Report.publication_id.in_(sub))
            if since:
                stmt = stmt.where(Report.report_date >= since)
            if until:
                stmt = stmt.where(Report.report_date <= until)
            stmt = stmt.group_by(Report.status)
            result = await session.execute(stmt)
            rows = result.all()

            stats = {"total": 0, "draft": 0, "submitted": 0}
            for s, count in rows:
                stats[s] = count
                stats["total"] += count
            return stats

    async def get_publications_for_submitter(self, member_id: str) -> list[dict]:
        """Get enabled publications where member is a submitter (and not whitelisted)."""
        async with self._sf() as session:
            sub_ids = select(ReportPublicationSubmitter.publication_id).where(
                ReportPublicationSubmitter.member_id == member_id
            )
            wl_ids = select(ReportPublicationWhitelist.publication_id).where(
                ReportPublicationWhitelist.member_id == member_id
            )
            stmt = (
                select(ReportPublication)
                .where(
                    ReportPublication.id.in_(sub_ids),
                    ReportPublication.id.notin_(wl_ids),
                    ReportPublication.enabled == True,  # noqa: E712
                )
                .order_by(ReportPublication.created_at.desc())
            )
            result = await session.execute(stmt)
            pubs = result.scalars().all()
            return [{"id": p.id, "name": p.name, "description": p.description,
                      "report_type": p.report_type} for p in pubs]

    # ===================== IM Notifications =====================

    async def _notify_receivers_on_submit(self, report: Report) -> None:
        """When a report is submitted, notify receivers of its publication (if enabled),
        respecting per-receiver submitter filters."""
        try:
            async with self._sf() as session:
                pub = await self._get_pub(session, report.publication_id)
                if not pub or not pub.notify_on_receive:
                    return
                all_receiver_ids = [r.member_id for r in pub.receivers]
                if not all_receiver_ids:
                    return

                filter_map = self._build_receiver_filter_map(pub)
                receiver_ids = [
                    rid for rid in all_receiver_ids
                    if rid not in filter_map or report.reporter_id in filter_map[rid]
                ]
                if not receiver_ids:
                    return

                names = await self._resolve_member_names(session, [report.reporter_id])
                reporter_name = names.get(report.reporter_id, "")

            from openvort.plugins.vortflow.aggregator import send_im_to_member

            type_label = TYPE_LABELS.get(report.report_type, "汇报")
            text = (
                f"**{reporter_name}** 提交了{type_label}\n\n"
                f"**{report.title or '无标题'}**\n\n"
                f"{(report.content or '')[:200]}{'...' if len(report.content or '') > 200 else ''}"
            )
            for rid in receiver_ids:
                try:
                    await send_im_to_member(rid, text)
                except Exception as e:
                    log.warning(f"通知接收人失败 receiver={rid}: {e}")
        except Exception as e:
            log.warning(f"发送提交通知失败: {e}")

    async def send_fill_reminders(self, publication_id: str) -> dict:
        """Send IM reminders to submitters who haven't submitted yet today."""
        from openvort.plugins.vortflow.aggregator import send_im_to_member

        async with self._sf() as session:
            pub_dict = await self._load_publication_dict(session, publication_id)
            if not pub_dict:
                return {"ok": False, "error": "发布不存在"}

            pub = await self._get_pub(session, publication_id)
            submitter_ids = [s.member_id for s in pub.submitters]
            whitelist_ids = {w.member_id for w in pub.whitelist}
            effective_ids = [sid for sid in submitter_ids if sid not in whitelist_ids]

            if not effective_ids:
                return {"ok": True, "sent": 0, "total": 0}

            today = date.today()
            submitted_stmt = select(Report.reporter_id).where(
                Report.publication_id == publication_id,
                Report.report_date == today,
                Report.status == "submitted",
            )
            result = await session.execute(submitted_stmt)
            submitted_ids = {r[0] for r in result.all()}
            pending_ids = [mid for mid in effective_ids if mid not in submitted_ids]
            names = await self._resolve_member_names(session, pending_ids)

        type_label = TYPE_LABELS.get(pub_dict.get("report_type", ""), "汇报")
        sent, failed = 0, 0
        for mid in pending_ids:
            name = names.get(mid, "")
            text = (
                f"{name}，请及时提交{type_label}：**{pub_dict['name']}**\n\n"
                f"截止时间：{pub_dict.get('deadline_time', '')}"
            )
            try:
                await send_im_to_member(mid, text)
                sent += 1
            except Exception as e:
                log.warning(f"提醒发送失败 member={mid}: {e}")
                failed += 1

        return {
            "ok": True, "sent": sent, "failed": failed,
            "total": len(pending_ids),
            "submitted_count": len(submitted_ids),
            "submitter_count": len(effective_ids),
        }

    async def send_deadline_summary(self, publication_id: str) -> dict:
        """At deadline, send summary to all receivers."""
        from openvort.plugins.vortflow.aggregator import send_im_to_member

        async with self._sf() as session:
            pub = await self._get_pub(session, publication_id)
            if not pub or not pub.notify_summary:
                return {"ok": False, "error": "发布不存在或未启用汇总通知"}

            receiver_ids = [r.member_id for r in pub.receivers]
            if not receiver_ids:
                return {"ok": True, "sent": 0}

            submitter_ids = [s.member_id for s in pub.submitters]
            whitelist_ids = {w.member_id for w in pub.whitelist}
            effective_ids = [sid for sid in submitter_ids if sid not in whitelist_ids]

            today = date.today()
            submitted_stmt = select(Report.reporter_id).where(
                Report.publication_id == publication_id,
                Report.report_date == today,
                Report.status == "submitted",
            )
            result = await session.execute(submitted_stmt)
            submitted_ids = {r[0] for r in result.all()}

            all_mids = list(set(effective_ids) | set(receiver_ids))
            names = await self._resolve_member_names(session, all_mids)

        submitted_names = [names.get(mid, mid[:8]) for mid in effective_ids if mid in submitted_ids]
        pending_names = [names.get(mid, mid[:8]) for mid in effective_ids if mid not in submitted_ids]

        type_label = TYPE_LABELS.get(pub.report_type, "汇报")
        lines = [
            f"## {type_label}汇总 · {pub.name}",
            "",
            f"- 应提交：{len(effective_ids)} 人",
            f"- 已提交：{len(submitted_names)} 人",
            f"- 未提交：{len(pending_names)} 人",
        ]
        if pending_names:
            lines.append(f"\n未提交成员：{'、'.join(pending_names[:10])}"
                         + (f" 等{len(pending_names)}人" if len(pending_names) > 10 else ""))

        text = "\n".join(lines)
        sent = 0
        for rid in receiver_ids:
            try:
                await send_im_to_member(rid, text)
                sent += 1
            except Exception as e:
                log.warning(f"汇总通知发送失败 receiver={rid}: {e}")

        return {"ok": True, "sent": sent, "total": len(receiver_ids)}

    # ===================== Helpers =====================

    @staticmethod
    async def _get_pub(session, publication_id: str) -> ReportPublication | None:
        stmt = (
            select(ReportPublication)
            .options(
                selectinload(ReportPublication.submitters),
                selectinload(ReportPublication.whitelist),
                selectinload(ReportPublication.receivers),
                selectinload(ReportPublication.receiver_filters),
            )
            .where(ReportPublication.id == publication_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_publication_dict(self, session, publication_id: str) -> dict | None:
        pub = await self._get_pub(session, publication_id)
        if not pub:
            return None
        all_mids = set()
        for s in pub.submitters:
            all_mids.add(s.member_id)
        for w in pub.whitelist:
            all_mids.add(w.member_id)
        for r in pub.receivers:
            all_mids.add(r.member_id)
        if pub.owner_id:
            all_mids.add(pub.owner_id)
        names = await self._resolve_member_names(session, list(all_mids)) if all_mids else {}
        return self._pub_to_dict(pub, names)

    @staticmethod
    async def _replace_receiver_filters(session, publication_id: str, filters: dict[str, list[str]]):
        """Replace receiver filter rows. filters = {receiver_id: [submitter_id, ...]}"""
        await session.execute(
            delete(ReportReceiverFilter).where(ReportReceiverFilter.publication_id == publication_id)
        )
        for rid, sids in filters.items():
            for sid in sids:
                if rid and sid:
                    session.add(ReportReceiverFilter(publication_id=publication_id, receiver_id=rid, submitter_id=sid))

    @staticmethod
    def _build_receiver_filter_map(pub: ReportPublication) -> dict[str, set[str]]:
        """Build {receiver_id: set(submitter_ids)} from publication's receiver_filters.
        Only receivers with configured filters appear in the map."""
        fm: dict[str, set[str]] = {}
        for f in pub.receiver_filters:
            fm.setdefault(f.receiver_id, set()).add(f.submitter_id)
        return fm

    @staticmethod
    async def _replace_assoc(session, model_cls, publication_id: str, member_ids: list[str]):
        await session.execute(
            delete(model_cls).where(model_cls.publication_id == publication_id)
        )
        for mid in member_ids:
            if mid:
                session.add(model_cls(publication_id=publication_id, member_id=mid))

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
    async def _resolve_member_info(session, member_ids: list[str]) -> dict[str, dict]:
        """Return {member_id: {"name": ..., "avatar_url": ...}}"""
        if not member_ids:
            return {}
        from openvort.contacts.models import Member
        result = await session.execute(
            select(Member.id, Member.name, Member.avatar_url).where(Member.id.in_(member_ids))
        )
        return {mid: {"name": mname, "avatar_url": avatar or ""} for mid, mname, avatar in result.all()}

    @staticmethod
    def _pub_to_dict(p: ReportPublication, names: dict[str, str] | None = None) -> dict:
        names = names or {}
        submitter_ids = [s.member_id for s in p.submitters]
        whitelist_ids = [w.member_id for w in p.whitelist]
        receiver_ids = [r.member_id for r in p.receivers]

        rf_map: dict[str, list[str]] = {}
        for f in (p.receiver_filters or []):
            rf_map.setdefault(f.receiver_id, []).append(f.submitter_id)

        return {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "report_type": p.report_type,
            "content_schema": json.loads(p.content_schema) if p.content_schema else {},
            "repeat_cycle": p.repeat_cycle,
            "deadline_time": p.deadline_time,
            "reminder_enabled": p.reminder_enabled,
            "reminder_time": p.reminder_time,
            "skip_weekends": p.skip_weekends,
            "skip_holidays": p.skip_holidays,
            "allow_multiple": p.allow_multiple,
            "allow_edit": p.allow_edit,
            "notify_summary": p.notify_summary,
            "notify_on_receive": p.notify_on_receive,
            "owner_id": p.owner_id or "",
            "owner_name": names.get(p.owner_id, "") if p.owner_id else "",
            "enabled": p.enabled,
            "submitter_ids": submitter_ids,
            "submitter_names": [names.get(mid, mid[:8]) for mid in submitter_ids],
            "submitter_count": len(submitter_ids),
            "whitelist_ids": whitelist_ids,
            "whitelist_names": [names.get(mid, mid[:8]) for mid in whitelist_ids],
            "receiver_ids": receiver_ids,
            "receiver_names": [names.get(mid, mid[:8]) for mid in receiver_ids],
            "receiver_filters": rf_map,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }

    @staticmethod
    def _report_to_dict(r: Report) -> dict:
        return {
            "id": r.id,
            "publication_id": r.publication_id or "",
            "reporter_id": r.reporter_id,
            "report_date": r.report_date.isoformat() if r.report_date else "",
            "report_type": r.report_type,
            "title": r.title,
            "content": r.content,
            "status": r.status,
            "auto_generated": r.auto_generated,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
