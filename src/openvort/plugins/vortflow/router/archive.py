"""Batch archive / unarchive work items with cascade."""

from fastapi import APIRouter, Request
from sqlalchemy import select, update as sa_update

from openvort.db.engine import get_session_factory
from openvort.web.app import require_auth
from openvort.plugins.vortflow.router.helpers import _log_event, _collect_story_descendant_ids
from openvort.plugins.vortflow.router.schemas import BatchArchiveBody
from openvort.plugins.vortflow.models import FlowStory, FlowTask, FlowBug

sub_router = APIRouter()


@sub_router.post("/work-items/batch-archive")
async def batch_archive(body: BatchArchiveBody, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
    if not body.ids:
        return {"ok": True, "count": 0}
    if body.type not in ("story", "task", "bug"):
        return {"error": f"无效类型: {body.type}"}

    sf = get_session_factory()
    async with sf() as session:
        affected = 0
        action = "archived" if body.archived else "unarchived"

        if body.type == "story":
            descendant_ids = await _collect_story_descendant_ids(session, body.ids)
            all_story_ids = list(set(body.ids) | set(descendant_ids))

            res = await session.execute(
                sa_update(FlowStory)
                .where(FlowStory.id.in_(all_story_ids))
                .values(is_archived=body.archived)
            )
            affected += res.rowcount or 0

            # cascade to tasks under these stories
            await session.execute(
                sa_update(FlowTask)
                .where(FlowTask.story_id.in_(all_story_ids))
                .values(is_archived=body.archived)
            )
            # cascade to bugs under these stories
            await session.execute(
                sa_update(FlowBug)
                .where(FlowBug.story_id.in_(all_story_ids))
                .values(is_archived=body.archived)
            )

            for sid in body.ids:
                await _log_event(session, "story", sid, action, {
                    "cascaded_stories": len(descendant_ids),
                }, actor_id=actor_id)

        elif body.type == "task":
            all_task_ids = list(body.ids)
            for tid in body.ids:
                child_ids = list(
                    (await session.execute(
                        select(FlowTask.id).where(FlowTask.parent_id == tid)
                    )).scalars().all()
                )
                all_task_ids.extend(child_ids)
            all_task_ids = list(set(all_task_ids))

            res = await session.execute(
                sa_update(FlowTask)
                .where(FlowTask.id.in_(all_task_ids))
                .values(is_archived=body.archived)
            )
            affected += res.rowcount or 0

            for tid in body.ids:
                await _log_event(session, "task", tid, action, {}, actor_id=actor_id)

        elif body.type == "bug":
            res = await session.execute(
                sa_update(FlowBug)
                .where(FlowBug.id.in_(body.ids))
                .values(is_archived=body.archived)
            )
            affected += res.rowcount or 0

            for bid in body.ids:
                await _log_event(session, "bug", bid, action, {}, actor_id=actor_id)

        await session.commit()

    return {"ok": True, "count": affected}
