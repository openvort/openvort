"""VortFlow notification layer — DB persistence + WebSocket push."""

from __future__ import annotations

import asyncio
import json

from openvort.plugins.vortflow.aggregator import NotificationPayload, im_aggregator
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.notifier")

_background_tasks: set[asyncio.Task] = set()


def schedule_notification(coro) -> None:
    """Fire-and-forget with strong reference + error logging."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_task_done)


def _task_done(task: asyncio.Task) -> None:
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        log.error("notification background task failed: %s", exc, exc_info=exc)


_ENTITY_TYPE_LABEL = {
    "story": "需求",
    "task": "任务",
    "bug": "缺陷",
}

_PRIORITY_LABEL = {1: "紧急", 2: "高", 3: "中", 4: "低"}
_SEVERITY_LABEL = {1: "致命", 2: "严重", 3: "一般", 4: "轻微"}

_FIELD_LABEL = {
    "priority": "优先级",
    "deadline": "截止日期",
    "severity": "严重程度",
    "iteration_id": "所属迭代",
}


class Notifier:
    """Writes to the notifications table and pushes via WebSocket."""

    def __init__(self):
        self._ws_manager = None

    def set_ws_manager(self, ws_manager) -> None:
        self._ws_manager = ws_manager

    # ------------------------------------------------------------------
    # Context resolution (single DB session for all lookups)
    # ------------------------------------------------------------------

    @staticmethod
    async def _resolve_context(
        *,
        actor_id: str = "",
        project_id: str = "",
        entity_type: str = "",
        entity_id: str = "",
    ) -> dict:
        """Resolve actor name, project name, and optional item fields."""
        from openvort.db.engine import get_session_factory

        ctx: dict = {
            "actor_name": "", "project_name": "",
            "priority": None, "severity": None,
            "deadline": None, "assignee_name": "",
        }
        try:
            sf = get_session_factory()
            async with sf() as session:
                if actor_id:
                    from openvort.contacts.models import Member
                    m = await session.get(Member, actor_id)
                    ctx["actor_name"] = m.name if m else ""
                if project_id:
                    from openvort.plugins.vortflow.models import FlowProject
                    p = await session.get(FlowProject, project_id)
                    ctx["project_name"] = p.name if p else ""
                if entity_type and entity_id:
                    from openvort.plugins.vortflow.models import (
                        FlowBug, FlowStory, FlowTask,
                    )
                    model = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}.get(entity_type)
                    if model:
                        item = await session.get(model, entity_id)
                        if item:
                            ctx["priority"] = getattr(item, "priority", None)
                            ctx["severity"] = getattr(item, "severity", None)
                            dl = getattr(item, "deadline", None)
                            ctx["deadline"] = dl.strftime("%Y-%m-%d") if dl else None
                            aid = getattr(item, "assignee_id", None) or getattr(item, "pm_id", None)
                            if aid:
                                from openvort.contacts.models import Member as _M
                                a = await session.get(_M, aid)
                                ctx["assignee_name"] = a.name if a else ""
        except Exception as exc:
            log.warning("_resolve_context error: %s", exc)
        return ctx

    # ------------------------------------------------------------------
    # IM text helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _im_header(title: str, project_name: str) -> str:
        return f"【{title}】{project_name}" if project_name else f"【{title}】"

    @staticmethod
    def _build_item_url(entity_type: str, entity_id: str, project_id: str) -> str:
        from openvort.config.settings import get_settings

        path_map = {"story": "stories", "task": "tasks", "bug": "bugs"}
        path = path_map.get(entity_type, "")
        if not path:
            return ""

        settings = get_settings()
        site_url = (settings.web.site_url or "").rstrip("/")
        if not site_url:
            host = settings.web.host or "localhost"
            if host in ("0.0.0.0", "::", ""):
                host = "localhost"
            site_url = f"http://{host}:{settings.web.port}"
        return f"{site_url}/vortflow/{path}?project_id={project_id}&action=detail&id={entity_id}"

    # ------------------------------------------------------------------
    # Public notification helpers
    # ------------------------------------------------------------------

    async def notify_item_created(
        self,
        entity_type: str,
        entity_id: str,
        title: str,
        project_id: str,
        actor_id: str,
        assignee_id: str | None = None,
        collaborator_ids: list[str] | None = None,
    ) -> None:
        label = _ENTITY_TYPE_LABEL.get(entity_type, entity_type)
        recipients = self._collect_recipients(
            actor_id, assignee_id=assignee_id, collaborator_ids=collaborator_ids,
        )
        if not recipients:
            return

        ctx = await self._resolve_context(
            actor_id=actor_id, project_id=project_id,
            entity_type=entity_type, entity_id=entity_id,
        )
        actor = ctx["actor_name"] or "某人"
        proj = ctx["project_name"]

        summary = f"{actor} 创建了{label}「{title}」"

        im_lines = [self._im_header(f"新{label}", proj)]
        im_lines.append(f"{actor} 创建了{label}「{title}」")
        extras: list[str] = []
        if entity_type == "bug" and ctx["severity"]:
            extras.append(f"严重程度: {_SEVERITY_LABEL.get(ctx['severity'], str(ctx['severity']))}")
        if ctx["priority"]:
            extras.append(f"优先级: {_PRIORITY_LABEL.get(ctx['priority'], str(ctx['priority']))}")
        if ctx["assignee_name"]:
            extras.append(f"负责人: {ctx['assignee_name']}")
        if extras:
            im_lines.append(" | ".join(extras))
        im_text = "\n".join(im_lines)

        data = {
            "action": "created",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
        }
        await self._fan_out(recipients, f"新{label}", summary, entity_id, data, im_text=im_text)

    async def notify_state_change(
        self,
        entity_type: str,
        entity_id: str,
        title: str,
        actor_id: str,
        from_state: str,
        to_state: str,
        assignee_id: str | None = None,
        collaborator_ids: list[str] | None = None,
        creator_id: str | None = None,
        project_id: str = "",
    ) -> None:
        label = _ENTITY_TYPE_LABEL.get(entity_type, entity_type)
        recipients = self._collect_recipients(
            actor_id,
            assignee_id=assignee_id,
            collaborator_ids=collaborator_ids,
            creator_id=creator_id,
        )
        if not recipients:
            return

        ctx = await self._resolve_context(actor_id=actor_id, project_id=project_id)
        actor = ctx["actor_name"] or "某人"
        proj = ctx["project_name"]

        summary = f"{actor} 将{label}「{title}」变更为「{to_state}」"

        im_lines = [self._im_header("状态变更", proj)]
        im_lines.append(f"{actor} 将{label}「{title}」从「{from_state}」变更为「{to_state}」")
        im_text = "\n".join(im_lines)

        data = {
            "action": "state_changed",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
            "from_state": from_state,
            "to_state": to_state,
        }
        await self._fan_out(recipients, "状态变更", summary, entity_id, data, im_text=im_text)

    async def notify_assignment(
        self,
        entity_type: str,
        entity_id: str,
        title: str,
        actor_id: str,
        new_assignee_id: str,
        project_id: str = "",
    ) -> None:
        label = _ENTITY_TYPE_LABEL.get(entity_type, entity_type)
        recipients = self._collect_recipients(actor_id, assignee_id=new_assignee_id)
        if not recipients:
            return

        ctx = await self._resolve_context(
            actor_id=actor_id, project_id=project_id,
            entity_type=entity_type, entity_id=entity_id,
        )
        actor = ctx["actor_name"] or "某人"
        proj = ctx["project_name"]

        summary = f"{actor} 将你分配为{label}「{title}」的负责人"

        im_lines = [self._im_header("任务分配", proj)]
        im_lines.append(f"{actor} 将你分配为{label}「{title}」的负责人")
        extras: list[str] = []
        if ctx["priority"]:
            extras.append(f"优先级: {_PRIORITY_LABEL.get(ctx['priority'], str(ctx['priority']))}")
        if ctx["deadline"]:
            extras.append(f"截止日期: {ctx['deadline']}")
        if extras:
            im_lines.append(" | ".join(extras))
        im_text = "\n".join(im_lines)

        data = {
            "action": "assigned",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
        }
        await self._fan_out(recipients, "任务分配", summary, entity_id, data, im_text=im_text)

    async def notify_comment(
        self,
        entity_type: str,
        entity_id: str,
        title: str,
        project_id: str,
        author_id: str,
        content_preview: str,
        mention_ids: list[str] | None = None,
        assignee_id: str | None = None,
        creator_id: str | None = None,
        collaborator_ids: list[str] | None = None,
    ) -> None:
        label = _ENTITY_TYPE_LABEL.get(entity_type, entity_type)

        ctx = await self._resolve_context(actor_id=author_id, project_id=project_id)
        actor = ctx["actor_name"] or "某人"
        proj = ctx["project_name"]

        data = {
            "action": "commented",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
        }

        base_recipients = self._collect_recipients(
            author_id,
            assignee_id=assignee_id,
            creator_id=creator_id,
            collaborator_ids=collaborator_ids,
        )
        mention_set = set(mention_ids or [])
        mention_set.discard(author_id)

        non_mention = [r for r in base_recipients if r not in mention_set]
        if non_mention:
            summary = f"{actor} 在{label}「{title}」中评论"
            im_lines = [self._im_header("新评论", proj)]
            im_lines.append(f"{actor} 在{label}「{title}」中评论:")
            im_lines.append(f'"{content_preview}"')
            im_text = "\n".join(im_lines)
            await self._fan_out(
                non_mention, "新评论", summary, entity_id, data,
                im_text=im_text, immediate=True,
            )

        all_mentions = list(mention_set)
        if all_mentions:
            summary = f"{actor} 在{label}「{title}」中提到了你"
            im_lines = [self._im_header("你被提及", proj)]
            im_lines.append(f"{actor} 在{label}「{title}」中提到了你:")
            im_lines.append(f'"{content_preview}"')
            im_text = "\n".join(im_lines)
            await self._fan_out(
                all_mentions, "你被提及", summary, entity_id, data,
                im_text=im_text, immediate=True,
            )

    async def notify_collaborator_added(
        self,
        entity_type: str,
        entity_id: str,
        title: str,
        project_id: str,
        actor_id: str,
        new_collaborator_ids: list[str],
    ) -> None:
        label = _ENTITY_TYPE_LABEL.get(entity_type, entity_type)
        recipients = [c for c in new_collaborator_ids if c and c != actor_id]
        if not recipients:
            return

        ctx = await self._resolve_context(actor_id=actor_id, project_id=project_id)
        actor = ctx["actor_name"] or "某人"
        proj = ctx["project_name"]

        summary = f"{actor} 将你添加为{label}「{title}」的协作人"

        im_lines = [self._im_header("协作人变更", proj)]
        im_lines.append(f"{actor} 将你添加为{label}「{title}」的协作人")
        im_text = "\n".join(im_lines)

        data = {
            "action": "collaborator_added",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
        }
        await self._fan_out(recipients, "协作人变更", summary, entity_id, data, im_text=im_text)

    async def notify_manual(
        self,
        entity_type: str,
        entity_id: str,
        title: str,
        project_id: str,
        actor_id: str,
        recipient_ids: list[str],
        notify_type: str = "remind",
        custom_message: str = "",
    ) -> None:
        """Send a manual reminder/urge notification to specified recipients."""
        label = _ENTITY_TYPE_LABEL.get(entity_type, entity_type)
        recipients = [r for r in recipient_ids if r and r != actor_id]
        if not recipients:
            return

        ctx = await self._resolve_context(
            actor_id=actor_id, project_id=project_id,
            entity_type=entity_type, entity_id=entity_id,
        )
        actor = ctx["actor_name"] or "某人"
        proj = ctx["project_name"]

        if notify_type == "urge":
            notif_title = "催办"
            summary = f"{actor} 催促你处理{label}「{title}」"
            im_header = self._im_header("催办", proj)
            im_action = f"{actor} 催促你尽快处理{label}「{title}」"
        else:
            notif_title = "提醒"
            summary = f"{actor} 提醒你关注{label}「{title}」"
            im_header = self._im_header("提醒", proj)
            im_action = f"{actor} 提醒你关注{label}「{title}」"

        im_lines = [im_header, im_action]
        extras: list[str] = []
        if ctx["priority"]:
            extras.append(f"优先级: {_PRIORITY_LABEL.get(ctx['priority'], str(ctx['priority']))}")
        if entity_type == "bug" and ctx["severity"]:
            extras.append(f"严重程度: {_SEVERITY_LABEL.get(ctx['severity'], str(ctx['severity']))}")
        if ctx["deadline"]:
            extras.append(f"截止日期: {ctx['deadline']}")
        if extras:
            im_lines.append(" | ".join(extras))
        if custom_message:
            im_lines.append(f"附言: {custom_message}")
        im_text = "\n".join(im_lines)

        data = {
            "action": notify_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
        }
        await self._fan_out(recipients, notif_title, summary, entity_id, data, im_text=im_text)

    async def notify_field_changes(
        self,
        entity_type: str,
        entity_id: str,
        title: str,
        project_id: str,
        actor_id: str,
        changes: dict[str, tuple],
        assignee_id: str | None = None,
        creator_id: str | None = None,
        collaborator_ids: list[str] | None = None,
    ) -> None:
        label = _ENTITY_TYPE_LABEL.get(entity_type, entity_type)
        recipients = self._collect_recipients(
            actor_id,
            assignee_id=assignee_id,
            creator_id=creator_id,
            collaborator_ids=collaborator_ids,
        )
        if not recipients:
            return

        ctx = await self._resolve_context(actor_id=actor_id, project_id=project_id)
        actor = ctx["actor_name"] or "某人"
        proj = ctx["project_name"]

        field_names = [_FIELD_LABEL.get(f, f) for f in changes]
        summary = f"{actor} 修改了{label}「{title}」的{'、'.join(field_names)}"

        im_lines = [self._im_header("字段变更", proj)]
        if len(changes) == 1:
            field, (old_val, new_val) = next(iter(changes.items()))
            fl = _FIELD_LABEL.get(field, field)
            im_lines.append(
                f"{actor} 修改了{label}「{title}」的{fl}: "
                f"{self._format_field_value(field, old_val)} → {self._format_field_value(field, new_val)}"
            )
        else:
            im_lines.append(f"{actor} 修改了{label}「{title}」:")
            for field, (old_val, new_val) in changes.items():
                fl = _FIELD_LABEL.get(field, field)
                im_lines.append(
                    f"· {fl}: {self._format_field_value(field, old_val)} → "
                    f"{self._format_field_value(field, new_val)}"
                )
        im_text = "\n".join(im_lines)

        data = {
            "action": "field_changed",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
            "fields": list(changes.keys()),
        }
        await self._fan_out(recipients, "字段变更", summary, entity_id, data, im_text=im_text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_field_value(field: str, value) -> str:
        if value is None or value == "":
            return "未设置"
        if field == "priority":
            return _PRIORITY_LABEL.get(value, str(value))
        if field == "severity":
            return _SEVERITY_LABEL.get(value, str(value))
        return str(value)

    @staticmethod
    def _collect_recipients(
        actor_id: str,
        *,
        assignee_id: str | None = None,
        collaborator_ids: list[str] | None = None,
        creator_id: str | None = None,
    ) -> list[str]:
        ids: set[str] = set()
        if assignee_id:
            ids.add(assignee_id)
        if creator_id:
            ids.add(creator_id)
        for cid in (collaborator_ids or []):
            if cid:
                ids.add(cid)
        ids.discard(actor_id)
        return list(ids)

    async def _fan_out(
        self,
        recipients: list[str],
        title: str,
        summary: str,
        source_id: str,
        data: dict,
        *,
        im_text: str = "",
        immediate: bool = False,
    ) -> None:
        entity_type = data.get("entity_type", "")
        entity_id = data.get("entity_id", "")
        project_id = data.get("project_id", "")

        item_url = self._build_item_url(entity_type, entity_id, project_id)
        if item_url and im_text:
            im_text = f"{im_text}\n查看详情: {item_url}"

        for rid in recipients:
            try:
                await self._persist(rid, title, summary, source_id, data)
            except Exception as exc:
                log.warning("notification db write failed for %s: %s", rid, exc)
            try:
                await self._ws_push(rid, title, summary, data)
            except Exception as exc:
                log.warning("ws push failed for %s: %s", rid, exc)
            await im_aggregator.enqueue(
                rid,
                NotificationPayload(
                    title=title,
                    summary=summary,
                    im_text=im_text or f"【{title}】\n{summary}",
                    source_id=source_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                ),
                immediate=immediate,
            )

    async def _persist(
        self, recipient_id: str, title: str, summary: str, source_id: str,
        data: dict | None = None,
    ) -> None:
        from openvort.db.engine import get_session_factory
        from openvort.db.models import Notification

        sf = get_session_factory()
        async with sf() as session:
            session.add(Notification(
                recipient_id=recipient_id,
                source="vortflow",
                source_id=source_id,
                title=title,
                summary=summary,
                status="pending",
                data_json=json.dumps(data or {}, ensure_ascii=False),
            ))
            await session.commit()

    async def _ws_push(
        self, member_id: str, title: str, summary: str, data: dict,
    ) -> None:
        ws = getattr(self, "_ws_manager", None)
        if ws is None:
            return
        payload = {
            "type": "vortflow_notification",
            "title": title,
            "message": summary,
            "data": data,
        }
        try:
            await ws.send_to(member_id, payload)
        except Exception as exc:
            log.warning("ws send_to %s error: %s", member_id, exc)


# Module-level singleton for easy import in router.py
notifier = Notifier()
