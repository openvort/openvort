from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import delete, select, update

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowBug,
    FlowComment,
    FlowEvent,
    FlowIterationBug,
    FlowIterationStory,
    FlowIterationTask,
    FlowStory,
    FlowTask,
    FlowVersionBug,
    FlowVersionStory,
    FlowWorkItemLink,
    _uuid,
)
from openvort.web.app import require_auth

from .helpers import _log_event

sub_router = APIRouter()

_TYPE_LABEL = {"story": "需求", "task": "任务", "bug": "缺陷"}
_TYPE_MODEL = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
_DEFAULT_STATE = {"story": "submitted", "task": "todo", "bug": "open"}

_SHARED_FIELDS = [
    "title", "description", "project_id", "tags_json",
    "collaborators_json", "deadline", "start_at", "end_at",
    "repo_id", "branch", "attachments_json", "created_at",
]


class ConvertBody(BaseModel):
    from_type: str  # story / task / bug
    id: str
    to_type: str  # story / task / bug


def _map_special_fields(src, from_type: str, to_type: str) -> dict:
    """Build target-specific field values from source record."""
    extra: dict = {}

    # --- assignee_id ---
    if from_type == "story":
        extra["assignee_id"] = getattr(src, "pm_id", None) or getattr(src, "assignee_id", None)
    else:
        extra["assignee_id"] = getattr(src, "assignee_id", None)

    # --- priority / severity ---
    if to_type == "story":
        if from_type == "bug":
            extra["priority"] = getattr(src, "severity", 3)
        else:
            extra["priority"] = 3
    elif to_type == "bug":
        if from_type == "story":
            extra["severity"] = getattr(src, "priority", 3)
        else:
            extra["severity"] = getattr(src, "severity", 3) if from_type == "bug" else 3

    # --- estimate_hours / actual_hours ---
    if to_type in ("task", "bug"):
        extra["estimate_hours"] = getattr(src, "estimate_hours", None)
        extra["actual_hours"] = getattr(src, "actual_hours", None)

    # --- story_id (task ↔ bug) ---
    if to_type in ("task", "bug") and from_type in ("task", "bug"):
        extra["story_id"] = getattr(src, "story_id", None)

    # --- submitter / reporter / creator ---
    if to_type == "story":
        extra["submitter_id"] = (
            getattr(src, "reporter_id", None) or
            getattr(src, "creator_id", None) or
            getattr(src, "submitter_id", None)
        )
    elif to_type == "bug":
        extra["reporter_id"] = (
            getattr(src, "submitter_id", None) or
            getattr(src, "creator_id", None) or
            getattr(src, "reporter_id", None)
        )
    elif to_type == "task":
        extra["creator_id"] = (
            getattr(src, "submitter_id", None) or
            getattr(src, "reporter_id", None) or
            getattr(src, "creator_id", None)
        )

    return extra


_ITERATION_LINK = {
    "story": (FlowIterationStory, "story_id", "story_order"),
    "task": (FlowIterationTask, "task_id", "task_order"),
    "bug": (FlowIterationBug, "bug_id", "bug_order"),
}

_VERSION_LINK = {
    "story": (FlowVersionStory, "story_id", "story_order"),
    "bug": (FlowVersionBug, "bug_id", "bug_order"),
}


@sub_router.post("/work-items/convert")
async def convert_work_item(body: ConvertBody, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
    from_type = body.from_type
    to_type = body.to_type

    if from_type not in _TYPE_MODEL or to_type not in _TYPE_MODEL:
        return {"error": "无效的工作项类型"}
    if from_type == to_type:
        return {"error": "源类型和目标类型相同"}

    src_model = _TYPE_MODEL[from_type]
    dst_model = _TYPE_MODEL[to_type]

    sf = get_session_factory()
    async with sf() as session:
        src = await session.get(src_model, body.id)
        if not src:
            return {"error": f"{_TYPE_LABEL.get(from_type, from_type)}不存在"}

        # --- 1. Build target record ---
        new_id = _uuid()
        fields: dict = {"id": new_id, "state": _DEFAULT_STATE[to_type]}
        for f in _SHARED_FIELDS:
            val = getattr(src, f, None)
            if val is not None:
                fields[f] = val
        fields.update(_map_special_fields(src, from_type, to_type))
        dst_obj = dst_model(**fields)
        session.add(dst_obj)

        # --- 2. Migrate iteration links ---
        from_iter = _ITERATION_LINK.get(from_type)
        to_iter = _ITERATION_LINK.get(to_type)
        if from_iter:
            from_iter_model, from_iter_fk, from_iter_order = from_iter
            rows = (await session.execute(
                select(from_iter_model).where(
                    getattr(from_iter_model, from_iter_fk) == body.id
                )
            )).scalars().all()
            if rows and to_iter:
                to_iter_model, to_iter_fk, to_iter_order = to_iter
                for row in rows:
                    link_kwargs = {
                        "iteration_id": row.iteration_id,
                        to_iter_fk: new_id,
                        to_iter_order: getattr(row, from_iter_order, 0),
                    }
                    session.add(to_iter_model(**link_kwargs))
            await session.execute(
                delete(from_iter_model).where(
                    getattr(from_iter_model, from_iter_fk) == body.id
                )
            )

        # --- 3. Migrate version links ---
        from_ver = _VERSION_LINK.get(from_type)
        to_ver = _VERSION_LINK.get(to_type)
        if from_ver:
            from_ver_model, from_ver_fk, from_ver_order = from_ver
            ver_rows = (await session.execute(
                select(from_ver_model).where(
                    getattr(from_ver_model, from_ver_fk) == body.id
                )
            )).scalars().all()
            if ver_rows and to_ver:
                to_ver_model, to_ver_fk, to_ver_order = to_ver
                for vrow in ver_rows:
                    ver_kwargs = {
                        "version_id": vrow.version_id,
                        to_ver_fk: new_id,
                        to_ver_order: getattr(vrow, from_ver_order, 0),
                    }
                    session.add(to_ver_model(**ver_kwargs))
            await session.execute(
                delete(from_ver_model).where(
                    getattr(from_ver_model, from_ver_fk) == body.id
                )
            )

        # --- 4. Migrate comments ---
        await session.execute(
            update(FlowComment)
            .where(FlowComment.entity_type == from_type, FlowComment.entity_id == body.id)
            .values(entity_type=to_type, entity_id=new_id)
        )

        # --- 5. Migrate events ---
        await session.execute(
            update(FlowEvent)
            .where(FlowEvent.entity_type == from_type, FlowEvent.entity_id == body.id)
            .values(entity_type=to_type, entity_id=new_id)
        )

        # --- 6. Migrate work-item links ---
        await session.execute(
            update(FlowWorkItemLink)
            .where(FlowWorkItemLink.source_type == from_type, FlowWorkItemLink.source_id == body.id)
            .values(source_type=to_type, source_id=new_id)
        )
        await session.execute(
            update(FlowWorkItemLink)
            .where(FlowWorkItemLink.target_type == from_type, FlowWorkItemLink.target_id == body.id)
            .values(target_type=to_type, target_id=new_id)
        )

        # --- 7. Detach FK references before deleting source ---
        if from_type == "story":
            await session.execute(
                update(FlowTask).where(FlowTask.story_id == body.id).values(story_id=None)
            )
            await session.execute(
                update(FlowBug).where(FlowBug.story_id == body.id).values(story_id=None)
            )
            await session.execute(
                update(FlowStory).where(FlowStory.parent_id == body.id).values(parent_id=None)
            )
        elif from_type == "task":
            await session.execute(
                update(FlowBug).where(FlowBug.task_id == body.id).values(task_id=None)
            )
            await session.execute(
                update(FlowTask).where(FlowTask.parent_id == body.id).values(parent_id=None)
            )

        await session.delete(src)

        # --- 8. Log conversion event ---
        await _log_event(
            session, to_type, new_id, "converted",
            {
                "from_type": from_type,
                "from_id": body.id,
                "to_type": to_type,
                "title": getattr(src, "title", ""),
            },
            actor_id=actor_id,
        )

        await session.commit()

    return {
        "new_id": new_id,
        "new_type": to_type,
        "message": f"已将{_TYPE_LABEL.get(from_type, from_type)}转换为{_TYPE_LABEL.get(to_type, to_type)}",
    }
