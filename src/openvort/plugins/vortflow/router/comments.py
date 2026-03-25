import json

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowComment,
    FlowEvent,
    FlowStory,
    FlowTask,
    FlowBug,
)
from openvort.plugins.vortflow.notifier import notifier as _notifier, schedule_notification
from openvort.web.app import require_auth

from .helpers import _log_event, _parse_json_list

_ENTITY_MODEL = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}

sub_router = APIRouter()


class CommentCreate(BaseModel):
    content: str
    mentions: list[str] = []


class CommentUpdate(BaseModel):
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
    item_title = ""
    item_project_id = ""
    item_assignee_id: str | None = None
    item_creator_id: str | None = None
    item_collaborators: list[str] = []
    async with sf() as session:
        model = _ENTITY_MODEL.get(entity_type)
        if model:
            item = await session.get(model, entity_id)
            if item:
                item_title = getattr(item, "title", "")
                item_project_id = getattr(item, "project_id", "") or ""
                item_assignee_id = getattr(item, "assignee_id", None) or getattr(item, "pm_id", None)
                item_creator_id = getattr(item, "creator_id", None) or getattr(item, "submitter_id", None) or getattr(item, "reporter_id", None)
                item_collaborators = _parse_json_list(getattr(item, "collaborators_json", "[]"))
        c = FlowComment(
            entity_type=entity_type,
            entity_id=entity_id,
            author_id=member_id,
            content=body.content,
            mentions_json=json.dumps(body.mentions or [], ensure_ascii=False),
        )
        session.add(c)
        await _log_event(session, entity_type, entity_id, "comment_added",
                         {"author_id": member_id, "preview": body.content[:100]},
                         actor_id=member_id)
        await session.commit()
        await session.refresh(c)
    schedule_notification(_notifier.notify_comment(
        entity_type, entity_id, item_title, item_project_id, member_id,
        content_preview=body.content[:50],
        mention_ids=body.mentions,
        assignee_id=item_assignee_id,
        creator_id=item_creator_id,
        collaborator_ids=item_collaborators,
    ))
    return {
        "id": c.id, "entity_type": c.entity_type, "entity_id": c.entity_id,
        "author_id": c.author_id, "content": c.content,
        "mentions": _parse_json_list(c.mentions_json),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@sub_router.patch("/comments/{comment_id}")
async def update_comment(comment_id: int, body: CommentUpdate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        c = await session.get(FlowComment, comment_id)
        if not c:
            return {"error": "评论不存在"}
        if c.author_id != member_id:
            return {"error": "只能编辑自己的评论"}
        c.content = body.content
        c.mentions_json = json.dumps(body.mentions or [], ensure_ascii=False)
        await _log_event(session, c.entity_type, c.entity_id, "comment_updated",
                         {"author_id": member_id, "comment_id": comment_id, "preview": body.content[:100]},
                         actor_id=member_id)
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
