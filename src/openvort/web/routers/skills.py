"""Skill 管理路由"""

import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from openvort.web.deps import get_skill_loader

router = APIRouter()


class CreateSkillRequest(BaseModel):
    name: str
    description: str = ""
    content: str = ""


class UpdateSkillRequest(BaseModel):
    description: str | None = None
    content: str | None = None


@router.get("")
async def list_skills():
    """列出所有 Skill"""
    loader = get_skill_loader()
    skills = loader.get_skills()

    builtin = []
    workspace = []
    for s in skills:
        item = {
            "name": s.name,
            "description": s.description,
            "source": s.source,
            "enabled": s.enabled,
        }
        if s.source == "builtin":
            builtin.append(item)
        else:
            workspace.append(item)

    return {"builtin": builtin, "workspace": workspace}


@router.get("/{name}")
async def get_skill(name: str):
    """获取 Skill 详情（含完整 markdown 内容）"""
    loader = get_skill_loader()
    skill = loader.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 不存在")

    return {
        "name": skill.name,
        "description": skill.description,
        "content": skill.content,
        "source": skill.source,
        "enabled": skill.enabled,
    }


@router.post("")
async def create_skill(req: CreateSkillRequest):
    """创建 workspace Skill"""
    loader = get_skill_loader()

    if loader.get_skill(req.name):
        raise HTTPException(status_code=409, detail=f"Skill '{req.name}' 已存在")

    path = loader.create_skill(req.name)
    if not path:
        raise HTTPException(status_code=500, detail="创建 Skill 失败")

    # 如果提供了 description 或 content，回写文件
    if req.description or req.content:
        content = req.content or f"# {req.name}\n\n在此编写 Skill 内容..."
        file_content = (
            f"---\nname: {req.name}\n"
            f"description: {req.description}\n"
            f"enabled: true\n---\n\n{content}\n"
        )
        path.write_text(file_content, encoding="utf-8")

    # 重新加载该 Skill
    from openvort.skill.loader import _parse_skill_file
    skill = _parse_skill_file(path, "workspace")
    if skill:
        loader._skills[skill.name] = skill

    return {"success": True, "name": req.name}


@router.put("/{name}")
async def update_skill(name: str, req: UpdateSkillRequest):
    """更新 Skill 内容（仅 workspace 来源可编辑）"""
    loader = get_skill_loader()
    skill = loader.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 不存在")
    if skill.source != "workspace":
        raise HTTPException(status_code=403, detail="内置 Skill 不可编辑")

    # 构建新文件内容
    description = req.description if req.description is not None else skill.description
    content = req.content if req.content is not None else skill.content

    file_content = (
        f"---\nname: {name}\n"
        f"description: {description}\n"
        f"enabled: {str(skill.enabled).lower()}\n---\n\n{content}\n"
    )

    try:
        skill.path.write_text(file_content, encoding="utf-8")
        skill.description = description
        skill.content = content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入失败: {e}")

    return {"success": True}


@router.delete("/{name}")
async def delete_skill(name: str):
    """删除 Skill（仅 workspace 来源可删除）"""
    loader = get_skill_loader()
    skill = loader.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 不存在")
    if skill.source != "workspace":
        raise HTTPException(status_code=403, detail="内置 Skill 不可删除")

    try:
        # 删除整个 Skill 目录
        skill_dir = skill.path.parent
        shutil.rmtree(skill_dir)
        del loader._skills[name]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")

    return {"success": True}


@router.post("/{name}/toggle")
async def toggle_skill(name: str):
    """启用/禁用 Skill"""
    loader = get_skill_loader()
    skill = loader.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 不存在")

    new_state = not skill.enabled
    ok = loader.enable_skill(name) if new_state else loader.disable_skill(name)
    if not ok:
        raise HTTPException(status_code=500, detail="操作失败")

    return {"success": True, "enabled": new_state}
