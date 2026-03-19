"""VortFlow notification layer — DB persistence + WebSocket push."""

from __future__ import annotations

import asyncio
import json

from openvort.plugins.vortflow.aggregator import NotificationPayload, im_aggregator
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.notifier")


_ENTITY_TYPE_LABEL = {
    "story": "需求",
    "task": "任务",
    "bug": "缺陷",
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
        }
        await self._fan_out(recipients, "任务分配", summary, entity_id, data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
                await self._persist(rid, title, summary, source_id)
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
