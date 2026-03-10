"""OpenClaw remote work node management API."""

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.web.deps import get_db_session_factory

router = APIRouter()


def _get_service():
    from openvort.core.openclaw_node import OpenClawNodeService
    return OpenClawNodeService(get_db_session_factory())


# ---- Request models ----

class CreateNodeRequest(BaseModel):
    name: str
    gateway_url: str
    gateway_token: str
    description: str = ""


class UpdateNodeRequest(BaseModel):
    name: str | None = None
    gateway_url: str | None = None
    gateway_token: str | None = None
    description: str | None = None


# ---- Endpoints ----

@router.get("")
async def list_nodes():
    """List all OpenClaw nodes."""
    service = _get_service()
    nodes = await service.list_nodes()

    # Attach bound member count
    for node in nodes:
        members = await service.get_bound_members(node["id"])
        node["bound_member_count"] = len(members)

    return {"nodes": nodes}


@router.post("")
async def create_node(req: CreateNodeRequest):
    """Create a new OpenClaw node."""
    if not req.name or not req.gateway_url or not req.gateway_token:
        return {"success": False, "error": "名称、Gateway 地址和 Gateway Token 不能为空"}

    service = _get_service()
    node = await service.create_node(
        name=req.name,
        gateway_url=req.gateway_url,
        gateway_token=req.gateway_token,
        description=req.description,
    )
    return {"success": True, "node": node}


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

    node = await service.update_node(node_id, **kwargs)
    if not node:
        return {"success": False, "error": "节点不存在"}
    return {"success": True, "node": node}


@router.delete("/{node_id}")
async def delete_node(node_id: str):
    """Delete node and unbind all employees."""
    service = _get_service()
    ok = await service.delete_node(node_id)
    if not ok:
        return {"success": False, "error": "节点不存在"}
    return {"success": True}


@router.post("/{node_id}/test")
async def test_connection(node_id: str):
    """Test node connectivity."""
    service = _get_service()
    result = await service.test_connection(node_id)
    return result


@router.get("/{node_id}/members")
async def get_bound_members(node_id: str):
    """List AI employees bound to this node."""
    service = _get_service()
    members = await service.get_bound_members(node_id)
    return {"members": members}
