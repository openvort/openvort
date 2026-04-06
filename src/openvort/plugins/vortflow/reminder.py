"""VortFlow work item reminder service — scheduled scanning + staggered IM delivery."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.aggregator import send_im_to_member
from openvort.plugins.vortflow.engine import (
    BUG_CLOSED_STATES,
    STORY_DONE_STATES,
    TASK_DONE_STATES,
)
from openvort.plugins.vortflow.models import (
    FlowBug,
    FlowIteration,
    FlowIterationBug,
    FlowIterationStory,
    FlowIterationTask,
    FlowProject,
    FlowProjectMember,
    FlowReminderSettings,
    FlowStory,
    FlowTask,
)
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.reminder")

_PRIORITY_LABEL = {1: "紧急", 2: "高", 3: "中", 4: "低"}
_SEVERITY_LABEL = {1: "致命", 2: "严重", 3: "一般", 4: "轻微"}

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

STAGGER_DELAY = 0.5  # seconds between IM sends to avoid flooding

_E_SUN = chr(0x2600) + chr(0xFE0F)       # ☀️
_E_CLOCK = chr(0x1F550)                   # 🕐
_E_CLIPBOARD = chr(0x1F4CB)               # 📋
_E_RED = chr(0x1F534)                     # 🔴
_E_YELLOW = chr(0x1F7E1)                  # 🟡
_E_FIRE = chr(0x1F525)                    # 🔥
_E_CHART = chr(0x1F4CA)                   # 📊
_E_BULB = chr(0x1F4A1)                    # 💡
_E_WARN = chr(0x26A0) + chr(0xFE0F)      # ⚠️

DEFAULT_SCENES: dict[str, dict[str, Any]] = {
    "morning": {"enabled": True, "time": "09:00"},
    "afternoon": {"enabled": False, "time": "14:00"},
    "weekly": {"enabled": True, "time": "17:00", "day": 5},
    "instant": {"enabled": True},
}


class ReminderService:
    """Scans work items per project and dispatches staggered IM reminders."""

    def __init__(self):
        self._scheduler = None
        self._ws_manager = None
        self._registered_jobs: set[str] = set()

    def set_scheduler(self, scheduler) -> None:
        self._scheduler = scheduler

    def set_ws_manager(self, ws_manager) -> None:
        self._ws_manager = ws_manager

    # ------------------------------------------------------------------
    # Scheduler registration
    # ------------------------------------------------------------------

    async def sync_all(self) -> None:
        """Load all enabled reminder settings and register cron jobs."""
        if not self._scheduler:
            log.warning("Scheduler not set, skip reminder sync")
            return

        for jid in list(self._registered_jobs):
            self._scheduler.remove(jid)
        self._registered_jobs.clear()

        sf = get_session_factory()
        async with sf() as session:
            rows = (await session.execute(
                select(FlowReminderSettings).where(FlowReminderSettings.enabled == True)  # noqa: E712
            )).scalars().all()

        for setting in rows:
            self._register_project(setting)

        log.info("Reminder sync done: %d projects registered", len(rows))

    def _register_project(self, setting: FlowReminderSettings) -> None:
        scenes = _parse_scenes(setting.scenes_json)
        work_days = setting.work_days or "1,2,3,4,5"
        dow = _work_days_to_cron(work_days)
        pid = setting.project_id

        if scenes.get("morning", {}).get("enabled"):
            t = scenes["morning"].get("time", "09:00")
            h, m = _parse_time(t)
            jid = f"vf_remind_{pid}_morning"
            self._scheduler.add_cron(jid, lambda _pid=pid: self._run("morning", _pid), f"{m} {h} * * {dow}")
            self._registered_jobs.add(jid)

        if scenes.get("afternoon", {}).get("enabled"):
            t = scenes["afternoon"].get("time", "14:00")
            h, m = _parse_time(t)
            jid = f"vf_remind_{pid}_afternoon"
            self._scheduler.add_cron(jid, lambda _pid=pid: self._run("afternoon", _pid), f"{m} {h} * * {dow}")
            self._registered_jobs.add(jid)

        if scenes.get("weekly", {}).get("enabled"):
            t = scenes["weekly"].get("time", "17:00")
            d = scenes["weekly"].get("day", 5)
            h, m_val = _parse_time(t)
            cron_dow = str(int(d) - 1) if int(d) >= 1 else "4"
            jid = f"vf_remind_{pid}_weekly"
            self._scheduler.add_cron(jid, lambda _pid=pid: self._run("weekly", _pid), f"{m_val} {h} * * {cron_dow}")
            self._registered_jobs.add(jid)

    def unregister_project(self, project_id: str) -> None:
        for scene in ("morning", "afternoon", "weekly"):
            jid = f"vf_remind_{project_id}_{scene}"
            if jid in self._registered_jobs:
                self._scheduler.remove(jid)
                self._registered_jobs.discard(jid)

    def register_project(self, setting: FlowReminderSettings) -> None:
        self.unregister_project(setting.project_id)
        if setting.enabled:
            self._register_project(setting)

    # ------------------------------------------------------------------
    # Execution entry
    # ------------------------------------------------------------------

    async def _run(self, scene: str, project_id: str) -> None:
        try:
            await self._execute(scene, project_id)
        except Exception:
            log.exception("Reminder execution failed: scene=%s project=%s", scene, project_id)

    async def _execute(self, scene: str, project_id: str) -> None:
        sf = get_session_factory()
        log.info("[reminder] _execute start: scene=%s project=%s", scene, project_id)

        async with sf() as session:
            setting = (await session.execute(
                select(FlowReminderSettings).where(FlowReminderSettings.project_id == project_id)
            )).scalar_one_or_none()
            if not setting or not setting.enabled:
                log.info("[reminder] skip: setting not found or disabled")
                return

            project = await session.get(FlowProject, project_id)
            if not project:
                log.info("[reminder] skip: project not found")
                return
            project_name = project.name

            # Collect members from multiple sources: project members + owner + work item assignees
            member_id_set: set[str] = set()

            pm_rows = (await session.execute(
                select(FlowProjectMember.member_id).where(FlowProjectMember.project_id == project_id)
            )).scalars().all()
            member_id_set.update(pm_rows)

            if project.owner_id:
                member_id_set.add(project.owner_id)

            for Model in (FlowStory, FlowTask, FlowBug):
                assignee_rows = (await session.execute(
                    select(Model.assignee_id).where(
                        Model.project_id == project_id,
                        Model.assignee_id.is_not(None),
                    ).distinct()
                )).scalars().all()
                member_id_set.update(assignee_rows)

            member_id_set.discard(None)
            if not member_id_set:
                log.info("[reminder] skip: no related members")
                return

            member_ids = list(member_id_set)
            log.info("[reminder] project=%s members=%d", project_name, len(member_ids))

            now = datetime.now()
            near_days = setting.near_deadline_days or 3

            stories = (await session.execute(
                select(FlowStory).where(
                    FlowStory.project_id == project_id,
                    FlowStory.state.not_in(STORY_DONE_STATES),
                )
            )).scalars().all()

            tasks = (await session.execute(
                select(FlowTask).where(
                    FlowTask.project_id == project_id,
                    FlowTask.state.not_in(TASK_DONE_STATES),
                )
            )).scalars().all()

            bugs = (await session.execute(
                select(FlowBug).where(
                    FlowBug.project_id == project_id,
                    FlowBug.state.not_in(BUG_CLOSED_STATES),
                )
            )).scalars().all()

            # Active iterations
            iterations = (await session.execute(
                select(FlowIteration).where(
                    FlowIteration.project_id == project_id,
                    FlowIteration.status == "active",
                )
            )).scalars().all()

            # Iteration progress (for active iterations)
            iter_progress: dict[str, dict] = {}
            for it in iterations:
                s_total = (await session.execute(
                    select(func.count()).select_from(FlowIterationStory)
                    .where(FlowIterationStory.iteration_id == it.id)
                )).scalar_one()
                s_done = (await session.execute(
                    select(func.count()).select_from(FlowIterationStory)
                    .join(FlowStory, FlowIterationStory.story_id == FlowStory.id)
                    .where(FlowIterationStory.iteration_id == it.id, FlowStory.state.in_(STORY_DONE_STATES))
                )).scalar_one()
                t_total = (await session.execute(
                    select(func.count()).select_from(FlowIterationTask)
                    .where(FlowIterationTask.iteration_id == it.id)
                )).scalar_one()
                t_done = (await session.execute(
                    select(func.count()).select_from(FlowIterationTask)
                    .join(FlowTask, FlowIterationTask.task_id == FlowTask.id)
                    .where(FlowIterationTask.iteration_id == it.id, FlowTask.state.in_(TASK_DONE_STATES))
                )).scalar_one()
                b_total = (await session.execute(
                    select(func.count()).select_from(FlowIterationBug)
                    .where(FlowIterationBug.iteration_id == it.id)
                )).scalar_one()
                b_done = (await session.execute(
                    select(func.count()).select_from(FlowIterationBug)
                    .join(FlowBug, FlowIterationBug.bug_id == FlowBug.id)
                    .where(FlowIterationBug.iteration_id == it.id, FlowBug.state.in_(BUG_CLOSED_STATES))
                )).scalar_one()
                total = s_total + t_total + b_total
                done = s_done + t_done + b_done
                days_left = (it.end_date - now).days if it.end_date else None
                iter_progress[it.id] = {
                    "name": it.name, "total": total, "done": done,
                    "days_left": days_left,
                }

            # Resolve member names
            from openvort.contacts.models import Member
            name_map: dict[str, str] = {}
            if member_ids:
                rows = (await session.execute(
                    select(Member.id, Member.name).where(Member.id.in_(member_ids))
                )).all()
                name_map = {r[0]: r[1] for r in rows}

        # Build per-member data and send
        all_items = (
            [("story", s) for s in stories]
            + [("task", t) for t in tasks]
            + [("bug", b) for b in bugs]
        )

        sent = 0
        for mid in member_ids:
            member_name = name_map.get(mid, "")
            my_items = [
                (etype, item) for etype, item in all_items
                if getattr(item, "assignee_id", None) == mid
            ]

            log.info("[reminder] member=%s(%s) items=%d", member_name, mid, len(my_items))

            if setting.skip_empty and not my_items:
                log.info("[reminder] skip member %s: no items (skip_empty)", mid)
                continue
            if setting.min_threshold and len(my_items) < setting.min_threshold:
                log.info("[reminder] skip member %s: below threshold", mid)
                continue

            prefs_ok = await _check_member_prefs(mid, scene)
            if not prefs_ok:
                log.info("[reminder] skip member %s: prefs disabled", mid)
                continue

            now = datetime.now()
            text = _render_message(
                scene=scene,
                member_name=member_name,
                member_id=mid,
                project_id=project_id,
                project_name=project_name,
                items=my_items,
                near_days=setting.near_deadline_days or 3,
                now=now,
                iter_progress=iter_progress,
            )

            log.info("[reminder] rendered text length=%d for %s", len(text) if text else 0, mid)
            if text:
                if sent > 0:
                    await asyncio.sleep(STAGGER_DELAY)

                # 1) Write to notifications table (always works, even in dev mode)
                title = _scene_title(scene)
                await _write_notification(mid, title, text, project_id, scene)

                # 2) Push via WebSocket
                if self._ws_manager:
                    try:
                        await self._ws_manager.send_to(mid, {
                            "type": "vortflow_notification",
                            "title": title,
                            "summary": text[:200],
                        })
                    except Exception:
                        pass

                # 3) Try IM send (works in production with channels configured)
                try:
                    await send_im_to_member(mid, text)
                except Exception:
                    log.debug("IM send skipped or failed for %s", mid)

                sent += 1
                log.info("[reminder] notification delivered to %s", mid)

        log.info("Reminder [%s] for project %s: sent to %d members", scene, project_id, sent)

    # ------------------------------------------------------------------
    # Manual trigger (for testing / API)
    # ------------------------------------------------------------------

    async def run_now(self, project_id: str, scene: str = "morning") -> dict:
        await self._run(scene, project_id)
        return {"ok": True, "scene": scene, "project_id": project_id}


# ======================================================================
# Helpers
# ======================================================================

_SCENE_TITLES = {
    "morning": "晨间工作简报",
    "afternoon": "午后进度检查",
    "weekly": "周工作总结",
}


def _scene_title(scene: str) -> str:
    return _SCENE_TITLES.get(scene, "工作项提醒")


async def _write_notification(member_id: str, title: str, summary: str, project_id: str, scene: str) -> None:
    try:
        sf = get_session_factory()
        from openvort.db.models import Notification
        async with sf() as session:
            n = Notification(
                recipient_id=member_id,
                source="vortflow",
                source_id=f"reminder_{scene}",
                title=title,
                summary=summary[:2000],
                status="sent",
                data_json=json.dumps({"project_id": project_id, "scene": scene}, ensure_ascii=False),
            )
            session.add(n)
            await session.commit()
    except Exception:
        log.warning("Failed to write notification for %s", member_id, exc_info=True)


def _parse_scenes(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_time(t: str) -> tuple[str, str]:
    parts = t.split(":")
    return parts[0], parts[1] if len(parts) > 1 else "0"


def _work_days_to_cron(work_days: str) -> str:
    """Convert '1,2,3,4,5' (1=Mon) to APScheduler day_of_week '0,1,2,3,4' (0=Mon)."""
    nums = [str(int(d.strip()) - 1) for d in work_days.split(",") if d.strip().isdigit()]
    return ",".join(nums) if nums else "0,1,2,3,4"


async def _check_member_prefs(member_id: str, scene: str) -> bool:
    """Check if a member has opted out of this reminder scene."""
    try:
        sf = get_session_factory()
        from openvort.contacts.models import Member
        async with sf() as session:
            m = await session.get(Member, member_id)
            if not m:
                return False
            if getattr(m, "is_virtual", False):
                return False
            raw = getattr(m, "notification_prefs", None) or "{}"
            prefs = json.loads(raw) if isinstance(raw, str) else raw
            vf = prefs.get("vortflow", {})
            reminder = vf.get("reminder", {})
            if not reminder.get("enabled", True):
                return False
            scene_pref = reminder.get(scene, {})
            if isinstance(scene_pref, dict) and not scene_pref.get("enabled", True):
                return False
    except Exception:
        pass
    return True


def _get_site_url() -> str:
    try:
        from openvort.config.settings import get_settings
        return (get_settings().web.site_url or "").rstrip("/")
    except Exception:
        return ""


def _render_message(
    *,
    scene: str,
    member_name: str,
    member_id: str,
    project_id: str,
    project_name: str,
    items: list[tuple[str, Any]],
    near_days: int,
    now: datetime,
    iter_progress: dict[str, dict],
) -> str:
    site_url = _get_site_url()
    if scene == "morning":
        return _render_morning(member_name, member_id, project_id, project_name, items, near_days, now, iter_progress, site_url)
    if scene == "afternoon":
        return _render_afternoon(member_name, member_id, project_id, project_name, items, near_days, now, iter_progress, site_url)
    if scene == "weekly":
        return _render_weekly(member_name, member_id, project_id, project_name, items, near_days, now, iter_progress, site_url)
    return ""


# ------------------------------------------------------------------
# Morning briefing
# ------------------------------------------------------------------

def _render_morning(
    name: str, member_id: str, project_id: str, project: str,
    items: list[tuple[str, Any]],
    near_days: int, now: datetime,
    iter_progress: dict, site_url: str,
) -> str:
    weekday = WEEKDAY_CN[now.weekday()]
    date_str = now.strftime("%Y-%m-%d")

    stories = [(t, i) for t, i in items if t == "story"]
    tasks = [(t, i) for t, i in items if t == "task"]
    bugs = [(t, i) for t, i in items if t == "bug"]

    overdue: list[tuple[str, Any]] = []
    near_deadline: list[tuple[str, Any]] = []
    urgent: list[tuple[str, Any]] = []

    for etype, item in items:
        if item.deadline and item.deadline < now:
            overdue.append((etype, item))
        elif item.deadline and item.deadline <= now + timedelta(days=near_days):
            near_deadline.append((etype, item))
        if etype == "bug" and getattr(item, "severity", 4) <= 2:
            urgent.append((etype, item))
        elif etype == "story" and getattr(item, "priority", 4) <= 2:
            urgent.append((etype, item))

    lines: list[str] = [
        f"## {_E_SUN} \u5de5\u4f5c\u7b80\u62a5 \u00b7 {project} \u00b7 {date_str} {weekday}",
        "",
        f"{name}\uff0c\u4ee5\u4e0b\u662f\u4eca\u65e5\u5de5\u4f5c\u6982\u89c8\uff1a",
        "",
        "### \u5f85\u529e\u6982\u89c8",
    ]

    if stories:
        lines.append(f"- \u5f85\u5904\u7406\u9700\u6c42\uff1a**{len(stories)}** \u6761")
    if tasks:
        lines.append(f"- \u8fdb\u884c\u4e2d\u4efb\u52a1\uff1a**{len(tasks)}** \u6761")
    if bugs:
        sev_high = sum(1 for _, b in bugs if getattr(b, "severity", 4) <= 2)
        extra = f"\uff08\u542b **{sev_high}** \u6761\u4e25\u91cd/\u81f4\u547d\uff09" if sev_high else ""
        lines.append(f"- \u5f85\u4fee\u590d\u7f3a\u9677\uff1a**{len(bugs)}** \u6761{extra}")
    if not stories and not tasks and not bugs:
        lines.append("> \u6682\u65e0\u5f85\u529e\u4e8b\u9879")

    top_items = _pick_top_items(items, now, near_days, limit=5)
    if top_items:
        lines.append("")
        lines.append("**\u4eca\u65e5\u91cd\u70b9**")
        for i, (etype, item) in enumerate(top_items, 1):
            label = _item_label(etype, item)
            suffix = _deadline_suffix(item, now)
            lines.append(f"{i}. {label}{suffix}")

    if overdue or near_deadline or urgent:
        lines.append("")
        lines.append("---")
        lines.append(f"### {_E_WARN} \u9700\u8981\u5173\u6ce8")

    if overdue:
        lines.append("")
        lines.append(f"{_E_RED} **\u5df2\u903e\u671f** ({len(overdue)} \u6761)")
        for etype, item in overdue[:5]:
            days = (now - item.deadline).days
            lines.append(f"- {_item_label(etype, item)} \u2014 **\u903e\u671f {days} \u5929**")
        if len(overdue) > 5:
            lines.append(f"- *...\u8fd8\u6709 {len(overdue) - 5} \u6761*")

    if near_deadline:
        lines.append("")
        lines.append(f"{_E_YELLOW} **\u5373\u5c06\u903e\u671f**\uff08{near_days} \u5929\u5185\uff0c{len(near_deadline)} \u6761\uff09")
        for etype, item in near_deadline[:5]:
            days = (item.deadline - now).days
            lines.append(f"- {_item_label(etype, item)} \u2014 \u5269\u4f59 {days} \u5929")
        if len(near_deadline) > 5:
            lines.append(f"- *...\u8fd8\u6709 {len(near_deadline) - 5} \u6761*")

    if urgent:
        lines.append("")
        lines.append(f"{_E_FIRE} **\u7d27\u6025/\u9ad8\u4f18\u672a\u5904\u7406** ({len(urgent)} \u6761)")
        for etype, item in urgent[:5]:
            lines.append(f"- {_item_label(etype, item)}")

    if iter_progress:
        lines.append("")
        lines.append("---")
        lines.append(f"### {_E_CHART} \u8fed\u4ee3\u8fdb\u5c55")
        for ip in iter_progress.values():
            total, done = ip["total"], ip["done"]
            pct = int(done / total * 100) if total else 0
            bar = _progress_bar(pct)
            left = _iter_days_left_str(ip.get("days_left"))
            lines.append(f"- **{ip['name']}** {bar} {pct}% ({done}/{total}){left}")

    suggestions = _build_suggestions(overdue, near_deadline, urgent, iter_progress, near_days)
    if suggestions:
        lines.append("")
        lines.append("---")
        lines.append(f"### {_E_BULB} \u5efa\u8bae")
        for i, s in enumerate(suggestions[:3], 1):
            lines.append(f"{i}. {s}")

    lines.append("")
    lines.extend(_render_footer(site_url, project_id, member_id))
    return "\n".join(lines)


# ------------------------------------------------------------------
# Afternoon check
# ------------------------------------------------------------------

def _render_afternoon(
    name: str, member_id: str, project_id: str, project: str,
    items: list[tuple[str, Any]],
    near_days: int, now: datetime,
    iter_progress: dict, site_url: str,
) -> str:
    date_str = now.strftime("%Y-%m-%d %H:%M")

    overdue = [(t, i) for t, i in items if i.deadline and i.deadline < now]
    today_due = [
        (t, i) for t, i in items
        if i.deadline and i.deadline.date() == now.date() and i.deadline >= now
    ]

    lines: list[str] = [
        f"## {_E_CLOCK} \u5348\u540e\u8fdb\u5ea6\u68c0\u67e5 \u00b7 {project} \u00b7 {date_str}",
        "",
        f"{name}\uff0c\u4e0b\u5348\u597d\uff1a",
        "",
        "### \u4ecd\u9700\u5173\u6ce8",
        f"\u5f85\u529e\u603b\u6570 **{len(items)}** \u6761",
    ]
    if overdue:
        lines.append(f"- {_E_RED} \u5df2\u903e\u671f: **{len(overdue)}** \u6761")
    if today_due:
        lines.append(f"- {_E_WARN} \u4eca\u65e5\u5230\u671f: **{len(today_due)}** \u6761")
        for t, i in today_due[:5]:
            lines.append(f"  - {_item_label(t, i)}")

    if iter_progress:
        lines.append("")
        lines.append("---")
        lines.append(f"### {_E_CHART} \u8fed\u4ee3\u8fdb\u5ea6")
        for ip in iter_progress.values():
            total, done = ip["total"], ip["done"]
            pct = int(done / total * 100) if total else 0
            bar = _progress_bar(pct)
            left = _iter_days_left_str(ip.get("days_left"))
            lines.append(f"- **{ip['name']}** {bar} {pct}% ({done}/{total}){left}")

    if today_due or overdue:
        lines.append("")
        lines.append("---")
        lines.append(f"### {_E_BULB} \u5efa\u8bae")
        if today_due:
            lines.append(f"\u8ddd\u4e0b\u73ed\u8fd8\u6709\u6570\u5c0f\u65f6\uff0c\u4f18\u5148\u5b8c\u6210\u4eca\u65e5\u5230\u671f\u7684 **{len(today_due)}** \u6761\u5de5\u4f5c\u9879\u53ef\u907f\u514d\u903e\u671f\u3002")
        if overdue:
            lines.append(f"\u8fd8\u6709 **{len(overdue)}** \u6761\u5df2\u903e\u671f\uff0c\u5efa\u8bae\u5c3d\u5feb\u5904\u7406\u6216\u8c03\u6574\u6392\u671f\u3002")

    lines.append("")
    lines.extend(_render_footer(site_url, project_id, member_id))
    return "\n".join(lines)


# ------------------------------------------------------------------
# Weekly digest
# ------------------------------------------------------------------

def _render_weekly(
    name: str, member_id: str, project_id: str, project: str,
    items: list[tuple[str, Any]],
    near_days: int, now: datetime,
    iter_progress: dict, site_url: str,
) -> str:
    week_num = now.isocalendar()[1]
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=4)
    date_range = f"{week_start.strftime('%m.%d')} - {week_end.strftime('%m.%d')}"

    overdue: list[tuple[str, Any]] = []
    for etype, item in items:
        if item.deadline and item.deadline < now:
            overdue.append((etype, item))

    lines: list[str] = [
        f"## {_E_CLIPBOARD} \u5468\u5de5\u4f5c\u603b\u7ed3 \u00b7 {project} \u00b7 \u7b2c {week_num} \u5468\uff08{date_range}\uff09",
        "",
        f"{name}\uff0c\u672c\u5468\u6982\u51b5\uff1a",
        "",
        "### \u9057\u7559\u4e8b\u9879",
        f"\u5f85\u529e **{len(items)}** \u6761\uff08\u542b\u903e\u671f **{len(overdue)}** \u6761\uff09",
    ]

    if overdue:
        lines.append("")
        for etype, item in overdue[:5]:
            days = (now - item.deadline).days
            lines.append(f"- {_item_label(etype, item)} \u2014 **\u903e\u671f {days} \u5929**")
        if len(overdue) > 5:
            lines.append(f"- *...\u8fd8\u6709 {len(overdue) - 5} \u6761*")

    if iter_progress:
        lines.append("")
        lines.append("---")
        lines.append(f"### {_E_CHART} \u8fed\u4ee3\u6982\u51b5")
        for ip in iter_progress.values():
            total, done = ip["total"], ip["done"]
            pct = int(done / total * 100) if total else 0
            bar = _progress_bar(pct)
            left = _iter_days_left_str(ip.get("days_left"))
            warn = " **\u9700\u52a0\u901f**" if ip.get("days_left") is not None and ip["days_left"] <= 3 and pct < 80 else ""
            lines.append(f"- **{ip['name']}** {bar} {pct}% ({done}/{total}){left}{warn}")

    lines.append("")
    lines.append("---")
    lines.append(f"### {_E_BULB} \u4e0b\u5468\u5efa\u8bae")
    if overdue:
        lines.append(f"\u903e\u671f **{len(overdue)}** \u6761\u5de5\u4f5c\u9879\u5df2\u62d6\u5ef6\uff0c\u5efa\u8bae\u4e0b\u5468\u4e00\u4f18\u5148\u5904\u7406\u6216\u540c\u6b65\u98ce\u9669\u3002")
    else:
        lines.append("\u672c\u5468\u6e05\u7406\u826f\u597d\uff0c\u7ee7\u7eed\u4fdd\u6301\u8282\u594f\u3002")

    lines.append("")
    lines.extend(_render_footer(site_url, project_id, member_id))
    return "\n".join(lines)


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

_TYPE_LABEL = {"story": "需求", "task": "任务", "bug": "缺陷"}
_TYPE_ROUTE = {"story": "stories", "task": "tasks", "bug": "bugs"}
_TYPE_TAB = {"story": "story", "task": "task", "bug": "bug"}


def _progress_bar(pct: int, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def _item_label(etype: str, item, site_url: str = "", project_id: str = "") -> str:
    tl = _TYPE_LABEL.get(etype, etype)
    extra = ""
    if etype == "bug" and hasattr(item, "severity"):
        extra = f"\u00b7{_SEVERITY_LABEL.get(item.severity, '')}"
    elif etype == "story" and hasattr(item, "priority") and item.priority <= 2:
        extra = f"\u00b7{_PRIORITY_LABEL.get(item.priority, '')}"
    tag = f"[{tl}{extra}]"
    if site_url:
        route = _TYPE_ROUTE.get(etype, "stories")
        tab = _TYPE_TAB.get(etype, etype)
        url = f"{site_url}/vortflow/{route}?project_id={project_id}&action=detail&id={item.id}&tab={tab}"
        return f"[**{tag}** {item.title}]({url})"
    return f"**{tag}** {item.title}"


def _deadline_suffix(item, now: datetime) -> str:
    if not item.deadline:
        return ""
    days = (item.deadline - now).days
    if days < 0:
        return f" \u2014 **\u903e\u671f {-days} \u5929**"
    if days == 0:
        return " \u2014 **\u4eca\u65e5\u5230\u671f**"
    if days <= 3:
        return f" \u2014 \u5269\u4f59 {days} \u5929"
    return ""


def _pick_top_items(
    items: list[tuple[str, Any]], now: datetime, near_days: int, limit: int = 5,
) -> list[tuple[str, Any]]:
    """Pick the most important items: severe bugs > overdue > near-deadline > high-priority."""
    def _sort_key(pair: tuple[str, Any]) -> tuple:
        etype, item = pair
        sev = getattr(item, "severity", 4) if etype == "bug" else 4
        pri = getattr(item, "priority", 4) if etype == "story" else 4
        overdue_days = (now - item.deadline).days if item.deadline and item.deadline < now else -9999
        near = (item.deadline - now).days if item.deadline and item.deadline >= now else 9999
        return (-overdue_days, sev, pri, near)
    return sorted(items, key=_sort_key)[:limit]


def _iter_days_left_str(days_left) -> str:
    if days_left is None:
        return ""
    if days_left < 0:
        return f" \u00b7 **\u5df2\u8d85\u671f {-days_left} \u5929**"
    if days_left == 0:
        return " \u00b7 **\u4eca\u65e5\u622a\u6b62**"
    return f" \u00b7 \u5269\u4f59 **{days_left}** \u5929"


def _render_footer(site_url: str, project_id: str, member_id: str) -> list[str]:
    lines = ["---"]
    if site_url:
        base = f"{site_url}/vortflow"
        qs = f"?project_id={project_id}&assignee_id={member_id}&status=incomplete"
        links = [
            f"[\u67e5\u770b\u6211\u7684\u9700\u6c42]({base}/stories{qs})",
            f"[\u67e5\u770b\u6211\u7684\u4efb\u52a1]({base}/tasks{qs})",
            f"[\u67e5\u770b\u6211\u7684\u7f3a\u9677]({base}/bugs{qs})",
        ]
        lines.append(" \u00b7 ".join(links))
        lines.append("")
    lines.append("*\u7531 OpenVort \u81ea\u52a8\u751f\u6210 \u00b7 \u53ef\u5728\u4e2a\u4eba\u8bbe\u7f6e\u4e2d\u8c03\u6574\u63a5\u6536\u504f\u597d*")
    return lines


def _build_suggestions(
    overdue: list,
    near: list,
    urgent: list,
    iter_progress: dict,
    near_days: int,
) -> list[str]:
    suggestions: list[str] = []
    if urgent:
        suggestions.append("\u7d27\u6025/\u9ad8\u4f18\u5de5\u4f5c\u9879\u5c1a\u672a\u5904\u7406\uff0c\u5efa\u8bae\u6700\u4f18\u5148\u5b89\u6392")
    if overdue:
        suggestions.append(f"\u6709 {len(overdue)} \u6761\u5df2\u903e\u671f\uff0c\u5efa\u8bae\u5c3d\u5feb\u5904\u7406\u6216\u8c03\u6574\u6392\u671f")
    if near:
        suggestions.append(f"{len(near)} \u6761\u5373\u5c06\u5728 {near_days} \u5929\u5185\u5230\u671f\uff0c\u5efa\u8bae\u5408\u7406\u5206\u914d\u65f6\u95f4")
    for ip in iter_progress.values():
        if ip.get("days_left") is not None and ip["days_left"] <= 2:
            total, done = ip["total"], ip["done"]
            pct = int(done / total * 100) if total else 0
            if pct < 70:
                suggestions.append(f"\u8fed\u4ee3\u300c{ip['name']}\u300d\u5373\u5c06\u7ed3\u675f\u4f46\u5b8c\u6210\u7387\u4ec5 {pct}%\uff0c\u5efa\u8bae\u805a\u7126\u51b2\u523a")
    return suggestions


# Module-level singleton
reminder_service = ReminderService()
