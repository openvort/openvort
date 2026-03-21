"""Notification center API — list, filter, batch-read notifications."""

import json

from fastapi import APIRouter, Request
from pydantic import BaseModel

from openvort.web.app import require_auth
from openvort.utils.logging import get_logger

log = get_logger("web.notifications")

router = APIRouter()


def _safe_json(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


@router.get("")
async def list_notifications(
    request: Request,
    status: str = "all",
    source: str = "",
    page: int = 1,
    limit: int = 20,
):
    """List notifications for the current user with optional filters."""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    from sqlalchemy import select, func, desc
    from openvort.db.models import Notification
    from openvort.web.deps import get_db_session_factory

    sf = get_db_session_factory()
    async with sf() as db:
        base = select(Notification).where(Notification.recipient_id == member_id)
        if status != "all":
            base = base.where(Notification.status == status)
        if source:
            base = base.where(Notification.source == source)

        count_result = await db.execute(select(func.count()).select_from(base.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * limit
        stmt = base.order_by(desc(Notification.created_at)).offset(offset).limit(limit)
        result = await db.execute(stmt)
        rows = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "notifications": [
            {
                "id": n.id,
                "source": n.source,
                "source_id": n.source_id,
                "session_id": n.session_id,
                "title": n.title,
                "summary": n.summary,
                "status": n.status,
                "im_channel": n.im_channel,
                "data": _safe_json(getattr(n, "data_json", "{}")),
                "created_at": n.created_at.isoformat() if n.created_at else "",
                "read_at": n.read_at.isoformat() if n.read_at else "",
            }
            for n in rows
        ],
    }


@router.get("/unread-count")
async def unread_count(request: Request, source: str = ""):
    """Get unread notification count for the current user."""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    from sqlalchemy import select, func
    from openvort.db.models import Notification
    from openvort.web.deps import get_db_session_factory

    sf = get_db_session_factory()
    async with sf() as db:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_id == member_id,
                Notification.status.in_(["pending", "sent"]),
            )
        )
        if source:
            stmt = stmt.where(Notification.source == source)
        total = (await db.execute(stmt)).scalar() or 0

    return {"count": total}


class BatchReadRequest(BaseModel):
    notification_ids: list[int] = []
    all: bool = False


@router.post("/batch-read")
async def batch_read(req: BatchReadRequest, request: Request):
    """Mark notifications as read (by IDs or all)."""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    from sqlalchemy import update
    from datetime import datetime
    from openvort.db.models import Notification
    from openvort.web.deps import get_db_session_factory

    sf = get_db_session_factory()
    async with sf() as db:
        base = (
            update(Notification)
            .where(Notification.recipient_id == member_id)
            .where(Notification.status.in_(["pending", "sent"]))
        )
        if not req.all and req.notification_ids:
            base = base.where(Notification.id.in_(req.notification_ids))
        result = await db.execute(base.values(status="read", read_at=datetime.utcnow()))
        await db.commit()

    return {"success": True, "count": result.rowcount}
