"""Skill 管理路由（管理员：内置 + 公共）"""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from openvort.db.models import Skill
from openvort.skill.directories import SkillDirectoryManager
from openvort.skill.importer import GitHubImporter
from openvort.skill.loader import SkillLoader
from openvort.web.deps import get_db_session_factory, get_skill_loader

router = APIRouter()


class CreateSkillRequest(BaseModel):
    name: str
    description: str = ""
    content: str = ""
    skill_type: str = "workflow"  # role / workflow / knowledge / template / guideline


class UpdateSkillRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    skill_type: str | None = None


# === 新增：多目录和 GitHub 导入功能 ===

@router.get("/directories")
async def list_skill_directories():
    """列出所有 Skill 扫描目录"""
    directories = SkillDirectoryManager.get_all_directories()
    return {"directories": directories}


@router.get("")
async def list_skills(skill_type: str = ""):
    """列出所有 Skill（builtin + public），可按 skill_type 筛选"""
    factory = get_db_session_factory()
    async with factory() as db:
        stmt = select(Skill).where(Skill.scope.in_(["builtin", "public"]))
        if skill_type:
            stmt = stmt.where(Skill.skill_type == skill_type)
        stmt = stmt.order_by(Skill.skill_type, Skill.sort_order, Skill.name)
        result = await db.execute(stmt)
        rows = result.scalars().all()

    items = []
    for s in rows:
        items.append({
            "id": s.id, "name": s.name, "description": s.description,
            "scope": s.scope, "skill_type": s.skill_type, "enabled": s.enabled,
        })

    return {"skills": items}


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """获取 Skill 详情（含完整 markdown 内容）"""
    factory = get_db_session_factory()
    async with factory() as db:
        row = await db.get(Skill, skill_id)
    if not row:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return {
        "id": row.id, "name": row.name, "description": row.description,
        "content": row.content, "scope": row.scope, "skill_type": row.skill_type,
        "enabled": row.enabled,
    }


@router.post("")
async def create_skill(req: CreateSkillRequest):
    """创建公共 Skill"""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="名称不能为空")

    factory = get_db_session_factory()
    async with factory() as db:
        existing = await db.execute(
            select(Skill).where(Skill.name == req.name, Skill.scope.in_(["builtin", "public"]))
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Skill '{req.name}' 已存在")

        skill = Skill(
            id=uuid.uuid4().hex,
            name=req.name,
            description=req.description,
            content=req.content,
            scope="public",
            skill_type=req.skill_type,
        )
        db.add(skill)
        await db.commit()

    return {"success": True, "id": skill.id}


@router.put("/{skill_id}")
async def update_skill(skill_id: str, req: UpdateSkillRequest):
    """更新 Skill 内容（仅公共 Skill 可编辑）"""
    factory = get_db_session_factory()
    async with factory() as db:
        row = await db.get(Skill, skill_id)
        if not row:
            raise HTTPException(status_code=404, detail="Skill 不存在")
        if row.scope == "builtin":
            raise HTTPException(status_code=403, detail="内置 Skill 不可编辑")
        if row.scope == "personal":
            raise HTTPException(status_code=403, detail="请通过成员技能接口编辑")

        if req.name is not None:
            row.name = req.name
        if req.description is not None:
            row.description = req.description
        if req.content is not None:
            row.content = req.content
        if req.skill_type is not None:
            row.skill_type = req.skill_type
        await db.commit()

    return {"success": True}


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    """删除 Skill（仅公共 Skill 可删除）"""
    factory = get_db_session_factory()
    async with factory() as db:
        row = await db.get(Skill, skill_id)
        if not row:
            raise HTTPException(status_code=404, detail="Skill 不存在")
        if row.scope == "builtin":
            raise HTTPException(status_code=403, detail="内置 Skill 不可删除")
        if row.scope == "personal":
            raise HTTPException(status_code=403, detail="请通过成员技能接口删除")

        await db.delete(row)
        await db.commit()

    return {"success": True}


@router.post("/{skill_id}/toggle")
async def toggle_skill(skill_id: str):
    """启用/禁用 Skill"""
    factory = get_db_session_factory()
    async with factory() as db:
        row = await db.get(Skill, skill_id)
        if not row:
            raise HTTPException(status_code=404, detail="Skill 不存在")

        row.enabled = not row.enabled
        await db.commit()
        new_state = row.enabled

    return {"success": True, "enabled": new_state}


# === 新增：多目录和 GitHub 导入功能 ===

@router.get("/directories")
async def list_skill_directories():
    """列出所有 Skill 扫描目录"""
    directories = SkillDirectoryManager.get_all_directories()
    return {"directories": directories}


@router.get("/search-online")
async def search_online_skills(q: str, limit: int = 10):
    """搜索 GitHub 上的 Skills"""
    importer = GitHubImporter()
    results = await importer.search(q, limit=limit)
    return {"results": results}


class ImportSkillRequest(BaseModel):
    url: str
    owner_id: str = ""


@router.post("/import")
async def import_skill_from_github(req: ImportSkillRequest):
    """从 GitHub URL 导入 Skill"""
    importer = GitHubImporter()

    try:
        result = await importer.import_from_url(req.url, req.owner_id)
        return {"success": True, "skill": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/import/repos/{owner}/{repo}")
async def get_github_repo_info(owner: str, repo: str):
    """获取 GitHub 仓库信息"""
    importer = GitHubImporter()
    result = await importer.get_readme_from_repo(f"https://github.com/{owner}/{repo}")
    if not result:
        raise HTTPException(status_code=404, detail="仓库不存在或无法访问")
    return result


@router.get("/{skill_id}/generate-content-prompt")
async def generate_skill_content_prompt(skill_id: str):
    """生成 AI 创建/优化 Skill 内容的 prompt，前端跳转 chat 页使用"""
    factory = get_db_session_factory()
    async with factory() as db:
        skill = await db.get(Skill, skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill 不存在")

    prompt = (
        f"请为 Skill「{skill.name}」生成专业、详细的技能描述内容。\n\n"
        f"现有信息：\n"
        f"- 名称：{skill.name}\n"
        f"- 描述：{skill.description or '暂无'}\n\n"
        f"请生成一份完整的 Skill 内容（Markdown 格式），包括：\n"
        f"1. 技能概述\n"
        f"2. 适用场景\n"
        f"3. 使用方法/最佳实践\n"
        f"4. 注意事项\n\n"
        f"要求：内容要专业、实用，能帮助 AI 员工更好地执行相关任务。"
    )
    return {"prompt": prompt}
