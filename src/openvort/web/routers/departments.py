"""部门管理路由"""

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.web.deps import get_db_session_factory

router = APIRouter()


def _get_service():
    from openvort.contacts.service import ContactService
    session_factory = get_db_session_factory()
    return ContactService(session_factory)


# ---- 请求模型 ----

class CreateDepartmentRequest(BaseModel):
    name: str
    parent_id: int | None = None


class UpdateDepartmentRequest(BaseModel):
    name: str | None = None
    parent_id: int | None = ...
    order: int | None = None


class AddMemberRequest(BaseModel):
    member_id: str
    is_primary: bool = False


# ---- 部门 CRUD ----

@router.get("")
async def get_department_tree(platform: str = ""):
    """获取部门树（含成员数）"""
    try:
        service = _get_service()
        tree = await service.get_department_tree(platform)
        return {"departments": tree}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"departments": [], "error": str(e)}


@router.get("/{dept_id}")
async def get_department(dept_id: int):
    """部门详情"""
    service = _get_service()
    dept = await service.get_department(dept_id)
    if not dept:
        return {"error": "部门不存在"}
    return {
        "id": dept.id,
        "name": dept.name,
        "parent_id": dept.parent_id,
        "platform": dept.platform,
        "platform_dept_id": dept.platform_dept_id,
        "order": dept.order,
    }


@router.post("")
async def create_department(req: CreateDepartmentRequest):
    """创建部门"""
    try:
        service = _get_service()
        dept = await service.create_department(req.name, req.parent_id)
        return {"success": True, "id": dept.id}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.put("/{dept_id}")
async def update_department(dept_id: int, req: UpdateDepartmentRequest):
    """编辑部门"""
    service = _get_service()
    ok = await service.update_department(
        dept_id,
        name=req.name,
        parent_id=req.parent_id,
        order=req.order,
    )
    return {"success": ok}


@router.delete("/{dept_id}")
async def delete_department(dept_id: int):
    """删除部门"""
    service = _get_service()
    ok = await service.delete_department(dept_id)
    return {"success": ok}


# ---- 部门成员 ----

@router.get("/{dept_id}/members")
async def get_department_members(dept_id: int):
    """部门成员列表"""
    try:
        service = _get_service()
        members = await service.get_department_members(dept_id)
        return {"members": members}
    except Exception as e:
        return {"members": [], "error": str(e)}


@router.post("/{dept_id}/members")
async def add_department_member(dept_id: int, req: AddMemberRequest):
    """添加成员到部门"""
    service = _get_service()
    ok = await service.add_member_to_department(dept_id, req.member_id, req.is_primary)
    return {"success": ok}


@router.delete("/{dept_id}/members/{member_id}")
async def remove_department_member(dept_id: int, member_id: str):
    """移除部门成员"""
    service = _get_service()
    ok = await service.remove_member_from_department(dept_id, member_id)
    return {"success": ok}
