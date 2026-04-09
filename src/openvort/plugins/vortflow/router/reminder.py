"""VortFlow reminder settings API router."""

import json

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import FlowProject, FlowReminderSettings
from openvort.plugins.vortflow.reminder import DEFAULT_SCENES, reminder_service

sub_router = APIRouter()


class ReminderSettingsBody(BaseModel):
    enabled: bool = False
    scenes: dict = {}
    work_days: str = "1,2,3,4,5"
    near_deadline_days: int = 3
    ai_suggestion: bool = True
    skip_empty: bool = True
    min_threshold: int = 0


class BulkReminderSettingsBody(BaseModel):
    project_ids: list[str] = []
    enabled: bool = False
    scenes: dict = {}
    work_days: str = "1,2,3,4,5"
    near_deadline_days: int = 3
    ai_suggestion: bool = True
    skip_empty: bool = True
    min_threshold: int = 0


def _setting_dict(s: FlowReminderSettings) -> dict:
    scenes = {}
    try:
        scenes = json.loads(s.scenes_json) if s.scenes_json else {}
    except (json.JSONDecodeError, TypeError):
        pass
    merged = {**DEFAULT_SCENES}
    for k, v in scenes.items():
        if k in merged:
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return {
        "id": s.id,
        "project_id": s.project_id,
        "enabled": s.enabled,
        "scenes": merged,
        "work_days": s.work_days or "1,2,3,4,5",
        "near_deadline_days": s.near_deadline_days,
        "ai_suggestion": s.ai_suggestion,
        "skip_empty": s.skip_empty,
        "min_threshold": s.min_threshold,
    }


@sub_router.get("/reminder-settings")
async def list_reminder_settings(project_id: str = Query("", alias="project_id")):
    """List reminder settings, optionally filtered by project_id."""
    sf = get_session_factory()
    async with sf() as session:
        q = select(FlowReminderSettings)
        if project_id:
            q = q.where(FlowReminderSettings.project_id == project_id)
        rows = (await session.execute(q)).scalars().all()
    return {"items": [_setting_dict(r) for r in rows]}


@sub_router.get("/reminder-settings/{project_id}")
async def get_reminder_settings(project_id: str):
    """Get reminder settings for a specific project (auto-creates with defaults if missing)."""
    sf = get_session_factory()
    async with sf() as session:
        proj = await session.get(FlowProject, project_id)
        if not proj:
            return {"error": "项目不存在"}
        setting = (await session.execute(
            select(FlowReminderSettings).where(FlowReminderSettings.project_id == project_id)
        )).scalar_one_or_none()
        if not setting:
            setting = FlowReminderSettings(
                project_id=project_id,
                scenes_json=json.dumps(DEFAULT_SCENES, ensure_ascii=False),
            )
            session.add(setting)
            await session.commit()
            await session.refresh(setting)
    return _setting_dict(setting)


@sub_router.put("/reminder-settings/bulk")
async def bulk_update_reminder_settings(body: BulkReminderSettingsBody):
    """Batch update: apply shared settings to selected projects, disable unselected ones."""
    sf = get_session_factory()
    scenes_json = json.dumps(body.scenes, ensure_ascii=False)

    async with sf() as session:
        all_rows = (await session.execute(select(FlowReminderSettings))).scalars().all()
        existing_map: dict[str, FlowReminderSettings] = {r.project_id: r for r in all_rows}

        selected = set(body.project_ids)

        for pid in selected:
            proj = await session.get(FlowProject, pid)
            if not proj:
                continue
            setting = existing_map.get(pid)
            if not setting:
                setting = FlowReminderSettings(project_id=pid)
                session.add(setting)
            setting.enabled = body.enabled
            setting.scenes_json = scenes_json
            setting.work_days = body.work_days
            setting.near_deadline_days = body.near_deadline_days
            setting.ai_suggestion = body.ai_suggestion
            setting.skip_empty = body.skip_empty
            setting.min_threshold = body.min_threshold

        for pid, setting in existing_map.items():
            if pid not in selected and setting.enabled:
                setting.enabled = False

        await session.commit()

        updated_rows = (await session.execute(select(FlowReminderSettings))).scalars().all()
        for row in updated_rows:
            reminder_service.register_project(row)

    return {"ok": True}


@sub_router.put("/reminder-settings/{project_id}")
async def update_reminder_settings(project_id: str, body: ReminderSettingsBody):
    """Create or update reminder settings for a project."""
    sf = get_session_factory()
    async with sf() as session:
        proj = await session.get(FlowProject, project_id)
        if not proj:
            return {"error": "项目不存在"}

        setting = (await session.execute(
            select(FlowReminderSettings).where(FlowReminderSettings.project_id == project_id)
        )).scalar_one_or_none()

        if not setting:
            setting = FlowReminderSettings(project_id=project_id)
            session.add(setting)

        setting.enabled = body.enabled
        setting.scenes_json = json.dumps(body.scenes, ensure_ascii=False)
        setting.work_days = body.work_days
        setting.near_deadline_days = body.near_deadline_days
        setting.ai_suggestion = body.ai_suggestion
        setting.skip_empty = body.skip_empty
        setting.min_threshold = body.min_threshold
        await session.commit()
        await session.refresh(setting)

        reminder_service.register_project(setting)

    return _setting_dict(setting)


class TestReminderBody(BaseModel):
    project_ids: list[str] = []
    scene: str = "morning"


@sub_router.post("/reminder-settings/test")
async def test_reminder(body: TestReminderBody):
    """Trigger a test reminder for the given projects and scene."""
    if not body.project_ids:
        return {"error": "请选择至少一个项目"}
    result = await reminder_service.run_now(body.project_ids, body.scene)
    return result
