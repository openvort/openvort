"""工作安排路由

提供工作安排（WorkAssignment）的 CRUD 接口：
- 列出某 AI 员工的工作安排
- 创建/更新/删除工作安排
"""

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from openvort.web.app import require_auth
from openvort.utils.logging import get_logger

log = get_logger("web.work_assignments")

work_assignments_router = APIRouter()


# ---- 请求模型 ----


class CreateAssignmentRequest(BaseModel):
    title: str  # 任务标题/一句话描述
    summary: str = ""  # 任务详细描述/AI 的理解
    plan: str = ""  # AI 员工"打算怎么做"的简短步骤

    requested_by_member_id: str = ""  # 谁要求的（默认为当前用户）
    assignee_member_id: str  # 谁来执行（AI 员工 ID）

    source_type: str = "manual"  # chat / code_task / schedule / manual
    source_id: str = ""  # 来源ID
    source_detail: str = ""  # 来源详情摘要

    related_schedule_id: int | None = None  # 关联的计划任务 ID

    status: str = "pending"  # pending / in_progress / completed / ongoing
    priority: str = "normal"  # low / normal / high / urgent
    due_date: str | None = None  # ISO 格式截止日期


class UpdateAssignmentRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    plan: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None


def _get_member_id(request: Request) -> str:
    payload = require_auth(request)
    return payload["sub"]


# ---- 路由实现 ----


@work_assignments_router.get("")
async def list_assignments(
    request: Request,
    assignee_member_id: str | None = None,
    requested_by_member_id: str | None = None,
    status: str | None = None,
):
    """列出工作安排

    - assignee_member_id: 筛选指定 AI 员工的工作安排
    - requested_by_member_id: 筛选指定委托人安排的工作安排
    - status: 筛选状态
    """
    from sqlalchemy import select, desc
    from openvort.db.models import WorkAssignment

    from openvort.web.deps import get_db_session_factory

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        stmt = select(WorkAssignment)

        if assignee_member_id:
            stmt = stmt.where(WorkAssignment.assignee_member_id == assignee_member_id)
        if requested_by_member_id:
            stmt = stmt.where(WorkAssignment.requested_by_member_id == requested_by_member_id)
        if status:
            stmt = stmt.where(WorkAssignment.status == status)

        stmt = stmt.order_by(desc(WorkAssignment.updated_at))

        result = await db.execute(stmt)
        assignments = result.scalars().all()

    # Batch-load linked ScheduleJob info for schedule-sourced assignments
    schedule_map: dict[int, "ScheduleJob"] = {}
    schedule_ids = [a.related_schedule_id for a in assignments if a.related_schedule_id]
    if schedule_ids:
        try:
            from openvort.db.models import ScheduleJob
            async with session_factory() as db2:
                sj_stmt = select(ScheduleJob).where(ScheduleJob.id.in_(schedule_ids))
                sj_result = await db2.execute(sj_stmt)
                for sj in sj_result.scalars().all():
                    schedule_map[sj.id] = sj
        except Exception:
            pass

    result_list = []
    for a in assignments:
        item: dict = {
            "id": a.id,
            "title": a.title,
            "summary": a.summary,
            "plan": a.plan,
            "requested_by_member_id": a.requested_by_member_id,
            "assignee_member_id": a.assignee_member_id,
            "source_type": a.source_type,
            "source_id": a.source_id,
            "source_detail": a.source_detail,
            "related_schedule_id": a.related_schedule_id,
            "status": a.status,
            "priority": a.priority,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "last_action_at": a.last_action_at.isoformat() if a.last_action_at else None,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        }
        sj = schedule_map.get(a.related_schedule_id) if a.related_schedule_id else None
        if sj:
            item["schedule_info"] = {
                "job_id": sj.job_id,
                "schedule_type": sj.schedule_type,
                "schedule": sj.schedule,
                "enabled": sj.enabled,
                "last_run_at": sj.last_run_at.isoformat() if sj.last_run_at else None,
                "last_status": sj.last_status or "pending",
                "last_result": sj.last_result or "",
            }
        result_list.append(item)

    return {"assignments": result_list}


@work_assignments_router.post("")
async def create_assignment(request: Request, req: CreateAssignmentRequest):
    """创建工作安排"""
    from openvort.db.models import WorkAssignment

    from openvort.web.deps import get_db_session_factory

    member_id = _get_member_id(request)

    # 如果没有指定委托人，默认使用当前用户
    if not req.requested_by_member_id:
        req.requested_by_member_id = member_id

    due_date = None
    if req.due_date:
        due_date = datetime.fromisoformat(req.due_date)

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        assignment = WorkAssignment(
            title=req.title,
            summary=req.summary,
            plan=req.plan,
            requested_by_member_id=req.requested_by_member_id,
            assignee_member_id=req.assignee_member_id,
            source_type=req.source_type,
            source_id=req.source_id,
            source_detail=req.source_detail,
            related_schedule_id=req.related_schedule_id,
            status=req.status,
            priority=req.priority,
            due_date=due_date,
        )
        db.add(assignment)
        await db.commit()
        await db.refresh(assignment)

    return {
        "success": True,
        "assignment": {
            "id": assignment.id,
            "title": assignment.title,
            "summary": assignment.summary,
            "plan": assignment.plan,
            "requested_by_member_id": assignment.requested_by_member_id,
            "assignee_member_id": assignment.assignee_member_id,
            "source_type": assignment.source_type,
            "source_id": assignment.source_id,
            "source_detail": assignment.source_detail,
            "related_schedule_id": assignment.related_schedule_id,
            "status": assignment.status,
            "priority": assignment.priority,
            "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
            "created_at": assignment.created_at.isoformat(),
            "updated_at": assignment.updated_at.isoformat(),
        },
    }


@work_assignments_router.put("/{assignment_id}")
async def update_assignment(
    request: Request, assignment_id: int, req: UpdateAssignmentRequest
):
    """更新工作安排（仅 owner 可以更新）"""
    from sqlalchemy import select
    from openvort.db.models import WorkAssignment

    from openvort.web.deps import get_db_session_factory

    member_id = _get_member_id(request)

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        stmt = select(WorkAssignment).where(WorkAssignment.id == assignment_id)
        result = await db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            return {"success": False, "error": "工作安排不存在"}

        # 只有委托人或者 AI 员工本人可以更新
        if (
            assignment.requested_by_member_id != member_id
            and assignment.assignee_member_id != member_id
        ):
            return {"success": False, "error": "无权限更新"}

        # 更新字段
        if req.title is not None:
            assignment.title = req.title
        if req.summary is not None:
            assignment.summary = req.summary
        if req.plan is not None:
            assignment.plan = req.plan
        if req.status is not None:
            assignment.status = req.status
            # 状态变更时更新 last_action_at
            assignment.last_action_at = datetime.utcnow()
        if req.priority is not None:
            assignment.priority = req.priority
        if req.due_date is not None:
            assignment.due_date = (
                datetime.fromisoformat(req.due_date) if req.due_date else None
            )

        await db.commit()
        await db.refresh(assignment)

    return {
        "success": True,
        "assignment": {
            "id": assignment.id,
            "title": assignment.title,
            "summary": assignment.summary,
            "plan": assignment.plan,
            "status": assignment.status,
            "priority": assignment.priority,
            "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
            "last_action_at": assignment.last_action_at.isoformat()
            if assignment.last_action_at
            else None,
            "updated_at": assignment.updated_at.isoformat(),
        },
    }


@work_assignments_router.delete("/{assignment_id}")
async def delete_assignment(request: Request, assignment_id: int):
    """删除工作安排（仅 owner 可以删除），联动删除关联的 ScheduleJob"""
    from sqlalchemy import select, delete
    from openvort.db.models import WorkAssignment

    from openvort.web.deps import get_db_session_factory

    member_id = _get_member_id(request)

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        stmt = select(WorkAssignment).where(WorkAssignment.id == assignment_id)
        result = await db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            return {"success": False, "error": "工作安排不存在"}

        if (
            assignment.requested_by_member_id != member_id
            and assignment.assignee_member_id != member_id
        ):
            return {"success": False, "error": "无权限删除"}

        related_schedule_id = assignment.related_schedule_id
        await db.delete(assignment)
        await db.commit()

    if related_schedule_id:
        await _delete_linked_schedule(related_schedule_id, member_id)

    return {"success": True}


@work_assignments_router.post("/{assignment_id}/update_status")
async def update_assignment_status(
    request: Request, assignment_id: int, status: str
):
    """快速更新工作安排状态，联动暂停/恢复/结束关联的 ScheduleJob"""
    from sqlalchemy import select
    from openvort.db.models import WorkAssignment

    from openvort.web.deps import get_db_session_factory

    member_id = _get_member_id(request)

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        stmt = select(WorkAssignment).where(WorkAssignment.id == assignment_id)
        result = await db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            return {"success": False, "error": "工作安排不存在"}

        if (
            assignment.requested_by_member_id != member_id
            and assignment.assignee_member_id != member_id
        ):
            return {"success": False, "error": "无权限更新"}

        old_status = assignment.status
        assignment.status = status
        assignment.last_action_at = datetime.utcnow()
        await db.commit()
        await db.refresh(assignment)
        related_schedule_id = assignment.related_schedule_id

    if related_schedule_id:
        await _sync_schedule_state(related_schedule_id, old_status, status, member_id)

    return {"success": True, "status": assignment.status}


# ---- helpers: sync with ScheduleJob ----

async def _get_schedule_service():
    from openvort.web.deps import get_schedule_service
    return get_schedule_service()


async def _delete_linked_schedule(schedule_id: int, member_id: str):
    """Delete the ScheduleJob linked to this work assignment."""
    svc = await _get_schedule_service()
    if not svc:
        return
    from sqlalchemy import select
    from openvort.db.models import ScheduleJob
    from openvort.web.deps import get_db_session_factory
    session_factory = get_db_session_factory()
    async with session_factory() as db:
        stmt = select(ScheduleJob).where(ScheduleJob.id == schedule_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if job:
            await svc.delete_job(job.job_id, owner_id=member_id, is_admin=True)


async def _sync_schedule_state(
    schedule_id: int, old_status: str, new_status: str, member_id: str
):
    """Pause/resume/remove the linked ScheduleJob when assignment status changes."""
    svc = await _get_schedule_service()
    if not svc:
        return
    from sqlalchemy import select
    from openvort.db.models import ScheduleJob
    from openvort.web.deps import get_db_session_factory
    session_factory = get_db_session_factory()
    async with session_factory() as db:
        stmt = select(ScheduleJob).where(ScheduleJob.id == schedule_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return

    should_disable = new_status in ("paused", "completed")
    should_enable = new_status in ("ongoing", "pending", "in_progress")

    if should_disable and job.enabled:
        await svc.toggle_job(job.job_id, owner_id=member_id, is_admin=True)
    elif should_enable and not job.enabled:
        await svc.toggle_job(job.job_id, owner_id=member_id, is_admin=True)
