"""Milestone CRUD, Event Log, Dashboard Stats, AI Generate."""

from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowBug, FlowEvent, FlowMilestone, FlowStory, FlowTask,
)
from .helpers import _log_event, _milestone_dict, _parse_dt
from .schemas import MilestoneCreate, MilestoneUpdate

sub_router = APIRouter()


# ============ Milestone CRUD ============

@sub_router.get("/milestones")
async def list_milestones(
    project_id: str = Query("", description="按项目过滤"),
    keyword: str = Query("", description="关键词搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowMilestone).order_by(FlowMilestone.due_date.asc().nulls_last())
        count_stmt = select(func.count()).select_from(FlowMilestone)
        if project_id:
            stmt = stmt.where(FlowMilestone.project_id == project_id)
            count_stmt = count_stmt.where(FlowMilestone.project_id == project_id)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(FlowMilestone.name.ilike(like))
            count_stmt = count_stmt.where(FlowMilestone.name.ilike(like))
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {"total": total, "items": [_milestone_dict(r) for r in rows]}

@sub_router.get("/milestones/{milestone_id}")
async def get_milestone(milestone_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowMilestone, milestone_id)
        if not r:
            return {"error": "里程碑不存在"}
    return _milestone_dict(r)

@sub_router.post("/milestones")
async def create_milestone(body: MilestoneCreate):
    sf = get_session_factory()
    async with sf() as session:
        m = FlowMilestone(
            project_id=body.project_id, name=body.name,
            story_id=body.story_id, due_date=_parse_dt(body.due_date),
        )
        session.add(m)
        await session.flush()
        await _log_event(session, "milestone", m.id, "created", {"name": body.name})
        await session.commit()
        await session.refresh(m)
    return _milestone_dict(m)

@sub_router.put("/milestones/{milestone_id}")
async def update_milestone(milestone_id: str, body: MilestoneUpdate):
    sf = get_session_factory()
    async with sf() as session:
        m = await session.get(FlowMilestone, milestone_id)
        if not m:
            return {"error": "里程碑不存在"}
        changes = {}
        if body.name is not None:
            changes["name"] = body.name
            m.name = body.name
        if body.due_date is not None:
            m.due_date = _parse_dt(body.due_date)
            changes["due_date"] = body.due_date
        if body.completed_at is not None:
            m.completed_at = _parse_dt(body.completed_at)
            changes["completed_at"] = body.completed_at
        if changes:
            await _log_event(session, "milestone", milestone_id, "updated", changes)
        await session.commit()
        await session.refresh(m)
    return _milestone_dict(m)

@sub_router.delete("/milestones/{milestone_id}")
async def delete_milestone(milestone_id: str):
    sf = get_session_factory()
    async with sf() as session:
        m = await session.get(FlowMilestone, milestone_id)
        if not m:
            return {"error": "里程碑不存在"}
        await session.delete(m)
        await _log_event(session, "milestone", milestone_id, "deleted", {"name": m.name})
        await session.commit()
    return {"ok": True}

@sub_router.post("/milestones/{milestone_id}/complete")
async def complete_milestone(milestone_id: str):
    sf = get_session_factory()
    async with sf() as session:
        m = await session.get(FlowMilestone, milestone_id)
        if not m:
            return {"error": "里程碑不存在"}
        m.completed_at = datetime.utcnow()
        await _log_event(session, "milestone", milestone_id, "completed", {"name": m.name})
        await session.commit()
        await session.refresh(m)
    return _milestone_dict(m)


# ============ Event Log ============

@sub_router.get("/events")
async def list_events(
    entity_type: str = Query("", description="实体类型"),
    entity_id: str = Query("", description="实体 ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowEvent).order_by(FlowEvent.created_at.desc())
        count_stmt = select(func.count()).select_from(FlowEvent)
        if entity_type:
            stmt = stmt.where(FlowEvent.entity_type == entity_type)
            count_stmt = count_stmt.where(FlowEvent.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(FlowEvent.entity_id == entity_id)
            count_stmt = count_stmt.where(FlowEvent.entity_id == entity_id)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
                "action": r.action, "actor_id": r.actor_id, "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# ============ Dashboard Stats ============

@sub_router.get("/dashboard/stats")
async def dashboard_stats(project_id: str = Query("", description="项目 ID")):
    sf = get_session_factory()
    async with sf() as session:
        story_q = select(func.count()).select_from(FlowStory)
        task_q = select(func.count()).select_from(FlowTask).join(
            FlowStory, FlowTask.story_id == FlowStory.id
        )
        bug_q = select(func.count()).select_from(FlowBug).outerjoin(
            FlowStory, FlowBug.story_id == FlowStory.id
        )

        if project_id:
            story_q = story_q.where(FlowStory.project_id == project_id)
            task_q = task_q.where(FlowStory.project_id == project_id)
            bug_q = bug_q.where(FlowStory.project_id == project_id)

        total_stories = (await session.execute(story_q)).scalar_one()
        total_tasks = (await session.execute(task_q)).scalar_one()
        total_bugs = (await session.execute(bug_q)).scalar_one()

        done_stories = (await session.execute(
            story_q.where(FlowStory.state == "done")
        )).scalar_one()
        done_tasks = (await session.execute(
            task_q.where(FlowTask.state == "done")
        )).scalar_one()
        closed_bugs = (await session.execute(
            bug_q.where(FlowBug.state == "closed")
        )).scalar_one()

    return {
        "stories": {"total": total_stories, "done": done_stories},
        "tasks": {"total": total_tasks, "done": done_tasks},
        "bugs": {"total": total_bugs, "closed": closed_bugs},
    }


# ============ AI Generate ============

@sub_router.get("/generate-description-prompt")
async def generate_vortflow_description(
    entity_type: str = Query(..., description="类型: story/task/bug/milestone"),
    project_name: str = Query("", description="项目名称"),
    title: str = Query("", description="标题"),
):
    """生成 AI 创建 VortFlow 描述内容的 prompt"""
    if entity_type == "story":
        prompt = (
            f"请为需求「{title}」生成专业、详细的需求描述内容。\n\n"
            f"项目：{project_name or '未指定'}\n"
            f"需求标题：{title}\n\n"
            f"请生成完整的需求描述（Markdown 格式），包括：\n"
            f"1. 背景与目标 - 为什么要做这个需求，解决什么问题\n"
            f"2. 功能描述 - 详细的功能点和用户故事\n"
            f"3. 验收标准 - 如何验证需求是否完成\n"
            f"4. 注意事项 - 实现过程中需要关注的点\n\n"
            f"要求：内容要清晰、完整，能帮助开发人员准确理解需求。"
        )
    elif entity_type == "task":
        prompt = (
            f"请为任务「{title}」生成详细的任务描述内容。\n\n"
            f"项目：{project_name or '未指定'}\n"
            f"任务标题：{title}\n\n"
            f"请生成完整的任务描述（Markdown 格式），包括：\n"
            f"1. 任务目标 - 具体要完成什么\n"
            f"2. 实施方案 - 建议的实现方式和技术方案\n"
            f"3. 关联需求 - 关联的需求或 Bug\n"
            f"4. 自测要点 - 如何验证任务完成\n\n"
            f"要求：内容要实用，能指导开发人员快速上手任务。"
        )
    elif entity_type == "bug":
        prompt = (
            f"请为缺陷「{title}」生成详细的缺陷描述内容。\n\n"
            f"项目：{project_name or '未指定'}\n"
            f"缺陷标题：{title}\n\n"
            f"请生成完整的缺陷描述（Markdown 格式），包括：\n"
            f"1. 问题描述 - 缺陷的详细描述\n"
            f"2. 复现步骤 - 一步步如何复现这个问题\n"
            f"3. 预期行为 - 正常应该是什么样子\n"
            f"4. 实际行为 - 实际发生了什么\n"
            f"5. 建议修复方案 - 如何修复这个问题\n\n"
            f"要求：描述要清晰、准确，帮助开发人员快速定位和修复问题。"
        )
    elif entity_type == "milestone":
        prompt = (
            f"请为里程碑「{title}」生成详细的描述内容。\n\n"
            f"项目：{project_name or '未指定'}\n"
            f"里程碑标题：{title}\n\n"
            f"请生成完整的里程碑描述（Markdown 格式），包括：\n"
            f"1. 目标概述 - 这个里程碑要达成什么目标\n"
            f"2. 关键交付物 - 需要完成哪些需求/任务\n"
            f"3. 时间安排 - 计划的时间节点\n"
            f"4. 风险与依赖 - 可能的风险和外部依赖\n\n"
            f"要求：内容要能帮助团队明确里程碑的目标和计划。"
        )
    else:
        prompt = f"请为「{title}」生成描述内容。"

    return {"prompt": prompt}
