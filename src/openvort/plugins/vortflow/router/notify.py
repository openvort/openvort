"""Manual notification endpoint — remind / urge work item participants."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from openvort.web.app import require_auth
from openvort.plugins.vortflow.notifier import notifier as _notifier, schedule_notification
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.router.notify")

sub_router = APIRouter()


class NotifyRequest(BaseModel):
    entity_type: str  # story / task / bug
    entity_id: str
    title: str
    project_id: str = ""
    notify_type: str = "remind"  # remind / urge
    recipient_ids: list[str] = []
    message: str = ""


@sub_router.post("/notify")
async def send_notify(body: NotifyRequest, request: Request):
    """Send a manual reminder or urge notification to specified recipients."""
    payload = require_auth(request)
    actor_id = payload.get("sub") or payload.get("member_id", "")

    if not body.recipient_ids:
        return {"success": False, "error": "recipient_ids is empty"}
    if body.notify_type not in ("remind", "urge"):
        return {"success": False, "error": "notify_type must be remind or urge"}

    schedule_notification(
        _notifier.notify_manual(
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            title=body.title,
            project_id=body.project_id,
            actor_id=actor_id,
            recipient_ids=body.recipient_ids,
            notify_type=body.notify_type,
            custom_message=body.message,
        )
    )

    return {"success": True}
