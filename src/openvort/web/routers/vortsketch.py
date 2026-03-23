"""VortSketch API router — sketch CRUD + page management + SSE generation."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sse_starlette.sse import EventSourceResponse

from openvort.utils.logging import get_logger

log = get_logger("web.routers.vortsketch")

router = APIRouter(prefix="/api/sketches", tags=["vortsketch"])


# ---- Request / Response Models ----


class CreateSketchRequest(BaseModel):
    name: str
    description: str = ""
    project_id: str | None = None
    story_id: str | None = None
    story_type: str = ""


class UpdateSketchRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_archived: bool | None = None


class CreatePageRequest(BaseModel):
    name: str


class UpdatePageRequest(BaseModel):
    name: str | None = None
    sort_order: int | None = None


class ImageBlock(BaseModel):
    data: str
    media_type: str = "image/png"


class GeneratePageRequest(BaseModel):
    description: str = ""
    images: list[ImageBlock] = []


class IteratePageRequest(BaseModel):
    instruction: str
    images: list[ImageBlock] = []


# ---- Helpers ----


def _get_member_id(request: Request) -> str:
    from openvort.web.app import require_auth
    payload = require_auth(request)
    return payload.get("sub", "")


def _get_session_factory():
    from openvort.web.deps import get_db_session_factory
    return get_db_session_factory()


def _get_generator():
    from openvort.config.settings import get_settings
    from openvort.core.engine.llm import LLMClient
    from openvort.plugins.vortsketch.generator import SketchGenerator
    settings = get_settings()
    llm = LLMClient(settings.llm.get_model_chain())
    return SketchGenerator(llm)


# ---- Sketch CRUD ----


@router.get("")
async def list_sketches(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    project_id: str = "",
    is_archived: bool = False,
):
    from openvort.plugins.vortsketch.models import Sketch, SketchPage

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        q = select(Sketch).where(Sketch.is_archived == is_archived)
        count_q = select(func.count()).select_from(Sketch).where(Sketch.is_archived == is_archived)

        if keyword:
            like = f"%{keyword}%"
            q = q.where(Sketch.name.ilike(like) | Sketch.description.ilike(like))
            count_q = count_q.where(Sketch.name.ilike(like) | Sketch.description.ilike(like))
        if project_id:
            q = q.where(Sketch.project_id == project_id)
            count_q = count_q.where(Sketch.project_id == project_id)

        total = (await session.execute(count_q)).scalar() or 0
        q = q.order_by(Sketch.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(q)).scalars().all()

        page_counts: dict[str, int] = {}
        sketch_ids = [s.id for s in rows]
        if sketch_ids:
            pc_q = (
                select(SketchPage.sketch_id, func.count().label("cnt"))
                .where(SketchPage.sketch_id.in_(sketch_ids))
                .group_by(SketchPage.sketch_id)
            )
            for r in (await session.execute(pc_q)).all():
                page_counts[r[0]] = r[1]

        items = []
        for s in rows:
            d = _sketch_to_dict(s)
            d["page_count"] = page_counts.get(s.id, 0)
            items.append(d)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }


@router.post("")
async def create_sketch(request: Request, body: CreateSketchRequest):
    from openvort.plugins.vortsketch.models import Sketch

    member_id = _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        sketch = Sketch(
            name=body.name,
            description=body.description,
            project_id=body.project_id,
            story_id=body.story_id,
            story_type=body.story_type,
            created_by=member_id,
            current_version=0,
        )
        session.add(sketch)
        await session.flush()
        await session.commit()
        return _sketch_to_dict(sketch)


@router.get("/{sketch_id}")
async def get_sketch(request: Request, sketch_id: str):
    """Get sketch detail with its pages list."""
    from openvort.plugins.vortsketch.models import Sketch, SketchPage

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        sketch = await session.get(Sketch, sketch_id)
        if not sketch:
            raise HTTPException(404, "Sketch not found")

        pages = (await session.execute(
            select(SketchPage)
            .where(SketchPage.sketch_id == sketch_id)
            .order_by(SketchPage.sort_order, SketchPage.created_at)
        )).scalars().all()

        result = _sketch_to_dict(sketch)
        result["pages"] = [_page_to_dict(p) for p in pages]
        return result


@router.patch("/{sketch_id}")
async def update_sketch(request: Request, sketch_id: str, body: UpdateSketchRequest):
    from openvort.plugins.vortsketch.models import Sketch

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        sketch = await session.get(Sketch, sketch_id)
        if not sketch:
            raise HTTPException(404, "Sketch not found")

        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "No fields to update")

        await session.execute(update(Sketch).where(Sketch.id == sketch_id).values(**updates))
        await session.commit()

        updated = await session.get(Sketch, sketch_id)
        if updated:
            await session.refresh(updated)
        return _sketch_to_dict(updated)


@router.delete("/{sketch_id}")
async def delete_sketch(request: Request, sketch_id: str):
    from openvort.plugins.vortsketch.models import Sketch, SketchPage, SketchVersion

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        sketch = await session.get(Sketch, sketch_id)
        if not sketch:
            raise HTTPException(404, "Sketch not found")

        await session.execute(delete(SketchPage).where(SketchPage.sketch_id == sketch_id))
        await session.execute(delete(SketchVersion).where(SketchVersion.sketch_id == sketch_id))
        await session.execute(delete(Sketch).where(Sketch.id == sketch_id))
        await session.commit()
        return {"ok": True}


@router.post("/{sketch_id}/duplicate")
async def duplicate_sketch(request: Request, sketch_id: str):
    from openvort.plugins.vortsketch.models import Sketch, SketchPage

    member_id = _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        sketch = await session.get(Sketch, sketch_id)
        if not sketch:
            raise HTTPException(404, "Sketch not found")

        new_sketch = Sketch(
            name=f"{sketch.name} (副本)",
            description=sketch.description,
            project_id=sketch.project_id,
            story_id=sketch.story_id,
            story_type=sketch.story_type,
            created_by=member_id,
            current_version=0,
        )
        session.add(new_sketch)
        await session.flush()

        pages = (await session.execute(
            select(SketchPage)
            .where(SketchPage.sketch_id == sketch_id)
            .order_by(SketchPage.sort_order, SketchPage.created_at)
        )).scalars().all()

        for p in pages:
            new_page = SketchPage(
                sketch_id=new_sketch.id,
                name=p.name,
                html_content=p.html_content,
                sort_order=p.sort_order,
            )
            session.add(new_page)

        await session.commit()
        return _sketch_to_dict(new_sketch)


# ---- Page CRUD ----


@router.get("/{sketch_id}/pages")
async def list_pages(request: Request, sketch_id: str):
    from openvort.plugins.vortsketch.models import Sketch, SketchPage

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        sketch = await session.get(Sketch, sketch_id)
        if not sketch:
            raise HTTPException(404, "Sketch not found")

        rows = (await session.execute(
            select(SketchPage)
            .where(SketchPage.sketch_id == sketch_id)
            .order_by(SketchPage.sort_order, SketchPage.created_at)
        )).scalars().all()

        return {"items": [_page_to_dict(p) for p in rows]}


@router.post("/{sketch_id}/pages")
async def create_page(request: Request, sketch_id: str, body: CreatePageRequest):
    from openvort.plugins.vortsketch.models import Sketch, SketchPage

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        sketch = await session.get(Sketch, sketch_id)
        if not sketch:
            raise HTTPException(404, "Sketch not found")

        max_order = (await session.execute(
            select(func.coalesce(func.max(SketchPage.sort_order), -1))
            .where(SketchPage.sketch_id == sketch_id)
        )).scalar() or 0

        page = SketchPage(
            sketch_id=sketch_id,
            name=body.name,
            sort_order=max_order + 1,
        )
        session.add(page)
        await session.flush()
        await session.commit()
        return _page_to_dict(page)


@router.get("/{sketch_id}/pages/{page_id}")
async def get_page(request: Request, sketch_id: str, page_id: str):
    from openvort.plugins.vortsketch.models import SketchPage

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        page = await session.get(SketchPage, page_id)
        if not page or page.sketch_id != sketch_id:
            raise HTTPException(404, "Page not found")
        return _page_to_dict(page, include_html=True)


@router.patch("/{sketch_id}/pages/{page_id}")
async def update_page(request: Request, sketch_id: str, page_id: str, body: UpdatePageRequest):
    from openvort.plugins.vortsketch.models import SketchPage

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        page = await session.get(SketchPage, page_id)
        if not page or page.sketch_id != sketch_id:
            raise HTTPException(404, "Page not found")

        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "No fields to update")

        await session.execute(update(SketchPage).where(SketchPage.id == page_id).values(**updates))
        await session.commit()

        updated = await session.get(SketchPage, page_id)
        return _page_to_dict(updated)


@router.delete("/{sketch_id}/pages/{page_id}")
async def delete_page(request: Request, sketch_id: str, page_id: str):
    from openvort.plugins.vortsketch.models import SketchPage

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        page = await session.get(SketchPage, page_id)
        if not page or page.sketch_id != sketch_id:
            raise HTTPException(404, "Page not found")

        await session.execute(delete(SketchPage).where(SketchPage.id == page_id))
        await session.commit()
        return {"ok": True}


@router.post("/{sketch_id}/pages/{page_id}/duplicate")
async def duplicate_page(request: Request, sketch_id: str, page_id: str):
    from openvort.plugins.vortsketch.models import SketchPage

    _get_member_id(request)
    sf = _get_session_factory()
    async with sf() as session:
        source = await session.get(SketchPage, page_id)
        if not source or source.sketch_id != sketch_id:
            raise HTTPException(404, "Page not found")

        max_order = (await session.execute(
            select(func.coalesce(func.max(SketchPage.sort_order), -1))
            .where(SketchPage.sketch_id == sketch_id)
        )).scalar() or 0

        new_page = SketchPage(
            sketch_id=sketch_id,
            name=f"{source.name} (副本)",
            html_content=source.html_content,
            sort_order=max_order + 1,
        )
        session.add(new_page)
        await session.flush()
        await session.commit()
        return _page_to_dict(new_page, include_html=True)


# ---- Page Generate / Iterate (SSE) ----


@router.post("/{sketch_id}/pages/{page_id}/generate")
async def generate_page(request: Request, sketch_id: str, page_id: str, body: GeneratePageRequest):
    """Generate HTML for a page via LLM. Returns SSE stream with real-time chunks."""
    from openvort.plugins.vortsketch.models import Sketch, SketchPage

    _get_member_id(request)
    sf = _get_session_factory()

    async with sf() as session:
        sketch = await session.get(Sketch, sketch_id)
        if not sketch:
            raise HTTPException(404, "Sketch not found")
        page = await session.get(SketchPage, page_id)
        if not page or page.sketch_id != sketch_id:
            raise HTTPException(404, "Page not found")

        sketch_desc = sketch.description
        sketch_name = sketch.name

    description = body.description or sketch_desc or sketch_name

    async def event_stream():
        try:
            yield {"event": "generating", "data": json.dumps({"message": "正在生成原型..."}, ensure_ascii=False)}

            generator = _get_generator()
            images = [img.model_dump() for img in body.images] if body.images else None

            final_html = ""
            final_summary = ""
            final_tokens = 0

            async for event in generator.generate_stream(
                description=description,
                requirement_context="",
                images=images,
            ):
                if event["type"] == "chunk":
                    yield {"event": "html_chunk", "data": json.dumps({"text": event["text"]}, ensure_ascii=False)}
                elif event["type"] == "done":
                    final_html = event["html"]
                    final_summary = event["summary"]
                    final_tokens = event["tokens"]

            if final_html:
                async with sf() as session:
                    await session.execute(
                        update(SketchPage).where(SketchPage.id == page_id).values(html_content=final_html)
                    )
                    await session.commit()

            yield {"event": "done", "data": json.dumps({
                "page_id": page_id,
                "html_content": final_html,
                "ai_summary": final_summary,
                "tokens_used": final_tokens,
            }, ensure_ascii=False)}

        except Exception as e:
            log.exception(f"生成原型失败: page_id={page_id}")
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_stream(), ping=15)


@router.post("/{sketch_id}/pages/{page_id}/iterate")
async def iterate_page(request: Request, sketch_id: str, page_id: str, body: IteratePageRequest):
    """Iterate on a page via LLM. Returns SSE stream with real-time chunks."""
    from openvort.plugins.vortsketch.models import SketchPage

    _get_member_id(request)
    sf = _get_session_factory()

    async with sf() as session:
        page = await session.get(SketchPage, page_id)
        if not page or page.sketch_id != sketch_id:
            raise HTTPException(404, "Page not found")
        if not page.html_content:
            raise HTTPException(400, "Page has no content to iterate on")
        previous_html = page.html_content

    async def event_stream():
        try:
            yield {"event": "generating", "data": json.dumps({"message": "正在修改原型..."}, ensure_ascii=False)}

            generator = _get_generator()
            images = [img.model_dump() for img in body.images] if body.images else None

            final_html = ""
            final_summary = ""
            final_tokens = 0
            final_patches: dict[str, str] | None = None

            async for event in generator.iterate_stream(
                instruction=body.instruction,
                previous_html=previous_html,
                requirement_context="",
                images=images,
            ):
                if event["type"] == "chunk":
                    yield {"event": "html_chunk", "data": json.dumps({"text": event["text"]}, ensure_ascii=False)}
                elif event["type"] == "done":
                    final_html = event["html"]
                    final_summary = event["summary"]
                    final_tokens = event["tokens"]
                    final_patches = event.get("patches")

            if final_html:
                async with sf() as session:
                    await session.execute(
                        update(SketchPage).where(SketchPage.id == page_id).values(html_content=final_html)
                    )
                    await session.commit()

            done_data: dict = {
                "page_id": page_id,
                "html_content": final_html,
                "ai_summary": final_summary,
                "tokens_used": final_tokens,
            }
            if final_patches:
                done_data["patches"] = final_patches

            yield {"event": "done", "data": json.dumps(done_data, ensure_ascii=False)}

        except Exception as e:
            log.exception(f"迭代原型失败: page_id={page_id}")
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_stream(), ping=15)


# ---- Serializers ----


def _sketch_to_dict(s) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "project_id": s.project_id,
        "story_id": s.story_id,
        "story_type": s.story_type,
        "created_by": s.created_by,
        "current_version": s.current_version,
        "is_archived": s.is_archived,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _page_to_dict(p, include_html: bool = False) -> dict:
    d = {
        "id": p.id,
        "sketch_id": p.sketch_id,
        "name": p.name,
        "sort_order": p.sort_order,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    if include_html:
        d["html_content"] = p.html_content
    return d
