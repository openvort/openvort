"""Jenkins management REST API router."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select, update

from openvort.db.engine import get_session_factory
from openvort.plugins.jenkins.client import JenkinsClient, JenkinsClientError, JenkinsConnection
from openvort.plugins.jenkins.models import JenkinsInstance
from openvort.plugins.vortgit.crypto import decrypt_token, encrypt_token
from openvort.web.app import require_admin, require_auth
from openvort.web.deps import get_db_session_factory

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_member_id(request: Request) -> str:
    payload = require_auth(request)
    return payload.get("sub", "")


def _get_roles(request: Request) -> list[str]:
    payload = require_auth(request)
    return payload.get("roles", [])


async def _get_user_credential(member_id: str, instance_id: str) -> dict | None:
    """Read and decrypt Jenkins credential for a member on a specific instance.

    Lookup order: instance-specific → global fallback.
    """
    from openvort.db.models import MemberPluginSetting

    sf = get_db_session_factory()
    async with sf() as session:
        stmt = select(MemberPluginSetting).where(
            MemberPluginSetting.member_id == member_id,
            MemberPluginSetting.plugin_name == f"jenkins:{instance_id}",
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

    if not row or not row.settings_data or row.settings_data == "{}":
        return None

    data = json.loads(row.settings_data)
    username = data.get("username", "")
    api_token_enc = data.get("api_token", "")
    if not username or not api_token_enc:
        return None

    try:
        api_token = decrypt_token(api_token_enc)
    except Exception:
        return None

    return {"username": username, "api_token": api_token}


async def _build_client(instance_id: str, member_id: str) -> JenkinsClient:
    """Build a JenkinsClient using instance URL + user personal credential."""
    credential = await _get_user_credential(member_id, instance_id)
    if not credential:
        raise HTTPException(
            status_code=422,
            detail="该实例的 Jenkins 凭证未配置，请点击「配置凭证」设置你的账号",
        )

    sf = get_db_session_factory()
    async with sf() as session:
        instance = await session.get(JenkinsInstance, instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Jenkins 实例不存在")

    conn = JenkinsConnection(
        url=instance.url,
        username=credential["username"],
        api_token=credential["api_token"],
        verify_ssl=instance.verify_ssl,
    )
    return JenkinsClient(conn)


_DYNAMIC_PARAM_KEYWORDS = {"git", "cascade", "unochoice", "dynamic"}


def _is_dynamic_param(class_name: str) -> bool:
    """Check if a parameter class is known to provide dynamic choices."""
    lower = class_name.lower()
    return any(kw in lower for kw in _DYNAMIC_PARAM_KEYWORDS)


async def _run_client(instance_id: str, member_id: str, handler):
    """Build client, run handler, close client, handle errors."""
    client = await _build_client(instance_id, member_id)
    try:
        return await handler(client)
    except JenkinsClientError as e:
        msg = str(e)
        if "401" in msg:
            raise HTTPException(status_code=422, detail="Jenkins 认证失败，请检查该实例的用户名和 API Token 是否正确")
        if "403" in msg:
            raise HTTPException(status_code=403, detail="Jenkins 权限不足，当前账号无权执行此操作")
        raise HTTPException(status_code=502, detail="Jenkins 请求失败，请检查 Jenkins 服务是否可用")
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateInstanceRequest(BaseModel):
    name: str
    url: str
    verify_ssl: bool = True
    is_default: bool = False


class UpdateInstanceRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    verify_ssl: bool | None = None
    is_default: bool | None = None


class TriggerBuildRequest(BaseModel):
    job_name: str
    parameters: dict | None = None


class SaveCredentialRequest(BaseModel):
    username: str
    api_token: str


class CreateViewRequest(BaseModel):
    name: str
    include_regex: str = ""


# ---------------------------------------------------------------------------
# Per-instance credential management
# ---------------------------------------------------------------------------

@router.get("/instances/{instance_id}/credential")
async def get_instance_credential(request: Request, instance_id: str):
    """Check if current user has credential for this instance."""
    member_id = _get_member_id(request)
    credential = await _get_user_credential(member_id, instance_id)
    if credential:
        return {"configured": True, "username": credential["username"]}
    return {"configured": False}


@router.put("/instances/{instance_id}/credential")
async def save_instance_credential(request: Request, instance_id: str, req: SaveCredentialRequest):
    """Save credential for current user on a specific instance."""
    member_id = _get_member_id(request)

    username = req.username.strip()
    api_token = req.api_token.strip()
    if not username or not api_token:
        raise HTTPException(status_code=400, detail="用户名和 API Token 不能为空")

    # Verify instance exists
    sf = get_db_session_factory()
    async with sf() as session:
        instance = await session.get(JenkinsInstance, instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="实例不存在")

    from openvort.db.models import MemberPluginSetting

    plugin_name = f"jenkins:{instance_id}"
    encrypted_token = encrypt_token(api_token)
    settings_json = json.dumps({"username": username, "api_token": encrypted_token}, ensure_ascii=False)

    async with sf() as session:
        stmt = select(MemberPluginSetting).where(
            MemberPluginSetting.member_id == member_id,
            MemberPluginSetting.plugin_name == plugin_name,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            row.settings_data = settings_json
        else:
            row = MemberPluginSetting(
                member_id=member_id,
                plugin_name=plugin_name,
                settings_data=settings_json,
            )
            session.add(row)
        await session.commit()

    return {"success": True}


@router.delete("/instances/{instance_id}/credential")
async def delete_instance_credential(request: Request, instance_id: str):
    """Delete credential for current user on a specific instance."""
    member_id = _get_member_id(request)

    from openvort.db.models import MemberPluginSetting

    plugin_name = f"jenkins:{instance_id}"
    sf = get_db_session_factory()
    async with sf() as session:
        stmt = select(MemberPluginSetting).where(
            MemberPluginSetting.member_id == member_id,
            MemberPluginSetting.plugin_name == plugin_name,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            await session.delete(row)
            await session.commit()

    return {"success": True}


# ---------------------------------------------------------------------------
# Instance CRUD (admin only for create/update/delete)
# ---------------------------------------------------------------------------

@router.get("/instances")
async def list_instances(request: Request):
    _get_member_id(request)
    sf = get_db_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(JenkinsInstance).order_by(JenkinsInstance.created_at.asc())
        )
        instances = result.scalars().all()

    return {
        "instances": [
            {
                "id": it.id,
                "name": it.name,
                "url": it.url,
                "verify_ssl": bool(it.verify_ssl),
                "is_default": bool(it.is_default),
                "created_at": it.created_at.isoformat() if it.created_at else None,
                "updated_at": it.updated_at.isoformat() if it.updated_at else None,
            }
            for it in instances
        ]
    }


@router.post("/instances")
async def create_instance(request: Request, req: CreateInstanceRequest):
    roles = _get_roles(request)
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    name = req.name.strip()
    url = req.url.strip().rstrip("/")
    if not name:
        raise HTTPException(status_code=400, detail="实例名称不能为空")
    if not url:
        raise HTTPException(status_code=400, detail="Jenkins URL 不能为空")

    sf = get_db_session_factory()
    async with sf() as session:
        exists = await session.scalar(
            select(JenkinsInstance).where(JenkinsInstance.name == name).limit(1)
        )
        if exists:
            raise HTTPException(status_code=409, detail=f"实例名称已存在: {name}")

        count = await session.scalar(select(func.count()).select_from(JenkinsInstance))
        is_default = req.is_default or not count

        if is_default:
            await session.execute(update(JenkinsInstance).values(is_default=False))

        instance = JenkinsInstance(
            id=uuid.uuid4().hex,
            name=name,
            url=url,
            username="",
            api_token="",
            verify_ssl=req.verify_ssl,
            is_default=is_default,
        )
        session.add(instance)
        await session.commit()
        await session.refresh(instance)

    return {
        "id": instance.id,
        "name": instance.name,
        "url": instance.url,
        "verify_ssl": bool(instance.verify_ssl),
        "is_default": bool(instance.is_default),
    }


@router.put("/instances/{instance_id}")
async def update_instance(request: Request, instance_id: str, req: UpdateInstanceRequest):
    roles = _get_roles(request)
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    sf = get_db_session_factory()
    async with sf() as session:
        instance = await session.get(JenkinsInstance, instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="实例不存在")

        if req.name is not None:
            name = req.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="实例名称不能为空")
            if name != instance.name:
                conflict = await session.scalar(
                    select(JenkinsInstance).where(JenkinsInstance.name == name).limit(1)
                )
                if conflict:
                    raise HTTPException(status_code=409, detail=f"实例名称已存在: {name}")
            instance.name = name

        if req.url is not None:
            url = req.url.strip().rstrip("/")
            if not url:
                raise HTTPException(status_code=400, detail="Jenkins URL 不能为空")
            instance.url = url

        if req.verify_ssl is not None:
            instance.verify_ssl = req.verify_ssl

        if req.is_default is not None and req.is_default:
            await session.execute(update(JenkinsInstance).values(is_default=False))
            instance.is_default = True

        await session.commit()
        await session.refresh(instance)

    return {
        "id": instance.id,
        "name": instance.name,
        "url": instance.url,
        "verify_ssl": bool(instance.verify_ssl),
        "is_default": bool(instance.is_default),
    }


@router.delete("/instances/{instance_id}")
async def delete_instance(request: Request, instance_id: str):
    roles = _get_roles(request)
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    sf = get_db_session_factory()
    async with sf() as session:
        instance = await session.get(JenkinsInstance, instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="实例不存在")
        was_default = bool(instance.is_default)
        await session.delete(instance)
        await session.commit()

        if was_default:
            next_default = await session.scalar(
                select(JenkinsInstance).order_by(JenkinsInstance.created_at.asc()).limit(1)
            )
            if next_default:
                next_default.is_default = True
                await session.commit()

    return {"success": True}


# ---------------------------------------------------------------------------
# Jenkins operations (use user personal credential)
# ---------------------------------------------------------------------------

@router.post("/instances/{instance_id}/verify")
async def verify_instance(request: Request, instance_id: str):
    member_id = _get_member_id(request)

    async def handler(client: JenkinsClient):
        data = await client.get_system_info()
        return {"ok": True, "message": "连接成功", "system": data}

    return await _run_client(instance_id, member_id, handler)


@router.get("/instances/{instance_id}/system")
async def get_system_info(request: Request, instance_id: str):
    member_id = _get_member_id(request)

    async def handler(client: JenkinsClient):
        data = await client.get_system_info()
        views = data.get("views", [])
        return {
            "mode": data.get("mode", ""),
            "views": views if isinstance(views, list) else [],
            "num_executors": data.get("numExecutors", 0),
            "quieting_down": data.get("quietingDown", False),
        }

    return await _run_client(instance_id, member_id, handler)


@router.get("/instances/{instance_id}/jobs")
async def list_jobs(
    request: Request,
    instance_id: str,
    view: str = "",
    folder: str = "",
    keyword: str = "",
    recursive: bool = False,
    include_folders: bool = True,
    limit: int = 200,
):
    member_id = _get_member_id(request)

    async def handler(client: JenkinsClient):
        jobs = await client.list_jobs(
            view=view,
            folder=folder,
            keyword=keyword,
            recursive=recursive,
            include_folders=include_folders,
            limit=min(max(1, limit), 500),
        )
        return {"jobs": jobs}

    return await _run_client(instance_id, member_id, handler)


@router.get("/instances/{instance_id}/jobs/info")
async def get_job_info(request: Request, instance_id: str, job_name: str):
    member_id = _get_member_id(request)

    if not job_name.strip():
        raise HTTPException(status_code=400, detail="job_name 不能为空")

    async def handler(client: JenkinsClient):
        info = await client.get_job_info(job_name.strip())

        # Extract parameter definitions with choices
        properties = info.get("property") if isinstance(info, dict) else []
        parameter_defs = []
        if isinstance(properties, list):
            for item in properties:
                defs = item.get("parameterDefinitions") if isinstance(item, dict) else None
                if isinstance(defs, list):
                    for d in defs:
                        param = {
                            "name": d.get("name", ""),
                            "type": d.get("type", ""),
                            "description": d.get("description", ""),
                            "default": ((d.get("defaultParameterValue") or {}).get("value", "")),
                        }
                        choices = d.get("choices")
                        if isinstance(choices, list):
                            param["choices"] = choices
                        else:
                            param_class = d.get("_class", "")
                            if param_class and _is_dynamic_param(param_class):
                                dynamic = await client.get_parameter_choices(
                                    job_name.strip(), param["name"], param_class,
                                )
                                if dynamic:
                                    param["choices"] = dynamic
                        parameter_defs.append(param)

        # Extract build history
        builds_raw = info.get("builds", [])
        builds = []
        if isinstance(builds_raw, list):
            for b in builds_raw:
                if isinstance(b, dict):
                    builds.append({
                        "number": b.get("number"),
                        "result": b.get("result"),
                        "timestamp": b.get("timestamp"),
                        "building": b.get("building", False),
                        "duration": b.get("duration"),
                        "url": b.get("url", ""),
                    })

        return {
            "job": {
                "name": info.get("name", ""),
                "full_name": info.get("fullName", ""),
                "display_name": info.get("displayName", ""),
                "description": info.get("description", ""),
                "url": info.get("url", ""),
                "buildable": info.get("buildable", True),
                "in_queue": info.get("inQueue", False),
                "next_build_number": info.get("nextBuildNumber"),
                "color": info.get("color", ""),
                "last_build": info.get("lastBuild") or None,
                "last_completed_build": info.get("lastCompletedBuild") or None,
                "parameters": parameter_defs,
                "builds": builds,
            }
        }

    return await _run_client(instance_id, member_id, handler)


@router.get("/instances/{instance_id}/jobs/config-summary")
async def get_job_config_summary(request: Request, instance_id: str, job_name: str):
    member_id = _get_member_id(request)

    if not job_name.strip():
        raise HTTPException(status_code=400, detail="job_name 不能为空")

    async def handler(client: JenkinsClient):
        xml_text = await client.get_job_config(job_name.strip())
        summary = JenkinsClient.parse_job_config_xml(xml_text)
        return {"job_name": job_name.strip(), "config_xml": xml_text, **summary}

    return await _run_client(instance_id, member_id, handler)


@router.post("/instances/{instance_id}/jobs/build")
async def trigger_build(request: Request, instance_id: str, req: TriggerBuildRequest):
    member_id = _get_member_id(request)

    job_name = req.job_name.strip()
    if not job_name:
        raise HTTPException(status_code=400, detail="job_name 不能为空")

    async def handler(client: JenkinsClient):
        params = req.parameters or {}
        payload = {str(k): "" if v is None else str(v) for k, v in params.items()}
        result = await client.trigger_build(job_name, payload if payload else None)
        return {"ok": True, "message": "构建已触发", "job_name": job_name, **result}

    return await _run_client(instance_id, member_id, handler)


@router.get("/instances/{instance_id}/builds/status")
async def get_build_status(
    request: Request, instance_id: str, job_name: str, build_number: int
):
    member_id = _get_member_id(request)

    if not job_name.strip():
        raise HTTPException(status_code=400, detail="job_name 不能为空")
    if build_number <= 0:
        raise HTTPException(status_code=400, detail="build_number 必须大于 0")

    async def handler(client: JenkinsClient):
        status = await client.get_build_status(job_name.strip(), build_number)
        return {"build": status}

    return await _run_client(instance_id, member_id, handler)


@router.get("/instances/{instance_id}/builds/log")
async def get_build_log(
    request: Request,
    instance_id: str,
    job_name: str,
    build_number: int,
    tail_lines: int = 200,
):
    member_id = _get_member_id(request)

    if not job_name.strip():
        raise HTTPException(status_code=400, detail="job_name 不能为空")
    if build_number <= 0:
        raise HTTPException(status_code=400, detail="build_number 必须大于 0")

    async def handler(client: JenkinsClient):
        data = await client.get_build_log(
            job_name.strip(), build_number, tail_lines=min(max(1, tail_lines), 5000)
        )
        return data

    return await _run_client(instance_id, member_id, handler)


# ---------------------------------------------------------------------------
# View management
# ---------------------------------------------------------------------------

@router.post("/instances/{instance_id}/views")
async def create_view(request: Request, instance_id: str, req: CreateViewRequest):
    member_id = _get_member_id(request)

    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="视图名称不能为空")

    async def handler(client: JenkinsClient):
        result = await client.create_view(name, include_regex=req.include_regex.strip())
        return {"ok": True, "message": f"视图「{name}」创建成功", **result}

    return await _run_client(instance_id, member_id, handler)


@router.delete("/instances/{instance_id}/views/{view_name}")
async def delete_view(request: Request, instance_id: str, view_name: str):
    member_id = _get_member_id(request)

    if not view_name.strip():
        raise HTTPException(status_code=400, detail="视图名称不能为空")

    async def handler(client: JenkinsClient):
        result = await client.delete_view(view_name.strip())
        return {"ok": True, "message": f"视图「{view_name}」已删除", **result}

    return await _run_client(instance_id, member_id, handler)
