from fastapi import APIRouter
from sqlalchemy import select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import FlowDescriptionTemplate

from .schemas import DescriptionTemplateUpdate

sub_router = APIRouter()

VALID_TYPES = ("需求", "任务", "缺陷")

@sub_router.get("/description-templates")
async def list_description_templates():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(FlowDescriptionTemplate))
        rows = result.scalars().all()
        items = {r.work_item_type: r.content for r in rows}
    return {"items": {t: items.get(t, "") for t in VALID_TYPES}}


@sub_router.put("/description-templates/{work_item_type}")
async def update_description_template(work_item_type: str, body: DescriptionTemplateUpdate):
    if work_item_type not in VALID_TYPES:
        return {"error": f"无效的工作项类型: {work_item_type}"}
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(FlowDescriptionTemplate).where(
                FlowDescriptionTemplate.work_item_type == work_item_type
            )
        )
        tpl = result.scalar_one_or_none()
        if tpl:
            tpl.content = body.content
        else:
            tpl = FlowDescriptionTemplate(work_item_type=work_item_type, content=body.content)
            session.add(tpl)
        await session.commit()
    return {"ok": True}
