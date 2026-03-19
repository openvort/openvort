"""VortGit FastAPI sub-router — Provider & Repo CRUD + remote import."""

import uuid

from fastapi import APIRouter, Body, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func, delete as sa_delete

from openvort.db.engine import get_session_factory
from openvort.plugins.vortgit.crypto import decrypt_token, encrypt_token
from openvort.plugins.vortgit.models import GitCodeTask, GitProvider, GitRepo, GitRepoMember
from openvort.utils.logging import get_logger
from openvort.web.auth import verify_token

log = get_logger("plugins.vortgit.router")

router = APIRouter(prefix="/api/vortgit", tags=["vortgit"])


# ============ Schemas ============

class ProviderCreate(BaseModel):
    name: str
    platform: str = "gitee"
    api_base: str = ""
    access_token: str = ""
    is_default: bool = False


class ProviderUpdate(BaseModel):
    name: str | None = None
    platform: str | None = None
    api_base: str | None = None
    access_token: str | None = None
    is_default: bool | None = None


class RepoCreate(BaseModel):
    provider_id: str
    name: str
    full_name: str
    clone_url: str = ""
    ssh_url: str = ""
    default_branch: str = "main"
    description: str = ""
    language: str = ""
    repo_type: str = "other"
    is_private: bool = False
    project_id: str | None = None


class RepoUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    repo_type: str | None = None
    project_id: str | None = None
    default_branch: str | None = None


class RepoImportItem(BaseModel):
    full_name: str
    project_id: str | None = None
    repo_type: str = "other"


class RepoImportBody(BaseModel):
    provider_id: str
    repos: list[RepoImportItem]


class RepoMemberAdd(BaseModel):
    member_id: str
    access_level: str = "read"
    platform_username: str = ""


class CodeTaskBatchDelete(BaseModel):
    ids: list[str]


# ============ Helpers ============

def _provider_to_dict(p: GitProvider) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "platform": p.platform,
        "api_base": p.api_base,
        "has_token": bool(p.access_token),
        "is_default": p.is_default,
        "owner_id": p.owner_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _repo_to_dict(r: GitRepo) -> dict:
    return {
        "id": r.id,
        "provider_id": r.provider_id,
        "project_id": r.project_id,
        "name": r.name,
        "full_name": r.full_name,
        "clone_url": r.clone_url,
        "ssh_url": r.ssh_url,
        "default_branch": r.default_branch,
        "description": r.description,
        "language": r.language,
        "repo_type": r.repo_type,
        "is_private": r.is_private,
        "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _get_provider_instance(provider: GitProvider):
    """Create a provider API client from the DB record."""
    token = decrypt_token(provider.access_token) if provider.access_token else ""
    if provider.platform == "gitee":
        from openvort.plugins.vortgit.providers.gitee import GiteeProvider
        return GiteeProvider(access_token=token, api_base=provider.api_base)
    raise HTTPException(400, f"Unsupported platform: {provider.platform}")


def _require_admin(request: Request) -> dict:
    """Lightweight admin check for plugin routes (matches web.app.require_admin)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    else:
        token = ""

    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    roles = payload.get("roles", [])
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return payload


# ============ Provider CRUD ============

@router.get("/providers")
async def list_providers():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(GitProvider).order_by(GitProvider.created_at.desc()))
        return {"items": [_provider_to_dict(p) for p in result.scalars().all()]}


@router.post("/providers")
async def create_provider(body: ProviderCreate):
    sf = get_session_factory()
    async with sf() as session:
        provider = GitProvider(
            id=uuid.uuid4().hex,
            name=body.name,
            platform=body.platform,
            api_base=body.api_base,
            access_token=encrypt_token(body.access_token) if body.access_token else "",
            is_default=body.is_default,
        )
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        return _provider_to_dict(provider)


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: str):
    sf = get_session_factory()
    async with sf() as session:
        provider = await session.get(GitProvider, provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")
        return _provider_to_dict(provider)


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, body: ProviderUpdate):
    sf = get_session_factory()
    async with sf() as session:
        provider = await session.get(GitProvider, provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")
        if body.name is not None:
            provider.name = body.name
        if body.platform is not None:
            provider.platform = body.platform
        if body.api_base is not None:
            provider.api_base = body.api_base
        if body.access_token is not None:
            provider.access_token = encrypt_token(body.access_token) if body.access_token else ""
        if body.is_default is not None:
            provider.is_default = body.is_default
        await session.commit()
        await session.refresh(provider)
        return _provider_to_dict(provider)


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str):
    sf = get_session_factory()
    async with sf() as session:
        provider = await session.get(GitProvider, provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")
        # Check if repos still reference this provider
        count = await session.scalar(
            select(func.count()).where(GitRepo.provider_id == provider_id)
        )
        if count and count > 0:
            raise HTTPException(400, f"Cannot delete: {count} repos still use this provider")
        await session.delete(provider)
        await session.commit()
        return {"ok": True}


# ============ Remote repos (fetch from platform) ============

@router.get("/providers/{provider_id}/remote-repos")
async def list_remote_repos(
    provider_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
):
    sf = get_session_factory()
    async with sf() as session:
        provider = await session.get(GitProvider, provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")

    client = _get_provider_instance(provider)
    try:
        repos = await client.list_repos(page=page, per_page=per_page, search=search)
        return {"items": repos}
    except Exception as e:
        log.error(f"Failed to fetch remote repos from provider {provider_id}: {e}")
        raise HTTPException(502, f"获取远程仓库失败: {e}")
    finally:
        await client.close()


# ============ Repo CRUD ============

@router.get("/repos")
async def list_repos(
    provider_id: str = Query(""),
    project_id: str = Query(""),
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    sf = get_session_factory()
    async with sf() as session:
        q = select(GitRepo)
        if provider_id:
            q = q.where(GitRepo.provider_id == provider_id)
        if project_id:
            q = q.where(GitRepo.project_id == project_id)
        if keyword:
            q = q.where(GitRepo.name.contains(keyword) | GitRepo.full_name.contains(keyword))

        total = await session.scalar(select(func.count()).select_from(q.subquery()))
        q = q.order_by(GitRepo.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        items = [_repo_to_dict(r) for r in result.scalars().all()]
        return {"items": items, "total": total or 0}


@router.post("/repos")
async def create_repo(body: RepoCreate):
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.scalar(select(GitRepo).where(GitRepo.full_name == body.full_name))
        if existing:
            raise HTTPException(400, f"Repo '{body.full_name}' already registered")
        repo = GitRepo(
            id=uuid.uuid4().hex,
            provider_id=body.provider_id,
            project_id=body.project_id or None,
            name=body.name,
            full_name=body.full_name,
            clone_url=body.clone_url,
            ssh_url=body.ssh_url,
            default_branch=body.default_branch,
            description=body.description,
            language=body.language,
            repo_type=body.repo_type,
            is_private=body.is_private,
            webhook_secret=uuid.uuid4().hex[:16],
        )
        session.add(repo)
        await session.commit()
        await session.refresh(repo)
        return _repo_to_dict(repo)


@router.get("/repos/{repo_id}")
async def get_repo(repo_id: str):
    sf = get_session_factory()
    async with sf() as session:
        repo = await session.get(GitRepo, repo_id)
        if not repo:
            raise HTTPException(404, "Repo not found")
        return _repo_to_dict(repo)


@router.put("/repos/{repo_id}")
async def update_repo(repo_id: str, body: RepoUpdate):
    sf = get_session_factory()
    async with sf() as session:
        repo = await session.get(GitRepo, repo_id)
        if not repo:
            raise HTTPException(404, "Repo not found")
        if body.name is not None:
            repo.name = body.name
        if body.description is not None:
            repo.description = body.description
        if body.repo_type is not None:
            repo.repo_type = body.repo_type
        if body.project_id is not None:
            repo.project_id = body.project_id or None
        if body.default_branch is not None:
            repo.default_branch = body.default_branch
        await session.commit()
        await session.refresh(repo)
        return _repo_to_dict(repo)


@router.delete("/repos/{repo_id}")
async def delete_repo(repo_id: str):
    sf = get_session_factory()
    async with sf() as session:
        repo = await session.get(GitRepo, repo_id)
        if not repo:
            raise HTTPException(404, "Repo not found")
        await session.execute(sa_delete(GitRepoMember).where(GitRepoMember.repo_id == repo_id))
        await session.delete(repo)
        await session.commit()
        return {"ok": True}


# ============ Batch import from remote ============

@router.post("/repos/import")
async def import_repos(body: RepoImportBody):
    sf = get_session_factory()
    async with sf() as session:
        provider = await session.get(GitProvider, body.provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")

    client = _get_provider_instance(provider)
    imported = []
    try:
        for item in body.repos:
            # Fetch latest info from platform
            try:
                remote = await client.get_repo(item.full_name)
            except Exception as e:
                log.warning(f"Failed to fetch {item.full_name}: {e}")
                continue

            sf2 = get_session_factory()
            async with sf2() as session:
                existing = await session.scalar(
                    select(GitRepo).where(GitRepo.full_name == item.full_name)
                )
                if existing:
                    continue
                repo = GitRepo(
                    id=uuid.uuid4().hex,
                    provider_id=body.provider_id,
                    project_id=item.project_id or None,
                    name=remote.get("name", item.full_name.split("/")[-1]),
                    full_name=item.full_name,
                    clone_url=remote.get("clone_url", ""),
                    ssh_url=remote.get("ssh_url", ""),
                    default_branch=remote.get("default_branch", "main"),
                    description=remote.get("description", ""),
                    language=remote.get("language", ""),
                    repo_type=item.repo_type,
                    is_private=remote.get("private", False),
                    webhook_secret=uuid.uuid4().hex[:16],
                )
                session.add(repo)
                await session.commit()
                await session.refresh(repo)
                imported.append(_repo_to_dict(repo))
    finally:
        await client.close()

    return {"imported": len(imported), "items": imported}


# ============ Repo commits & branches (proxy to provider) ============

@router.get("/repos/{repo_id}/commits")
async def list_repo_commits(
    repo_id: str,
    branch: str = Query(""),
    since: str = Query(""),
    until: str = Query(""),
    author: str = Query(""),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        repo = await session.get(GitRepo, repo_id)
        if not repo:
            raise HTTPException(404, "Repo not found")
        provider = await session.get(GitProvider, repo.provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")

    client = _get_provider_instance(provider)
    try:
        commits = await client.list_commits(
            repo.full_name,
            branch=branch or repo.default_branch,
            since=since,
            until=until,
            author=author,
            page=page,
            per_page=per_page,
        )
        return {"items": commits}
    finally:
        await client.close()


@router.get("/repos/{repo_id}/branches")
async def list_repo_branches(repo_id: str):
    sf = get_session_factory()
    async with sf() as session:
        repo = await session.get(GitRepo, repo_id)
        if not repo:
            raise HTTPException(404, "Repo not found")
        provider = await session.get(GitProvider, repo.provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")

    client = _get_provider_instance(provider)
    try:
        branches = await client.list_branches(repo.full_name)
        return {"items": branches}
    finally:
        await client.close()


# ============ Repo members ============

@router.get("/repos/{repo_id}/members")
async def list_repo_members(repo_id: str):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(GitRepoMember).where(GitRepoMember.repo_id == repo_id)
        )
        members = result.scalars().all()
        return {
            "items": [
                {
                    "id": m.id,
                    "repo_id": m.repo_id,
                    "member_id": m.member_id,
                    "access_level": m.access_level,
                    "platform_username": m.platform_username,
                }
                for m in members
            ]
        }


@router.post("/repos/{repo_id}/members")
async def add_repo_member(repo_id: str, body: RepoMemberAdd):
    sf = get_session_factory()
    async with sf() as session:
        repo = await session.get(GitRepo, repo_id)
        if not repo:
            raise HTTPException(404, "Repo not found")
        existing = await session.scalar(
            select(GitRepoMember).where(
                GitRepoMember.repo_id == repo_id,
                GitRepoMember.member_id == body.member_id,
            )
        )
        if existing:
            existing.access_level = body.access_level
            if body.platform_username:
                existing.platform_username = body.platform_username
        else:
            member = GitRepoMember(
                id=uuid.uuid4().hex,
                repo_id=repo_id,
                member_id=body.member_id,
                access_level=body.access_level,
                platform_username=body.platform_username,
            )
            session.add(member)
        await session.commit()
        return {"ok": True}


@router.delete("/repos/{repo_id}/members/{member_id}")
async def remove_repo_member(repo_id: str, member_id: str):
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(
            sa_delete(GitRepoMember).where(
                GitRepoMember.repo_id == repo_id,
                GitRepoMember.member_id == member_id,
            )
        )
        await session.commit()
        return {"ok": True}


# ============ Sync repo info from platform ============

@router.post("/repos/{repo_id}/sync")
async def sync_repo(repo_id: str):
    sf = get_session_factory()
    async with sf() as session:
        repo = await session.get(GitRepo, repo_id)
        if not repo:
            raise HTTPException(404, "Repo not found")
        provider = await session.get(GitProvider, repo.provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")

    client = _get_provider_instance(provider)
    try:
        remote = await client.get_repo(repo.full_name)
    finally:
        await client.close()

    from datetime import datetime

    sf2 = get_session_factory()
    async with sf2() as session:
        repo = await session.get(GitRepo, repo_id)
        if repo:
            repo.description = remote.get("description", repo.description)
            repo.language = remote.get("language", repo.language)
            repo.default_branch = remote.get("default_branch", repo.default_branch)
            repo.is_private = remote.get("private", repo.is_private)
            repo.last_synced_at = datetime.utcnow()
            await session.commit()
            await session.refresh(repo)
            return _repo_to_dict(repo)

    raise HTTPException(404, "Repo not found after sync")


# ============ Code Tasks (AI coding task history) ============

def _code_task_to_dict(t: GitCodeTask) -> dict:
    import json as _json
    files = []
    try:
        files = _json.loads(t.files_changed) if t.files_changed else []
    except Exception:
        pass
    return {
        "id": t.id,
        "repo_id": t.repo_id,
        "member_id": t.member_id,
        "story_id": t.story_id,
        "task_id": t.task_id,
        "bug_id": t.bug_id,
        "cli_tool": t.cli_tool,
        "task_description": t.task_description,
        "branch_name": t.branch_name,
        "status": t.status,
        "pr_url": t.pr_url,
        "files_changed": files,
        "diff_summary": t.diff_summary,
        "duration_seconds": t.duration_seconds,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _code_task_detail_to_dict(t: GitCodeTask) -> dict:
    d = _code_task_to_dict(t)
    d["cli_stdout"] = t.cli_stdout
    d["cli_stderr"] = t.cli_stderr
    return d


@router.get("/code-tasks")
async def list_code_tasks(
    status: str = Query(""),
    repo_id: str = Query(""),
    member_id: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        q = select(GitCodeTask)
        if status:
            q = q.where(GitCodeTask.status == status)
        if repo_id:
            q = q.where(GitCodeTask.repo_id == repo_id)
        if member_id:
            q = q.where(GitCodeTask.member_id == member_id)

        total = await session.scalar(select(func.count()).select_from(q.subquery()))
        q = q.order_by(GitCodeTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        items = [_code_task_to_dict(t) for t in result.scalars().all()]
        return {"items": items, "total": total or 0}


@router.get("/code-tasks/stats")
async def code_task_stats():
    sf = get_session_factory()
    async with sf() as session:
        total = await session.scalar(select(func.count()).select_from(GitCodeTask)) or 0
        success = await session.scalar(
            select(func.count()).where(GitCodeTask.status.in_(["success", "review"]))
        ) or 0
        failed = await session.scalar(
            select(func.count()).where(GitCodeTask.status == "failed")
        ) or 0
        running = await session.scalar(
            select(func.count()).where(GitCodeTask.status == "running")
        ) or 0
        active_repos = await session.scalar(
            select(func.count(func.distinct(GitCodeTask.repo_id)))
        ) or 0

        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        this_week = await session.scalar(
            select(func.count()).where(GitCodeTask.created_at >= week_ago)
        ) or 0

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "running": running,
        "success_rate": round(success / total * 100, 1) if total else 0,
        "active_repos": active_repos,
        "this_week": this_week,
    }


@router.get("/code-tasks/{task_id}")
async def get_code_task(task_id: str):
    sf = get_session_factory()
    async with sf() as session:
        task = await session.get(GitCodeTask, task_id)
        if not task:
            raise HTTPException(404, "Code task not found")
        return _code_task_detail_to_dict(task)


@router.delete("/code-tasks/{task_id}")
async def delete_code_task(task_id: str, request: Request):
    """删除单个编码任务记录（仅管理员）"""
    _require_admin(request)
    sf = get_session_factory()
    async with sf() as session:
        task = await session.get(GitCodeTask, task_id)
        if not task:
            raise HTTPException(404, "Code task not found")
        await session.delete(task)
        await session.commit()
        return {"ok": True}


@router.post("/code-tasks/batch-delete")
async def batch_delete_code_tasks(body: CodeTaskBatchDelete, request: Request):
    """批量删除编码任务记录（仅管理员）"""
    _require_admin(request)
    if not body.ids:
        return {"deleted": 0}
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            sa_delete(GitCodeTask).where(GitCodeTask.id.in_(body.ids))
        )
        deleted = result.rowcount or 0
        await session.commit()
        return {"deleted": deleted}


# ============ Coding Environment Status ============

@router.get("/coding-env/status")
async def coding_env_status():
    try:
        from openvort.core.execution.coding_env import CodingEnvironment
        from openvort.config.config_service import ConfigService
        from openvort.plugins.vortgit.config import VortGitSettings

        settings = VortGitSettings()
        config_service = ConfigService(get_session_factory())
        env = CodingEnvironment(
            image=settings.cli_docker_image,
            timeout=settings.cli_timeout,
        )
        cli_config = await config_service.get_cli_config()
        status = await env.get_status()
        raw = status.to_dict()
        # Reshape cli_tools dict into array for frontend
        cli_tools_list = [
            {"name": k, "installed": v.get("installed", False), "version": v.get("version", "")}
            for k, v in raw.get("cli_tools", {}).items()
        ]
        raw["cli_tools"] = cli_tools_list
        raw["docker_image_ready"] = raw.pop("coding_image_pulled", False)
        raw["cli_default_tool"] = cli_config["cli_default_tool"]
        raw["has_claude_key"] = bool(settings.claude_code_api_key)
        raw["has_aider_key"] = bool(settings.aider_api_key)
        return raw
    except Exception as e:
        return {"error": str(e), "mode": "unavailable", "cli_tools": []}
