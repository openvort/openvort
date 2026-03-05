"""AI 员工岗位管理路由"""

import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete

from openvort.db.models import Post, PostSkill
from openvort.web.deps import get_db_session_factory

router = APIRouter()


class CreatePostRequest(BaseModel):
    """创建岗位请求"""
    key: str
    name: str
    description: str = ""
    icon: str = ""
    default_persona: str = ""
    default_auto_report: bool = False
    default_report_frequency: str = "daily"


class UpdatePostRequest(BaseModel):
    """更新岗位请求"""
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    default_persona: str | None = None
    default_auto_report: bool | None = None
    default_report_frequency: str | None = None
    enabled: bool | None = None


class BindSkillsRequest(BaseModel):
    skill_ids: list[str]
    priorities: dict[str, int] = {}  # skill_id -> priority


@router.get("")
async def list_posts(
    enabled: bool = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
):
    """列出岗位，可选按 enabled 筛选，支持分页"""
    factory = get_db_session_factory()
    async with factory() as db:
        # 查询总数
        count_stmt = select(Post)
        if enabled is not None:
            count_stmt = count_stmt.where(Post.enabled == enabled)
        from sqlalchemy import func
        count_result = await db.execute(select(func.count()).select_from(count_stmt.subquery()))
        total = count_result.scalar() or 0

        # 分页查询
        stmt = select(Post)
        if enabled is not None:
            stmt = stmt.where(Post.enabled == enabled)
        stmt = stmt.order_by(Post.key).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        rows = result.scalars().all()

    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "key": r.key,
            "name": r.name,
            "description": r.description,
            "icon": r.icon,
            "default_persona": r.default_persona,
            "default_auto_report": r.default_auto_report,
            "default_report_frequency": r.default_report_frequency,
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })

    return {"posts": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{post_key_or_id}")
async def get_post(post_key_or_id: str):
    """获取岗位详情"""
    factory = get_db_session_factory()
    async with factory() as db:
        # 先按 key 查，再按 id 查
        result = await db.execute(
            select(Post).where(Post.key == post_key_or_id)
        )
        post = result.scalar_one_or_none()
        if not post:
            result = await db.execute(
                select(Post).where(Post.id == post_key_or_id)
            )
            post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="岗位不存在")

    return {
        "id": post.id,
        "key": post.key,
        "name": post.name,
        "description": post.description,
        "icon": post.icon,
        "default_persona": post.default_persona,
        "default_auto_report": post.default_auto_report,
        "default_report_frequency": post.default_report_frequency,
        "enabled": post.enabled,
    }


@router.post("")
async def create_post(req: CreatePostRequest):
    """创建岗位"""
    if not req.key.strip():
        raise HTTPException(status_code=400, detail="key 不能为空")
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="名称不能为空")

    factory = get_db_session_factory()
    async with factory() as db:
        # 检查 key 是否已存在
        result = await db.execute(
            select(Post).where(Post.key == req.key)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"岗位 key '{req.key}' 已存在")

        post = Post(
            id=uuid.uuid4().hex,
            key=req.key,
            name=req.name,
            description=req.description,
            icon=req.icon,
            default_persona=req.default_persona,
            default_auto_report=req.default_auto_report,
            default_report_frequency=req.default_report_frequency,
        )
        db.add(post)
        await db.commit()

    return {"success": True, "id": post.id}


@router.put("/{post_id}")
async def update_post(post_id: str, req: UpdatePostRequest):
    """更新岗位"""
    factory = get_db_session_factory()
    async with factory() as db:
        post = await db.get(Post, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="岗位不存在")

        if req.name is not None:
            post.name = req.name
        if req.description is not None:
            post.description = req.description
        if req.icon is not None:
            post.icon = req.icon
        if req.default_persona is not None:
            post.default_persona = req.default_persona
        if req.default_auto_report is not None:
            post.default_auto_report = req.default_auto_report
        if req.default_report_frequency is not None:
            post.default_report_frequency = req.default_report_frequency
        if req.enabled is not None:
            post.enabled = req.enabled

        await db.commit()

    return {"success": True}


@router.delete("/{post_id}")
async def delete_post(post_id: str):
    """删除岗位（逻辑删除，设为 disabled）"""
    factory = get_db_session_factory()
    async with factory() as db:
        post = await db.get(Post, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="岗位不存在")

        # 逻辑删除
        post.enabled = False
        await db.commit()

    return {"success": True}


@router.get("/{post_key_or_id}/skills")
async def get_post_skills(post_key_or_id: str):
    """获取岗位的推荐技能列表"""
    factory = get_db_session_factory()
    async with factory() as db:
        # 查找岗位
        result = await db.execute(
            select(Post).where(Post.key == post_key_or_id)
        )
        post = result.scalar_one_or_none()
        if not post:
            result = await db.execute(
                select(Post).where(Post.id == post_key_or_id)
            )
            post = result.scalar_one_or_none()

        if not post:
            raise HTTPException(status_code=404, detail="岗位不存在")

        # 查找关联的技能
        from openvort.db.models import Skill
        result = await db.execute(
            select(Skill, PostSkill).join(
                PostSkill, PostSkill.skill_id == Skill.id
            ).where(
                PostSkill.role == post.key,
                Skill.enabled == True,  # noqa: E712
            ).order_by(PostSkill.priority)
        )

        skills = []
        for skill, _ in result.all():
            skills.append({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "scope": skill.scope,
                "skill_type": skill.skill_type,
            })

    return {"skills": skills}


@router.put("/{post_key_or_id}/skills")
async def bind_post_skills(post_key_or_id: str, req: BindSkillsRequest):
    """重置岗位的推荐技能列表"""
    factory = get_db_session_factory()
    async with factory() as db:
        # 查找岗位
        result = await db.execute(
            select(Post).where(Post.key == post_key_or_id)
        )
        post = result.scalar_one_or_none()
        if not post:
            result = await db.execute(
                select(Post).where(Post.id == post_key_or_id)
            )
            post = result.scalar_one_or_none()

        if not post:
            raise HTTPException(status_code=404, detail="岗位不存在")

        # 删除旧的映射
        await db.execute(
            delete(PostSkill).where(PostSkill.role == post.key)
        )

        # 添加新的映射
        for skill_id in req.skill_ids:
            priority = req.priorities.get(skill_id, 0)
            db.add(PostSkill(
                role=post.key,
                skill_id=skill_id,
                priority=priority,
            ))

        await db.commit()

    return {"success": True}


@router.get("/{post_key_or_id}/generate-persona-prompt")
async def generate_persona_prompt(post_key_or_id: str):
    """生成 AI 创建 persona 的 prompt，前端跳转 chat 页使用"""
    factory = get_db_session_factory()
    async with factory() as db:
        # 查找岗位
        result = await db.execute(
            select(Post).where(Post.key == post_key_or_id)
        )
        post = result.scalar_one_or_none()
        if not post:
            result = await db.execute(
                select(Post).where(Post.id == post_key_or_id)
            )
            post = result.scalar_one_or_none()

        if not post:
            raise HTTPException(status_code=404, detail="岗位不存在")

        # 获取岗位已有的技能
        from openvort.db.models import Skill
        result = await db.execute(
            select(Skill, PostSkill).join(
                PostSkill, PostSkill.skill_id == Skill.id
            ).where(
                PostSkill.role == post.key,
                Skill.enabled == True,  # noqa: E712
            ).order_by(PostSkill.priority)
        )
        skills = [s for s, _ in result.all()]

    if not skills:
        return {"prompt": f"请为团队 AI 员工岗位「{post.name}」生成一段专业、有特色的 Persona 描述（200字以内）。这位岗位目前还没有配置技能，请基于岗位名称「{post.key}」生成一段合适的人设描述。"}

    skills_text = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    prompt = (
        f"请根据以下岗位已有技能信息，为团队 AI 员工岗位「{post.name}」生成一段专业、有特色的 Persona 描述（200字以内）。\n"
        f"要求：像真人自我介绍一样写，突出该岗位的专业领域和核心能力，让人一眼就能理解这个 AI 员工能做什么。\n\n"
        f"岗位已有技能：\n{skills_text}"
    )
    return {"prompt": prompt}
