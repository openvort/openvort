"""成员技能路由（登录用户：个人 Skill CRUD + 公共 Skill 订阅）"""

import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from openvort.contacts.models import Member
from openvort.db.models import MemberSkill, Skill
from openvort.web.deps import get_db_session_factory

router = APIRouter()


class CreatePersonalSkillRequest(BaseModel):
    name: str
    description: str = ""
    content: str = ""


class UpdatePersonalSkillRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None


class UpdateMemberBioRequest(BaseModel):
    bio: str


# ---- Member personal skills ----


@router.get("/member/{member_id}")
async def get_member_skills(member_id: str):
    """获取成员的个人技能 + 已订阅的公共技能"""
    factory = get_db_session_factory()
    async with factory() as db:
        member = await db.get(Member, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="成员不存在")

        # Personal skills
        result = await db.execute(
            select(Skill).where(
                Skill.scope == "personal", Skill.owner_id == member_id
            ).order_by(Skill.sort_order, Skill.name)
        )
        personal = [
            {"id": s.id, "name": s.name, "description": s.description,
             "content": s.content, "enabled": s.enabled}
            for s in result.scalars().all()
        ]

        # Subscribed public skills
        result = await db.execute(
            select(Skill, MemberSkill.enabled).join(
                MemberSkill, MemberSkill.skill_id == Skill.id
            ).where(MemberSkill.member_id == member_id)
        )
        subscribed = [
            {"id": row[0].id, "name": row[0].name, "description": row[0].description,
             "subscribed": True, "enabled": row[1]}
            for row in result.all()
        ]

    return {
        "member_id": member_id,
        "name": member.name,
        "bio": member.bio,
        "personal": personal,
        "subscribed": subscribed,
    }


@router.post("/member/{member_id}/personal")
async def create_personal_skill(member_id: str, req: CreatePersonalSkillRequest):
    """为成员新增个人技能"""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="名称不能为空")

    factory = get_db_session_factory()
    async with factory() as db:
        member = await db.get(Member, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="成员不存在")

        skill = Skill(
            id=uuid.uuid4().hex,
            name=req.name,
            description=req.description,
            content=req.content,
            scope="personal",
            owner_id=member_id,
        )
        db.add(skill)
        await db.commit()

    return {"success": True, "id": skill.id}


@router.put("/personal/{skill_id}")
async def update_personal_skill(skill_id: str, req: UpdatePersonalSkillRequest):
    """更新个人技能"""
    factory = get_db_session_factory()
    async with factory() as db:
        row = await db.get(Skill, skill_id)
        if not row:
            raise HTTPException(status_code=404, detail="Skill 不存在")
        if row.scope != "personal":
            raise HTTPException(status_code=403, detail="仅可编辑个人技能")

        if req.name is not None:
            row.name = req.name
        if req.description is not None:
            row.description = req.description
        if req.content is not None:
            row.content = req.content
        await db.commit()

    return {"success": True}


@router.delete("/personal/{skill_id}")
async def delete_personal_skill(skill_id: str):
    """删除个人技能"""
    factory = get_db_session_factory()
    async with factory() as db:
        row = await db.get(Skill, skill_id)
        if not row:
            raise HTTPException(status_code=404, detail="Skill 不存在")
        if row.scope != "personal":
            raise HTTPException(status_code=403, detail="仅可删除个人技能")

        await db.delete(row)
        await db.commit()

    return {"success": True}


# ---- Public skill subscription ----


@router.get("/public")
async def list_public_skills():
    """列出所有公共技能（供订阅 UI）"""
    factory = get_db_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(Skill).where(Skill.scope == "public", Skill.enabled == True).order_by(Skill.sort_order, Skill.name)  # noqa: E712
        )
        skills = [
            {"id": s.id, "name": s.name, "description": s.description}
            for s in result.scalars().all()
        ]
    return {"skills": skills}


@router.post("/member/{member_id}/subscribe/{skill_id}")
async def subscribe_skill(member_id: str, skill_id: str):
    """成员订阅公共技能"""
    factory = get_db_session_factory()
    async with factory() as db:
        skill = await db.get(Skill, skill_id)
        if not skill or skill.scope != "public":
            raise HTTPException(status_code=404, detail="公共技能不存在")

        existing = await db.execute(
            select(MemberSkill).where(
                MemberSkill.member_id == member_id, MemberSkill.skill_id == skill_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="已订阅")

        db.add(MemberSkill(member_id=member_id, skill_id=skill_id))
        await db.commit()

    return {"success": True}


@router.delete("/member/{member_id}/subscribe/{skill_id}")
async def unsubscribe_skill(member_id: str, skill_id: str):
    """成员取消订阅公共技能"""
    factory = get_db_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(MemberSkill).where(
                MemberSkill.member_id == member_id, MemberSkill.skill_id == skill_id
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="未订阅")

        await db.delete(row)
        await db.commit()

    return {"success": True}


# ---- Bio management ----


@router.put("/member/{member_id}/bio")
async def update_member_bio(member_id: str, req: UpdateMemberBioRequest):
    """更新成员 bio"""
    factory = get_db_session_factory()
    async with factory() as db:
        member = await db.get(Member, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="成员不存在")
        member.bio = req.bio
        await db.commit()

    return {"success": True}


@router.get("/member/{member_id}/generate-bio-prompt")
async def generate_bio_prompt(member_id: str):
    """生成 AI 创建 bio 的 prompt，前端跳转 chat 页使用"""
    factory = get_db_session_factory()
    async with factory() as db:
        member = await db.get(Member, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="成员不存在")

        result = await db.execute(
            select(Skill).where(
                Skill.scope == "personal", Skill.owner_id == member_id, Skill.enabled == True  # noqa: E712
            ).order_by(Skill.sort_order)
        )
        skills = result.scalars().all()

    if not skills:
        return {"prompt": f"请为团队成员「{member.name}」生成一段自然、有人格感的个人简介（200字以内）。这位成员目前还没有填写技能信息，请基于名字生成一段通用的专业简介。"}

    skills_text = "\n".join(f"- {s.name}: {s.content[:200]}" for s in skills if s.content)
    prompt = (
        f"请根据以下技能信息，为团队成员「{member.name}」生成一段自然、有人格感的个人简介（200字以内）。\n"
        f"要求：像真人自我介绍一样写，不要干巴巴地罗列技能，而是用流畅的语言描述这个人的专业背景和特点。\n\n"
        f"技能信息：\n{skills_text}"
    )
    return {"prompt": prompt}
