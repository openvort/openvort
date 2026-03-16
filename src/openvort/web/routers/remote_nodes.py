"""Remote work node management API.

Supports both OpenClaw remote nodes and Docker container nodes.
Docker nodes additionally expose lifecycle (start/stop/restart),
container logs, resource stats, and a WebSocket terminal proxy.

IMPORTANT: Static path routes (/docker/*) must be defined BEFORE
parameterized routes (/{node_id}/*) to avoid path conflicts.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

from openvort.web.deps import get_db_session_factory

router = APIRouter()


def _get_service():
    from openvort.core.remote_node import RemoteNodeService
    return RemoteNodeService(get_db_session_factory())


# ---- Request models ----

class CreateNodeRequest(BaseModel):
    name: str
    node_type: str = "openclaw"
    gateway_url: str = ""
    gateway_token: str = ""
    image: str = ""
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    network_mode: str = "host"
    env_vars: dict[str, str] = {}
    description: str = ""


class UpdateNodeRequest(BaseModel):
    name: str | None = None
    gateway_url: str | None = None
    gateway_token: str | None = None
    description: str | None = None
    node_type: str | None = None
    config: dict | None = None


# ---- Docker image & stats routes (MUST be before /{node_id} routes) ----

@router.get("/docker/images")
async def list_docker_images():
    """List locally available Docker images."""
    from openvort.core.docker_executor import DockerExecutor
    images = await DockerExecutor().list_local_images()
    return {"images": images}


@router.post("/docker/pull-image")
async def pull_docker_image(body: dict):
    """Pull a Docker image."""
    image = body.get("image", "")
    if not image:
        return {"ok": False, "message": "请指定镜像名"}
    from openvort.core.docker_executor import DockerExecutor
    result = await DockerExecutor().pull_image(image)
    return result


@router.get("/docker/stats")
async def all_docker_stats():
    """Get resource stats for all running Docker nodes."""
    service = _get_service()
    stats = await service.get_all_docker_stats()
    return {"stats": stats}


# ---- Shared CRUD endpoints ----

@router.get("")
async def list_nodes():
    """List all remote nodes."""
    service = _get_service()
    nodes = await service.list_nodes()

    for node in nodes:
        members = await service.get_bound_members(node["id"])
        node["bound_member_count"] = len(members)

    return {"nodes": nodes}


@router.post("")
async def create_node(req: CreateNodeRequest):
    """Create a new node (OpenClaw or Docker)."""
    if not req.name:
        return {"success": False, "error": "名称不能为空"}

    service = _get_service()

    if req.node_type == "docker":
        if not req.image:
            return {"success": False, "error": "请选择 Docker 镜像"}
        node = await service.create_docker_node(
            name=req.name,
            image=req.image,
            memory_limit=req.memory_limit,
            cpu_limit=req.cpu_limit,
            network_mode=req.network_mode,
            env_vars=req.env_vars or {},
            description=req.description,
        )
        create_result = node.pop("_create_result", {})
        if not create_result.get("ok"):
            return {"success": False, "error": create_result.get("message", "创建容器失败"), "node": node}
        return {"success": True, "node": node}
    else:
        if not req.gateway_url or not req.gateway_token:
            return {"success": False, "error": "Gateway 地址和 Token 不能为空"}
        node = await service.create_node(
            name=req.name,
            gateway_url=req.gateway_url,
            gateway_token=req.gateway_token,
            description=req.description,
            node_type=req.node_type,
        )
        return {"success": True, "node": node}


# ---- Parameterized node routes ----

@router.get("/{node_id}")
async def get_node(node_id: str):
    """Get node details."""
    service = _get_service()
    node = await service.get_node(node_id)
    if not node:
        return {"error": "节点不存在"}, 404
    return node


@router.put("/{node_id}")
async def update_node(node_id: str, req: UpdateNodeRequest):
    """Update node configuration."""
    service = _get_service()
    kwargs = {}
    if req.name is not None:
        kwargs["name"] = req.name
    if req.gateway_url is not None:
        kwargs["gateway_url"] = req.gateway_url
    if req.gateway_token is not None:
        kwargs["gateway_token"] = req.gateway_token
    if req.description is not None:
        kwargs["description"] = req.description
    if req.node_type is not None:
        kwargs["node_type"] = req.node_type
    if req.config is not None:
        kwargs["config"] = req.config

    node = await service.update_node(node_id, **kwargs)
    if not node:
        return {"success": False, "error": "节点不存在"}
    return {"success": True, "node": node}


@router.delete("/{node_id}")
async def delete_node(node_id: str):
    """Delete node. For Docker nodes, also remove the container."""
    service = _get_service()
    node = await service.get_node(node_id)
    if not node:
        return {"success": False, "error": "节点不存在"}

    if node.get("node_type") == "docker":
        await service.remove_docker_container(node_id)

    ok = await service.delete_node(node_id)
    if not ok:
        return {"success": False, "error": "删除失败"}
    return {"success": True}


@router.post("/{node_id}/test")
async def test_connection(node_id: str):
    """Test node connectivity / check Docker container status."""
    service = _get_service()
    return await service.test_connection(node_id)


@router.get("/{node_id}/members")
async def get_bound_members(node_id: str):
    """List AI employees bound to this node."""
    service = _get_service()
    members = await service.get_bound_members(node_id)
    return {"members": members}


@router.post("/{node_id}/start")
async def start_container(node_id: str):
    """Start a stopped Docker container."""
    return await _get_service().start_docker_container(node_id)


@router.post("/{node_id}/stop")
async def stop_container(node_id: str):
    """Stop a running Docker container."""
    return await _get_service().stop_docker_container(node_id)


@router.post("/{node_id}/restart")
async def restart_container(node_id: str):
    """Restart a Docker container."""
    return await _get_service().restart_docker_container(node_id)


@router.get("/{node_id}/container-status")
async def container_status(node_id: str):
    """Get detailed Docker container status."""
    return await _get_service().get_docker_status(node_id)


@router.get("/{node_id}/container-stats")
async def container_stats(node_id: str):
    """Get CPU/memory stats for a Docker container."""
    return await _get_service().get_docker_stats(node_id)


@router.get("/{node_id}/logs")
async def container_logs(node_id: str, tail: int = Query(100, ge=1, le=1000)):
    """Get recent Docker container logs."""
    logs = await _get_service().get_docker_logs(node_id, tail=tail)
    return {"logs": logs}


# ---- WebSocket terminal proxy ----

@router.websocket("/{node_id}/terminal")
async def terminal_proxy(ws: WebSocket, node_id: str, token: str = ""):
    """WebSocket terminal: forward I/O between xterm.js and docker exec with PTY."""
    import fcntl
    import json
    import os
    import pty
    import signal
    import struct
    import termios

    from openvort.web.auth import verify_token

    payload = verify_token(token) if token else None
    if not payload or "admin" not in payload.get("roles", []):
        await ws.close(code=4003, reason="未授权")
        return

    await ws.accept()

    service = _get_service()
    node = await service.get_node(node_id)
    if not node or node.get("node_type") != "docker":
        await ws.close(code=4000, reason="节点不存在或不是 Docker 类型")
        return
    cid = (node.get("config") or {}).get("container_id", "")
    if not cid:
        await ws.close(code=4001, reason="容器 ID 不存在")
        return

    master_fd, slave_fd = pty.openpty()
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-it", cid, "/bin/bash",
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
        )
    except Exception as exc:
        os.close(master_fd)
        os.close(slave_fd)
        await ws.close(code=4002, reason=str(exc))
        return

    os.close(slave_fd)

    loop = asyncio.get_event_loop()

    def _set_winsize(cols: int, rows: int):
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
            os.kill(proc.pid, signal.SIGWINCH)
        except Exception:
            pass

    async def _read_pty():
        try:
            while True:
                data = await loop.run_in_executor(None, os.read, master_fd, 4096)
                if not data:
                    break
                await ws.send_bytes(data)
        except OSError:
            pass
        except Exception:
            pass

    async def _read_ws():
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                raw = msg.get("bytes") or (msg.get("text", "").encode())
                if not raw:
                    continue
                if raw[:1] == b"\x01":
                    try:
                        resize = json.loads(raw[1:])
                        _set_winsize(resize.get("cols", 80), resize.get("rows", 24))
                    except Exception:
                        pass
                    continue
                await loop.run_in_executor(None, os.write, master_fd, raw)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    read_task = asyncio.create_task(_read_pty())
    ws_task = asyncio.create_task(_read_ws())

    try:
        await asyncio.wait([read_task, ws_task], return_when=asyncio.FIRST_COMPLETED)
    finally:
        read_task.cancel()
        ws_task.cancel()
        if proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            await ws.close()
        except Exception:
            pass
