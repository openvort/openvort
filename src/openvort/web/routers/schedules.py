"""定时任务路由

提供两组路由：
- schedules_router: /api/schedules — 登录用户管理个人任务
- admin_schedules_router: /api/admin/schedules — 管理员管理所有任务
"""

from fastapi import APIRouter, Request
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


_scheduler_instance = None
_service_instance = None


def _get_service():
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
async def list_my_jobs(request: Request):
    """列出我的任务"""
    member_id = _get_member_id(request)
    service = _get_service()
    jobs = await service.list_jobs(owner_id=member_id)
    return {"jobs": jobs}


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
    )("/{job_id}")
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
async def list_all_jobs():
    """列出所有任务"""
    service = _get_service()
    jobs = await service.list_jobs()
    return {"jobs": jobs}


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
