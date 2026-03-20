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
        summary = f"{label}「{title}」已创建"
        data = {
            "action": "created",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
        }
        await self._fan_out(recipients, f"新{label}", summary, entity_id, data)

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
        summary = f"{label}「{title}」状态变更: {from_state} -> {to_state}"
        data = {
            "action": "state_changed",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
            "from_state": from_state,
            "to_state": to_state,
        }
        await self._fan_out(recipients, "状态变更", summary, entity_id, data)

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
        summary = f"你被分配为{label}「{title}」的负责人"
        data = {
            "action": "assigned",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
        }
        await self._fan_out(recipients, "任务分配", summary, entity_id, data)

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
            summary = f"{label}「{title}」有新评论: {content_preview}"
            await self._fan_out(non_mention, "新评论", summary, entity_id, data)

        extra_mentions = [m for m in mention_set if m not in base_recipients]
        all_mentions = list(mention_set)
        if all_mentions:
            summary = f"你在{label}「{title}」中被提及: {content_preview}"
            await self._fan_out(all_mentions, "你被提及", summary, entity_id, data)

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
        summary = f"你被添加为{label}「{title}」的协作人"
        data = {
            "action": "collaborator_added",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
        }
        await self._fan_out(recipients, "协作人变更", summary, entity_id, data)

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

        lines = []
        for field, (old_val, new_val) in changes.items():
            field_label = _FIELD_LABEL.get(field, field)
            old_display = self._format_field_value(field, old_val)
            new_display = self._format_field_value(field, new_val)
            lines.append(f"{field_label}: {old_display} -> {new_display}")

        summary = f"{label}「{title}」" + "，".join(lines)
        data = {
            "action": "field_changed",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
            "fields": list(changes.keys()),
        }
        await self._fan_out(recipients, "字段变更", summary, entity_id, data)

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
    ) -> None:
        entity_type = data.get("entity_type", "")
        entity_id = data.get("entity_id", "")
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
                    source_id=source_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                ),
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
