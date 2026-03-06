"""定时任务路由

提供两组路由：
- schedules_router: /api/schedules — 登录用户管理个人任务
- admin_schedules_router: /api/admin/schedules — 管理员管理所有任务
"""

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from openvort.web.app import require_auth
from openvort.utils.logging import get_logger

log = get_logger("web.schedules")

schedules_router = APIRouter()
admin_schedules_router = APIRouter()


# ---- 请求模型 ----

class CreateJobRequest(BaseModel):
    name: str
    description: str = ""
    schedule_type: str  # cron | interval | once
    schedule: str  # cron 表达式 / 秒数 / ISO 时间
    timezone: str = "Asia/Shanghai"
    action_type: str = "agent_chat"
    action_config: dict | None = None
    enabled: bool = True
    visible: bool = True  # 团队任务是否对成员展示
    target_member_id: str = ""  # 执行人（AI 员工 ID）


class UpdateJobRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    schedule_type: str | None = None
    schedule: str | None = None
    timezone: str | None = None
    action_type: str | None = None
    action_config: dict | None = None
    enabled: bool | None = None
    visible: bool | None = None
    target_member_id: str | None = None  # 执行人（AI 员工 ID）


class BatchDeleteJobsRequest(BaseModel):
    job_ids: list[str]


_scheduler_instance = None
_service_instance = None


def _get_service():
    from openvort.web.deps import get_schedule_service

    # Prefer the centrally-initialized instance from deps (startup with sync)
    svc = get_schedule_service()
    if svc is not None:
        return svc

    # Fallback: lazy init (e.g. deps not yet populated)
    from openvort.web.deps import get_db_session_factory, get_agent
    from openvort.core.schedule_service import ScheduleService
    from openvort.core.scheduler import Scheduler

    global _scheduler_instance, _service_instance
    if _scheduler_instance is None:
        _scheduler_instance = Scheduler()
        _scheduler_instance.start()
    if _service_instance is None:
        session_factory = get_db_session_factory()
        try:
            agent = get_agent()
        except Exception:
            agent = None
        _service_instance = ScheduleService(session_factory, _scheduler_instance, agent)
    return _service_instance


def _get_member_id(request: Request) -> str:
    payload = require_auth(request)
    return payload["sub"]


def _is_admin(request: Request) -> bool:
    payload = require_auth(request)
    return "admin" in payload.get("roles", [])


# ---- 个人任务路由 (/api/schedules) ----


@schedules_router.get("")
async def list_my_jobs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
    schedule_type: str | None = Query(None),
    last_status: str | None = Query(None),
    hide_done_once: bool = Query(True),
):
    """列出我的任务"""
    member_id = _get_member_id(request)
    service = _get_service()
    return await service.list_jobs(
        owner_id=member_id,
        page=page, page_size=page_size,
        keyword=keyword, schedule_type=schedule_type,
        last_status=last_status, hide_done_once=hide_done_once,
    )


@schedules_router.post("")
async def create_my_job(request: Request, req: CreateJobRequest):
    """创建个人任务"""
    member_id = _get_member_id(request)
    service = _get_service()
    job = await service.create_job(
        owner_id=member_id,
        scope="personal",
        name=req.name,
        description=req.description,
        schedule_type=req.schedule_type,
        schedule=req.schedule,
        timezone=req.timezone,
        action_type=req.action_type,
        action_config=req.action_config,
        enabled=req.enabled,
        visible=req.visible,
        target_member_id=req.target_member_id or "",
    )
    return {"success": True, "job": job}


@schedules_router.post("/batch-delete")
async def batch_delete_my_jobs(request: Request, req: BatchDeleteJobsRequest):
    """批量删除个人任务"""
    member_id = _get_member_id(request)
    service = _get_service()
    count = await service.batch_delete_jobs(req.job_ids, owner_id=member_id)
    return {"success": True, "count": count}


@schedules_router.put("/{job_id}")
async def update_my_job(request: Request, job_id: str, req: UpdateJobRequest):
    """编辑个人任务（仅 owner）"""
    member_id = _get_member_id(request)
    service = _get_service()
    fields = req.model_dump(exclude_none=True)
    job = await service.update_job(job_id, owner_id=member_id, **fields)
    if not job:
        return {"success": False, "error": "任务不存在或无权限"}
    return {"success": True, "job": job}


@schedules_router.delete("/{job_id}")
async def delete_my_job(request: Request, job_id: str):
    """删除个人任务（仅 owner）"""
    member_id = _get_member_id(request)
    service = _get_service()
    ok = await service.delete_job(job_id, owner_id=member_id)
    return {"success": ok}


@schedules_router.post("/{job_id}/toggle")
async def toggle_my_job(request: Request, job_id: str):
    """启用/禁用个人任务"""
    member_id = _get_member_id(request)
    service = _get_service()
    job = await service.toggle_job(job_id, owner_id=member_id)
    if not job:
        return {"success": False, "error": "任务不存在或无权限"}
    return {"success": True, "job": job}


@schedules_router.post("/{job_id}/run")
async def run_my_job(request: Request, job_id: str):
    """立即执行个人任务"""
    member_id = _get_member_id(request)
    # 先验证归属
    service = _get_service()
    job = await service.get_job(job_id)
    if not job or job["owner_id"] != member_id:
        return {"success": False, "error": "任务不存在或无权限"}
    result = await service.run_now(job_id)
    return result


# ---- 管理员任务路由 (/api/admin/schedules) ----


@admin_schedules_router.get("")
async def list_all_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
    schedule_type: str | None = Query(None),
    last_status: str | None = Query(None),
    hide_done_once: bool = Query(True),
):
    """列出所有任务"""
    service = _get_service()
    return await service.list_jobs(
        page=page, page_size=page_size,
        keyword=keyword, schedule_type=schedule_type,
        last_status=last_status, hide_done_once=hide_done_once,
    )


@admin_schedules_router.post("")
async def create_team_job(request: Request, req: CreateJobRequest):
    """创建团队任务"""
    member_id = _get_member_id(request)
    service = _get_service()
    job = await service.create_job(
        owner_id=member_id,
        scope="team",
        name=req.name,
        description=req.description,
        schedule_type=req.schedule_type,
        schedule=req.schedule,
        timezone=req.timezone,
        action_type=req.action_type,
        action_config=req.action_config,
        enabled=req.enabled,
        visible=req.visible,
    )
    return {"success": True, "job": job}


@admin_schedules_router.post("/batch-delete")
async def batch_delete_any_jobs(req: BatchDeleteJobsRequest):
    """批量删除任务"""
    service = _get_service()
    count = await service.batch_delete_jobs(req.job_ids, is_admin=True)
    return {"success": True, "count": count}


@admin_schedules_router.put("/{job_id}")
async def update_any_job(request: Request, job_id: str, req: UpdateJobRequest):
    """编辑任意任务"""
    service = _get_service()
    fields = req.model_dump(exclude_none=True)
    job = await service.update_job(job_id, is_admin=True, **fields)
    if not job:
        return {"success": False, "error": "任务不存在"}
    return {"success": True, "job": job}


@admin_schedules_router.delete("/{job_id}")
async def delete_any_job(job_id: str):
    """删除任意任务"""
    service = _get_service()
    ok = await service.delete_job(job_id, is_admin=True)
    return {"success": ok}


@admin_schedules_router.post("/{job_id}/toggle")
async def toggle_any_job(job_id: str):
    """启用/禁用任意任务"""
    service = _get_service()
    job = await service.toggle_job(job_id, is_admin=True)
    if not job:
        return {"success": False, "error": "任务不存在"}
    return {"success": True, "job": job}


@admin_schedules_router.post("/{job_id}/run")
async def run_any_job(job_id: str):
    """立即执行任意任务"""
    service = _get_service()
    result = await service.run_now(job_id)
    return result


# ---- 获取 AI 员工列表（用于任务执行人选择）----

@schedules_router.get("/executors")
async def list_executors(request: Request):
    """获取可作为执行人的 AI 员工列表"""
    from sqlalchemy import select
    from openvort.contacts.models import Member

    from openvort.web.deps import get_db_session_factory

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        stmt = select(Member).where(
            Member.is_virtual == True,  # noqa: E712
            Member.status == "active",
        )
        result = await db.execute(stmt)
        members = result.scalars().all()

    return {
        "executors": [
            {
                "id": m.id,
                "name": m.name,
                "virtual_role": m.virtual_role or "",
            }
            for m in members
        ]
    }
