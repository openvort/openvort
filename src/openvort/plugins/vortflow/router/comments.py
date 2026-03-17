import json

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import FlowComment, FlowEvent
from openvort.web.app import require_auth

from .helpers import _log_event, _parse_json_list

sub_router = APIRouter()


class CommentCreate(BaseModel):
    content: str
    mentions: list[str] = []


@sub_router.get("/comments/{entity_type}/{entity_id}")
async def list_comments(entity_type: str, entity_id: str):
    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowComment)
            .where(FlowComment.entity_type == entity_type, FlowComment.entity_id == entity_id)
            .order_by(FlowComment.created_at.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
    return {"items": [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "author_id": r.author_id, "content": r.content,
            "mentions": _parse_json_list(r.mentions_json),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]}


@sub_router.post("/comments/{entity_type}/{entity_id}")
async def create_comment(entity_type: str, entity_id: str, body: CommentCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        c = FlowComment(
            entity_type=entity_type,
            entity_id=entity_id,
            author_id=member_id,
            content=body.content,
            mentions_json=json.dumps(body.mentions or [], ensure_ascii=False),
        )
        session.add(c)
        await _log_event(session, entity_type, entity_id, "comment_added",
                         {"author_id": member_id, "preview": body.content[:100]})
        await session.commit()
        await session.refresh(c)
    return {
        "id": c.id, "entity_type": c.entity_type, "entity_id": c.entity_id,
        "author_id": c.author_id, "content": c.content,
        "mentions": _parse_json_list(c.mentions_json),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@sub_router.get("/activity/{entity_type}/{entity_id}")
async def list_activity(entity_type: str, entity_id: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowEvent)
            .where(FlowEvent.entity_type == entity_type, FlowEvent.entity_id == entity_id)
            .order_by(FlowEvent.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        rows = (await session.execute(stmt)).scalars().all()
    return {"items": [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "action": r.action, "actor_id": r.actor_id,
            "detail": r.detail,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]}
