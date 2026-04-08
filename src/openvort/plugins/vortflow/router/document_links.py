"""VortFlow document-links router: work item <-> KB document association."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import FlowDocumentLink, FlowProject
from openvort.utils.logging import get_logger
from openvort.web.app import require_auth

from .helpers import _log_event

log = get_logger("vortflow.router.document_links")

sub_router = APIRouter()


# ---- Request Models ----


class DocLinkCreate(BaseModel):
    document_id: str
    entity_type: str  # story/task/bug
    entity_id: str


class DocWithLinkCreate(BaseModel):
    title: str
    content: str = ""
    entity_type: str
    entity_id: str
    project_id: str


class ReorderBody(BaseModel):
    link_ids: list[str]


# ---- Helpers ----


async def _get_or_create_default_folder(session, project_id: str, member_id: str) -> str:
    """Get or create the default KB folder for work item documents under a project."""
    from openvort.plugins.knowledge.models import KBFolder

    project = await session.get(FlowProject, project_id)
    project_name = project.name if project else "未分类项目"

    # Find or create project-level folder
    stmt = select(KBFolder).where(KBFolder.name == project_name, KBFolder.parent_id == "")
    result = await session.execute(stmt)
    project_folder = result.scalar_one_or_none()

    if not project_folder:
        project_folder = KBFolder(name=project_name, parent_id="", description=f"项目「{project_name}」文档", owner_id=member_id)
        session.add(project_folder)
        await session.flush()

    # Find or create "工作项文档" subfolder
    stmt = select(KBFolder).where(KBFolder.name == "工作项文档", KBFolder.parent_id == project_folder.id)
    result = await session.execute(stmt)
    doc_folder = result.scalar_one_or_none()

    if not doc_folder:
        doc_folder = KBFolder(name="工作项文档", parent_id=project_folder.id, description="工作项关联文档自动归档目录", owner_id=member_id)
        session.add(doc_folder)
        await session.flush()

    return doc_folder.id


async def _next_sort_order(session, entity_type: str, entity_id: str) -> int:
    stmt = select(func.coalesce(func.max(FlowDocumentLink.sort_order), -1)).where(
        FlowDocumentLink.entity_type == entity_type,
        FlowDocumentLink.entity_id == entity_id,
    )
    result = await session.execute(stmt)
    return (result.scalar() or 0) + 1


# ---- Endpoints ----


@sub_router.get("/document-links")
async def list_document_links(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
):
    """List KB documents linked to a work item."""
    from openvort.plugins.knowledge.models import KBDocument

    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowDocumentLink, KBDocument)
            .outerjoin(KBDocument, FlowDocumentLink.document_id == KBDocument.id)
            .where(
                FlowDocumentLink.entity_type == entity_type,
                FlowDocumentLink.entity_id == entity_id,
            )
            .order_by(FlowDocumentLink.sort_order)
        )
        rows = (await session.execute(stmt)).all()

        items = []
        for link, doc in rows:
            if not doc:
                continue
            items.append({
                "link_id": link.id,
                "document_id": doc.id,
                "title": doc.title,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "status": doc.status,
                "sort_order": link.sort_order,
                "created_at": link.created_at.isoformat() if link.created_at else "",
            })

    return {"items": items}


@sub_router.post("/document-links")
async def create_document_link(body: DocLinkCreate, request: Request):
    """Link an existing KB document to a work item."""
    from openvort.plugins.knowledge.models import KBDocument

    payload = require_auth(request)
    member_id = payload.get("sub", "")

    sf = get_session_factory()
    async with sf() as session:
        doc = await session.get(KBDocument, body.document_id)
        if not doc:
            return {"error": "文档不存在"}

        existing = await session.execute(
            select(FlowDocumentLink).where(
                FlowDocumentLink.document_id == body.document_id,
                FlowDocumentLink.entity_type == body.entity_type,
                FlowDocumentLink.entity_id == body.entity_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "该文档已关联"}

        sort_order = await _next_sort_order(session, body.entity_type, body.entity_id)
        link = FlowDocumentLink(
            document_id=body.document_id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            sort_order=sort_order,
            created_by=member_id,
        )
        session.add(link)
        await _log_event(session, body.entity_type, body.entity_id, "doc_linked",
                         {"document_id": body.document_id, "title": doc.title})
        await session.commit()
        await session.refresh(link)

    return {"ok": True, "id": link.id, "document_id": body.document_id, "title": doc.title}


@sub_router.post("/document-links/with-doc")
async def create_doc_and_link(body: DocWithLinkCreate, request: Request):
    """Create a new KB text document and link it to a work item."""
    from openvort.plugins.knowledge.models import KBDocument

    payload = require_auth(request)
    member_id = payload.get("sub", "")

    sf = get_session_factory()
    async with sf() as session:
        folder_id = await _get_or_create_default_folder(session, body.project_id, member_id)

        doc = KBDocument(
            title=body.title,
            folder_id=folder_id,
            file_name="",
            file_type="md",
            file_size=len((body.content or "").encode("utf-8")),
            content=body.content or "",
            status="pending",
            owner_id=member_id,
        )
        session.add(doc)
        await session.flush()

        sort_order = await _next_sort_order(session, body.entity_type, body.entity_id)
        link = FlowDocumentLink(
            document_id=doc.id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            sort_order=sort_order,
            created_by=member_id,
        )
        session.add(link)
        await _log_event(session, body.entity_type, body.entity_id, "doc_created",
                         {"document_id": doc.id, "title": body.title})
        await session.commit()
        doc_id = doc.id

    # Background: chunk & embed
    from openvort.web.routers.knowledge import _process_document
    if body.content and body.content.strip():
        asyncio.create_task(_process_document(doc_id))

    return {"ok": True, "link_id": link.id, "document_id": doc_id, "title": body.title}


@sub_router.post("/document-links/with-upload")
async def upload_doc_and_link(
    request: Request,
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    entity_id: str = Form(...),
    project_id: str = Form(...),
    title: str = Form(None),
):
    """Upload a file to KB and link the resulting document to a work item."""
    from openvort.plugins.knowledge.chunker import parse_document
    from openvort.plugins.knowledge.models import KBDocument

    payload = require_auth(request)
    member_id = payload.get("sub", "")

    file_name = file.filename or "unknown"
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "txt"
    if ext not in ("pdf", "docx", "doc", "md", "markdown", "txt", "text"):
        return {"error": f"不支持的文件类型: {ext}"}

    file_bytes = await file.read()
    file_size = len(file_bytes)

    try:
        content = parse_document(file_bytes, ext, file_name)
    except Exception as e:
        return {"error": f"文档解析失败: {e}"}

    if not content or not content.strip():
        return {"error": "文档内容为空"}

    doc_title = title or file_name.rsplit(".", 1)[0]
    normalized_ext = ext if ext not in ("markdown", "text") else ("md" if ext == "markdown" else "txt")

    sf = get_session_factory()
    async with sf() as session:
        folder_id = await _get_or_create_default_folder(session, project_id, member_id)

        doc = KBDocument(
            title=doc_title,
            folder_id=folder_id,
            file_name=file_name,
            file_type=normalized_ext,
            file_size=file_size,
            content=content,
            status="pending",
            owner_id=member_id,
        )
        session.add(doc)
        await session.flush()

        sort_order = await _next_sort_order(session, entity_type, entity_id)
        link = FlowDocumentLink(
            document_id=doc.id,
            entity_type=entity_type,
            entity_id=entity_id,
            sort_order=sort_order,
            created_by=member_id,
        )
        session.add(link)
        await _log_event(session, entity_type, entity_id, "doc_uploaded",
                         {"document_id": doc.id, "title": doc_title})
        await session.commit()
        doc_id = doc.id

    from openvort.web.routers.knowledge import _process_document
    asyncio.create_task(_process_document(doc_id))

    return {"ok": True, "link_id": link.id, "document_id": doc_id, "title": doc_title}


@sub_router.put("/document-links/reorder")
async def reorder_document_links(body: ReorderBody):
    """Reorder linked documents by providing link_ids in desired order."""
    sf = get_session_factory()
    async with sf() as session:
        for idx, link_id in enumerate(body.link_ids):
            link = await session.get(FlowDocumentLink, link_id)
            if link:
                link.sort_order = idx
        await session.commit()
    return {"ok": True}


@sub_router.delete("/document-links/{link_id}")
async def delete_document_link(link_id: str):
    """Remove a document link (does NOT delete the KB document itself)."""
    sf = get_session_factory()
    async with sf() as session:
        link = await session.get(FlowDocumentLink, link_id)
        if not link:
            return {"error": "关联不存在"}
        await _log_event(session, link.entity_type, link.entity_id, "doc_unlinked",
                         {"document_id": link.document_id})
        await session.delete(link)
        await session.commit()
    return {"ok": True}
