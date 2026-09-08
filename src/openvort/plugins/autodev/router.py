"""AutoDev REST — 项目自动交付配置、队列、派发、运行记录、统计、全局任务。挂在 /api/autodev。"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from openvort.db.models import RemoteNode
from openvort.plugins.autodev import contract as ct
from openvort.plugins.autodev.models import AutodevProject, AutodevRun
from openvort.plugins.autodev.service import (
    ACTION_DISPATCH,
    ACTION_SYNC,
    AutodevError,
    _decrypt,
    get_service,
    mask,
)
from openvort.web.auth import verify_token

router = APIRouter(prefix="/api/autodev", tags=["autodev"])


def _auth_payload(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    payload = verify_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="未登录")
    return payload


def _require_admin(request: Request) -> dict:
    payload = _auth_payload(request)
    if "admin" not in payload.get("roles", []):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return payload


def project_dict(p: AutodevProject) -> dict:
    return {
        "id": p.id,
        "project_id": p.project_id,
        "repo_path": p.repo_path,
        "jira_project_key": p.jira_project_key,
        "sync_jql": p.sync_jql,
        "sync_max_results": p.sync_max_results,
        "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
        "deliver": p.deliver,
        "enabled": p.enabled,
        "paused": p.paused,
        "last_dispatched_at": p.last_dispatched_at.isoformat() if p.last_dispatched_at else None,
        "hcm_base_url": p.hcm_base_url,
        "hcm_username": p.hcm_username,
        "hcm_password": mask(_decrypt(p.hcm_password_enc)),
        "env": json.loads(p.env_json or "{}"),
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def run_dict(r: AutodevRun) -> dict:
    return {
        "id": r.id,
        "issue_key": r.issue_key,
        "story_id": r.story_id,
        "status": r.status,
        "trigger": r.trigger,
        "exit_code": r.exit_code,
        "exit_meaning": ct.describe_exit(r.exit_code) if r.status != "running" else "运行中",
        "outcome": r.outcome,
        "verdict": r.verdict,
        "branch": r.branch,
        "worktree": r.worktree,
        "mr_url": r.mr_url,
        "model": r.model,
        "image_id": r.image_id,
        "dispatch_dir": r.dispatch_dir,
        "run_dir": r.run_dir,
        "input_tokens": r.input_tokens,
        "output_tokens": r.output_tokens,
        "total_tokens": r.total_tokens,
        "cached_tokens": r.cached_tokens,
        "calls": r.calls,
        "duration_ms": r.duration_ms,
        "cost": r.cost,
        "error": r.error,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


class ProjectConfigIn(BaseModel):
    repo_path: str | None = None
    jira_project_key: str | None = None
    sync_jql: str | None = None
    sync_max_results: int | None = None
    deliver: bool | None = None
    enabled: bool | None = None
    hcm_base_url: str | None = None
    hcm_username: str | None = None
    hcm_password: str | None = None
    env: dict | None = None


class DispatchIn(BaseModel):
    issue_key: str = ""
    max_starts: int = 1


class GlobalJobIn(BaseModel):
    enabled: bool
    interval_seconds: int | None = None


@router.get("/exit-codes")
async def exit_codes():
    return {"codes": [{"code": k, "meaning": v, "outcome": ct.outcome_for(k)} for k, v in ct.EXIT_CODES.items()]}


@router.get("/global")
async def global_state():
    """全局状态：AI 员工、它绑定的 master（含 slot）、固定参数、两条全局任务。"""
    svc = get_service()
    master: dict = {"node_id": "", "name": "", "max_slots": 0, "error": ""}
    try:
        node_id = await svc.master_node_id()
        _, cfg = await svc._node(node_id)
        async with svc._sf() as db:
            node = await db.get(RemoteNode, node_id)
        master.update(node_id=node_id, name=node.name if node else node_id, max_slots=ct.node_max_slots(cfg))
    except AutodevError as e:
        master["error"] = str(e)
    jobs = {}
    for action in (ACTION_DISPATCH, ACTION_SYNC):
        job = await svc.find_global_job(action)
        jobs[action] = None if job is None else {
            "job_id": job.job_id, "enabled": job.enabled, "schedule": job.schedule,
            "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
            "last_status": job.last_status, "last_result": job.last_result,
        }
    return {"ai_member_id": svc.ai_member_id, "master": master, "fixed": ct.fixed_params(), "jobs": jobs}


@router.put("/global/{action}")
async def set_global_job(action: str, body: GlobalJobIn, request: Request):
    payload = _require_admin(request)
    if action not in (ACTION_DISPATCH, ACTION_SYNC):
        raise HTTPException(404, "未知全局任务")
    try:
        await get_service().ensure_global_jobs(creator_id=payload.get("member_id", ""))
        job = await get_service().set_global_job(action, enabled=body.enabled, interval_seconds=body.interval_seconds)
    except AutodevError as e:
        raise HTTPException(400, str(e))
    return {"job": job}


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    p = await get_service().get_project(project_id)
    return {"config": project_dict(p) if p else None}


@router.put("/projects/{project_id}")
async def put_project(project_id: str, body: ProjectConfigIn, request: Request):
    _require_admin(request)
    data = body.model_dump(exclude_none=True)
    if "env" in data:
        data["env_json"] = data.pop("env")
    try:
        p = await get_service().upsert_project(project_id, data)
    except (ValueError, AutodevError) as e:
        raise HTTPException(400, str(e))
    return {"config": project_dict(p)}


@router.post("/projects/{project_id}/pause")
async def pause_project(project_id: str, request: Request):
    _require_admin(request)
    return {"config": project_dict(await get_service().set_paused(project_id, True))}


@router.post("/projects/{project_id}/resume")
async def resume_project(project_id: str, request: Request):
    _require_admin(request)
    return {"config": project_dict(await get_service().set_paused(project_id, False))}


@router.get("/projects/{project_id}/queue")
async def queue(project_id: str):
    svc = get_service()
    p = await svc.get_project(project_id)
    if not p:
        raise HTTPException(404, "该项目尚未配置自动交付")
    running = await svc._running_keys(p.id)
    items = await svc.queue(p)
    for it in items:
        it["running"] = it["key"] in running
    return {"items": items, "unmapped_dev_assign": await svc.unmapped_dev_assign(p), "ai_member_id": svc.ai_member_id}


@router.post("/projects/{project_id}/sync")
async def sync_now(project_id: str, request: Request):
    _require_admin(request)
    svc = get_service()
    p = await svc.get_project(project_id)
    if not p:
        raise HTTPException(404, "该项目尚未配置自动交付")
    try:
        return {"counts": await svc.sync_project(p)}
    except (AutodevError, AssertionError, ValueError) as e:
        raise HTTPException(502, f"同步失败: {e}")


@router.post("/projects/{project_id}/dispatch")
async def dispatch(project_id: str, body: DispatchIn, request: Request):
    _require_admin(request)
    try:
        return await get_service().dispatch(project_id, issue_key=body.issue_key.strip(),
                                            max_starts=body.max_starts, trigger="manual")
    except (AutodevError, ValueError, AssertionError) as e:
        raise HTTPException(400, str(e))


@router.get("/projects/{project_id}/runs")
async def runs(project_id: str, issue_key: str = "", limit: int = Query(50, ge=1, le=500)):
    rows = await get_service().list_runs(project_id, issue_key=issue_key, limit=limit)
    return {"items": [run_dict(r) for r in rows]}


@router.get("/projects/{project_id}/stats")
async def stats(project_id: str, days: int = Query(7, ge=1, le=365)):
    return await get_service().stats(project_id, days=days)


@router.post("/poll")
async def poll(request: Request):
    _require_admin(request)
    return {"reconciled": await get_service().poll_once()}
