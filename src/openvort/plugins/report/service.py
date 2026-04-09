"""
汇报业务层 (v2)

Publication CRUD + Report CRUD + IM 通知
"""

import json
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select, func as sa_func
from sqlalchemy.orm import selectinload

from openvort.plugins.report.models import (
    Report,
    ReportPublication,
    ReportPublicationReceiver,
    ReportPublicationSubmitter,
    ReportPublicationWhitelist,
    ReportRead,
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
                                 content_schema: dict | None = None, content_template: str = "",
                                 repeat_cycle: str = "daily",
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
            content_template=content_template,
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
                "name", "description", "report_type", "content_template",
                "repeat_cycle", "deadline_time",
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
            has_content_change = "content" in fields or "title" in fields
            for key in ("title", "content", "status", "publication_id"):
                if key in fields:
                    setattr(report, key, fields[key])

            if fields.get("status") == "submitted" and old_status != "submitted":
                report.submitted_at = datetime.now()

            await session.commit()
            await session.refresh(report)

        if fields.get("status") == "submitted" and old_status != "submitted" and report.publication_id:
            await self._notify_receivers_on_submit(report)
        elif has_content_change and report.status == "submitted" and report.publication_id:
            await self._notify_receivers_on_edit(report)

        return self._report_to_dict(report)

    async def withdraw_report(self, report_id: str, member_id: str) -> dict | None:
        """Withdraw a submitted report back to draft. Only the reporter can withdraw."""
        async with self._sf() as session:
            stmt = select(Report).where(Report.id == report_id)
            result = await session.execute(stmt)
            report = result.scalar_one_or_none()
            if not report:
                return None
            if report.reporter_id != member_id:
                return {"error": "只能撤回自己的汇报"}
            if report.status != "submitted":
                return {"error": "只有已提交的汇报才能撤回"}

            report.status = "draft"
            report.submitted_at = None
            await session.commit()
            await session.refresh(report)
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

            pub_ids = list({r.publication_id for r in reports if r.publication_id})
            pub_names = await self._resolve_publication_names(session, pub_ids) if pub_ids else {}

            items = []
            for r in reports:
                d = self._report_to_dict(r)
                mi = info.get(r.reporter_id, {})
                d["reporter_name"] = mi.get("name", "")
                d["reporter_avatar_url"] = mi.get("avatar_url", "")
                d["publication_name"] = pub_names.get(r.publication_id, "") if r.publication_id else ""
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

            pub_ids = list({r.publication_id for r in reports if r.publication_id})
            pub_names = await self._resolve_publication_names(session, pub_ids) if pub_ids else {}

            report_ids = [r.id for r in reports]
            read_ids: set[str] = set()
            if report_ids:
                read_result = await session.execute(
                    select(ReportRead.report_id).where(
                        ReportRead.report_id.in_(report_ids),
                        ReportRead.reader_id == receiver_id,
                    )
                )
                read_ids = {row[0] for row in read_result.all()}

            items = []
            for r in reports:
                d = self._report_to_dict(r)
                mi = info.get(r.reporter_id, {})
                d["reporter_name"] = mi.get("name", "")
                d["reporter_avatar_url"] = mi.get("avatar_url", "")
                d["publication_name"] = pub_names.get(r.publication_id, "") if r.publication_id else ""
                d["is_read"] = r.id in read_ids
                items.append(d)
            return items

    async def mark_report_read(self, report_id: str, reader_id: str) -> bool:
        async with self._sf() as session:
            existing = await session.execute(
                select(ReportRead).where(
                    ReportRead.report_id == report_id,
                    ReportRead.reader_id == reader_id,
                )
            )
            if existing.scalar_one_or_none():
                return True
            session.add(ReportRead(report_id=report_id, reader_id=reader_id))
            await session.commit()
            return True

    async def mark_all_reports_read(self, receiver_id: str, *,
                                     publication_id: str | None = None) -> int:
        """Mark all received unread reports as read. Returns count marked."""
        from sqlalchemy import or_, exists

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
            already_read = select(ReportRead.report_id).where(ReportRead.reader_id == receiver_id)

            stmt = select(Report.id).where(
                Report.publication_id.in_(sub),
                Report.status == "submitted",
                or_(~filter_exists, reporter_in_filter),
                Report.id.notin_(already_read),
            )
            if publication_id:
                stmt = stmt.where(Report.publication_id == publication_id)
            result = await session.execute(stmt)
            unread_ids = [row[0] for row in result.all()]

            for rid in unread_ids:
                session.add(ReportRead(report_id=rid, reader_id=receiver_id))
            if unread_ids:
                await session.commit()
            return len(unread_ids)

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

    async def get_submission_stats(self, receiver_id: str, *,
                                    publication_id: str | None = None,
                                    since: date | None = None,
                                    until: date | None = None) -> list[dict]:
        """Per (date, publication) submission stats for a receiver.

        Respects per-receiver submitter filters: if the receiver has configured
        filters for a publication, only the filtered submitters are counted.

        Returns a list of {publication_id, publication_name, report_date,
        total_submitters, submitted_count}.
        """
        from collections import defaultdict

        async with self._sf() as session:
            pub_stmt = (
                select(ReportPublication)
                .options(
                    selectinload(ReportPublication.submitters),
                    selectinload(ReportPublication.whitelist),
                    selectinload(ReportPublication.receiver_filters),
                )
                .join(ReportPublicationReceiver,
                      ReportPublicationReceiver.publication_id == ReportPublication.id)
                .where(
                    ReportPublicationReceiver.member_id == receiver_id,
                    ReportPublication.enabled == True,  # noqa: E712
                )
            )
            if publication_id:
                pub_stmt = pub_stmt.where(ReportPublication.id == publication_id)
            result = await session.execute(pub_stmt)
            pubs = result.scalars().unique().all()

            if not pubs:
                return []

            pub_map: dict[str, dict] = {}
            for p in pubs:
                wl = {w.member_id for w in p.whitelist}
                all_submitter_ids = [s.member_id for s in p.submitters if s.member_id not in wl]

                filter_ids = {f.submitter_id for f in p.receiver_filters if f.receiver_id == receiver_id}
                if filter_ids:
                    visible_ids = set(sid for sid in all_submitter_ids if sid in filter_ids)
                else:
                    visible_ids = set(all_submitter_ids)

                pub_map[p.id] = {
                    "name": p.name,
                    "total_submitters": len(visible_ids),
                    "visible_ids": visible_ids,
                }

            report_stmt = (
                select(Report.publication_id, Report.report_date, Report.reporter_id)
                .where(
                    Report.publication_id.in_(list(pub_map.keys())),
                    Report.status == "submitted",
                )
            )
            if since:
                report_stmt = report_stmt.where(Report.report_date >= since)
            if until:
                report_stmt = report_stmt.where(Report.report_date <= until)
            result = await session.execute(report_stmt)
            rows = result.all()

            count_map: dict[tuple, set] = defaultdict(set)
            for pid, rdate, reporter_id in rows:
                pm = pub_map.get(pid)
                if pm and reporter_id in pm["visible_ids"]:
                    count_map[(pid, rdate)].add(reporter_id)

            stats = []
            for (pid, rdate), submitted_set in sorted(
                count_map.items(), key=lambda x: str(x[0][1]), reverse=True
            ):
                pm = pub_map.get(pid)
                if not pm:
                    continue
                stats.append({
                    "publication_id": pid,
                    "publication_name": pm["name"],
                    "report_date": rdate.isoformat() if rdate else "",
                    "total_submitters": pm["total_submitters"],
                    "submitted_count": len(submitted_set),
                })
            return stats

    async def get_submission_detail(self, publication_id: str, report_date: date,
                                    receiver_id: str | None = None) -> dict | None:
        """Return submitted/not-submitted member lists for a publication on a given date.
        If receiver_id is provided, respects per-receiver submitter filters."""
        async with self._sf() as session:
            pub = await session.execute(
                select(ReportPublication)
                .options(
                    selectinload(ReportPublication.submitters),
                    selectinload(ReportPublication.whitelist),
                    selectinload(ReportPublication.receiver_filters),
                )
                .where(ReportPublication.id == publication_id)
            )
            pub_obj = pub.scalars().first()
            if not pub_obj:
                return None

            wl = {w.member_id for w in pub_obj.whitelist}
            all_submitter_ids = [s.member_id for s in pub_obj.submitters if s.member_id not in wl]

            if receiver_id:
                filter_ids = {f.submitter_id for f in pub_obj.receiver_filters if f.receiver_id == receiver_id}
                if filter_ids:
                    all_submitter_ids = [sid for sid in all_submitter_ids if sid in filter_ids]

            result = await session.execute(
                select(Report.reporter_id, Report.submitted_at)
                .where(
                    Report.publication_id == publication_id,
                    Report.report_date == report_date,
                    Report.status == "submitted",
                )
            )
            submitted_rows = result.all()
            submitted_map = {row[0]: row[1] for row in submitted_rows}
            visible_set = set(all_submitter_ids)
            submitted_ids = [mid for mid in submitted_map if mid in visible_set]
            not_submitted_ids = [mid for mid in all_submitter_ids if mid not in submitted_map]

            all_mids = list(set(submitted_ids + not_submitted_ids))
            info = await self._resolve_member_info(session, all_mids) if all_mids else {}

            submitted_list = []
            for mid in submitted_ids:
                mi = info.get(mid, {})
                submitted_list.append({
                    "member_id": mid,
                    "name": mi.get("name", ""),
                    "avatar_url": mi.get("avatar_url", ""),
                    "submitted_at": submitted_map[mid].isoformat() if submitted_map[mid] else None,
                })

            not_submitted_list = []
            for mid in not_submitted_ids:
                mi = info.get(mid, {})
                not_submitted_list.append({
                    "member_id": mid,
                    "name": mi.get("name", ""),
                    "avatar_url": mi.get("avatar_url", ""),
                })

            return {
                "publication_id": publication_id,
                "publication_name": pub_obj.name,
                "report_date": report_date.isoformat(),
                "deadline_time": pub_obj.deadline_time,
                "submitted": submitted_list,
                "not_submitted": not_submitted_list,
            }

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
                      "report_type": p.report_type,
                      "content_template": p.content_template or ""} for p in pubs]

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
            report_url = self._build_report_url("read")
            text = (
                f"**{reporter_name}** 提交了{type_label}\n\n"
                f"**{report.title or '无标题'}**\n\n"
                f"{(report.content or '')[:200]}{'...' if len(report.content or '') > 200 else ''}"
            )
            if report_url:
                text += f"\n\n[查看详情]({report_url})"
            for rid in receiver_ids:
                try:
                    await send_im_to_member(rid, text)
                except Exception as e:
                    log.warning(f"通知接收人失败 receiver={rid}: {e}")
        except Exception as e:
            log.warning(f"发送提交通知失败: {e}")

    async def _notify_receivers_on_edit(self, report: Report) -> None:
        """When a submitted report is edited, notify receivers."""
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
            report_url = self._build_report_url("read")
            text = (
                f"**{reporter_name}** 修改了{type_label}\n\n"
                f"**{report.title or '无标题'}**\n\n"
                f"{(report.content or '')[:200]}{'...' if len(report.content or '') > 200 else ''}"
            )
            if report_url:
                text += f"\n\n[查看详情]({report_url})"
            for rid in receiver_ids:
                try:
                    await send_im_to_member(rid, text)
                except Exception as e:
                    log.warning(f"编辑通知接收人失败 receiver={rid}: {e}")
        except Exception as e:
            log.warning(f"发送编辑通知失败: {e}")

    async def send_fill_reminders(self, publication_id: str, *,
                                   report_date: date | None = None) -> dict:
        """Send IM reminders to submitters who haven't submitted for the given date."""
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

            target_date = report_date or date.today()
            period_start = self._compute_period_start(pub.repeat_cycle, target_date)
            submitted_stmt = select(Report.reporter_id).where(
                Report.publication_id == publication_id,
                Report.report_date >= period_start,
                Report.report_date <= target_date,
                Report.status == "submitted",
            )
            result = await session.execute(submitted_stmt)
            submitted_ids = {r[0] for r in result.all()}
            pending_ids = [mid for mid in effective_ids if mid not in submitted_ids]
            names = await self._resolve_member_names(session, pending_ids)

        type_label = TYPE_LABELS.get(pub_dict.get("report_type", ""), "汇报")
        date_label = f"{target_date.month}月{target_date.day}日"
        deadline_display = self._compute_deadline_display(target_date, pub_dict.get("deadline_time", ""))
        report_url = self._build_report_url()
        sent, failed = 0, 0
        for mid in pending_ids:
            name = names.get(mid, "")
            text = (
                f"{name}，请及时提交{date_label}{type_label}：**{pub_dict['name']}**\n\n"
                f"截止时间：{deadline_display}"
            )
            if report_url:
                text += f"\n\n[前往填写]({report_url})"
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
            period_start = self._compute_period_start(pub.repeat_cycle, today)
            submitted_stmt = select(Report.reporter_id).where(
                Report.publication_id == publication_id,
                Report.report_date >= period_start,
                Report.report_date <= today,
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

        report_url = self._build_report_url("read")
        if report_url:
            lines.append(f"\n[查看汇报]({report_url})")

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
    def _compute_period_start(repeat_cycle: str, today: date) -> date:
        """Compute the start of the current reporting period based on repeat_cycle."""
        if repeat_cycle == "weekly":
            return today - timedelta(days=today.weekday())
        elif repeat_cycle == "monthly":
            return today.replace(day=1)
        return today

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
    def _compute_deadline_display(report_date: date, deadline_time: str) -> str:
        """Convert deadline_time config (e.g. '次日 08:45') to an absolute date string
        relative to report_date. E.g. report_date=4/8, deadline='次日 08:45' -> '4月9日 08:45'."""
        import re
        m = re.search(r"(\d{2}:\d{2})", deadline_time)
        hm = m.group(1) if m else "10:00"
        if deadline_time.startswith("次日"):
            d = report_date + timedelta(days=1)
        else:
            d = report_date
        return f"{d.month}月{d.day}日 {hm}"

    @staticmethod
    def _build_report_url(tab: str = "") -> str:
        from openvort.config.settings import get_settings
        site_url = (get_settings().web.site_url or "").rstrip("/")
        if not site_url:
            return ""
        url = f"{site_url}/reports"
        if tab:
            url += f"?tab={tab}"
        return url

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
    async def _resolve_publication_names(session, pub_ids: list[str]) -> dict[str, str]:
        if not pub_ids:
            return {}
        result = await session.execute(
            select(ReportPublication.id, ReportPublication.name).where(ReportPublication.id.in_(pub_ids))
        )
        return {pid: pname for pid, pname in result.all()}

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
            "content_template": p.content_template or "",
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
