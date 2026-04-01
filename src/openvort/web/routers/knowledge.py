"""Knowledge Base API router — folder management + document management + search."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update

from openvort.utils.logging import get_logger

log = get_logger("web.routers.knowledge")

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ---- Request / Response Models ----


class CreateFolderRequest(BaseModel):
    name: str
    parent_id: str = ""
    description: str = ""


class UpdateFolderRequest(BaseModel):
    name: str | None = None
    parent_id: str | None = None
    description: str | None = None


class CreateTextDocRequest(BaseModel):
    title: str
    content: str
    file_type: str = "qa"
    folder_id: str = ""


class UpdateDocRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    folder_id: str | None = None


class MoveItemsRequest(BaseModel):
    folder_ids: list[str] = []
    document_ids: list[str] = []
    target_folder_id: str = ""


class CreateGitDocRequest(BaseModel):
    repo_id: str
    branch: str
    path: str
    title: str = ""
    folder_id: str = ""


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


# ---- Helpers ----


def _get_member_id(request: Request) -> str:
    from openvort.web.app import require_auth
    payload = require_auth(request)
    return payload.get("sub", "")


def _get_session_factory():
    from openvort.web.deps import get_db_session_factory
    return get_db_session_factory()


def _get_embedding_service():
    from openvort.web.deps import get_embedding_service
    return get_embedding_service()


async def _process_document(doc_id: str) -> None:
    """Background task: parse, chunk, embed, and store a document."""
    from openvort.plugins.knowledge.chunker import chunk_text, parse_document
    from openvort.plugins.knowledge.models import KBChunk, KBDocument

    sf = _get_session_factory()
    embedding_svc = _get_embedding_service()

    async with sf() as session:
        doc = await session.get(KBDocument, doc_id)
        if not doc:
            return

        try:
            doc.status = "processing"
            await session.commit()

            # Clear existing chunks before re-processing
            try:
                await session.execute(
                    delete(KBChunk).where(KBChunk.document_id == doc_id)
                )
                await session.commit()
            except Exception:
                pass

            # Parse content if file was uploaded (content stored at upload time)
            text = doc.content
            if not text or not text.strip():
                doc.status = "error"
                doc.error_message = "文档内容为空"
                await session.commit()
                return

            # Chunk
            chunks = chunk_text(text)
            if not chunks:
                doc.status = "error"
                doc.error_message = "文档分块失败：未产生有效分块"
                await session.commit()
                return

            # Embed
            if not embedding_svc or not embedding_svc.available:
                doc.status = "error"
                doc.error_message = "Embedding 服务未配置，无法向量化"
                await session.commit()
                return

            chunk_texts = [c.content for c in chunks]
            embeddings = await embedding_svc.embed(chunk_texts)

            # Store chunks
            for chunk, embedding in zip(chunks, embeddings):
                db_chunk = KBChunk(
                    document_id=doc_id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    embedding=embedding,
                    token_count=chunk.token_count,
                    metadata_json=json.dumps(chunk.metadata, ensure_ascii=False),
                )
                session.add(db_chunk)

            doc.chunk_count = len(chunks)
            doc.status = "ready"
            doc.error_message = ""
            await session.commit()

            log.info(f"文档处理完成: {doc.title} ({len(chunks)} chunks)")
        except Exception as e:
            log.error(f"文档处理失败: {doc.title}, error: {e}")
            try:
                doc.status = "error"
                doc.error_message = str(e)[:500]
                await session.commit()
            except Exception:
                pass


# ---- Folder Endpoints ----


@router.get("/folders")
async def list_folders(parent_id: str = ""):
    """List folders under a parent (empty = root)."""
    from openvort.plugins.knowledge.models import KBFolder

    sf = _get_session_factory()
    async with sf() as session:
        stmt = (
            select(KBFolder)
            .where(KBFolder.parent_id == parent_id)
            .order_by(KBFolder.sort_order, KBFolder.created_at)
        )
        result = await session.execute(stmt)
        folders = result.scalars().all()

    return {
        "items": [
            {
                "id": f.id,
                "name": f.name,
                "parent_id": f.parent_id,
                "description": f.description,
                "sort_order": f.sort_order,
                "owner_id": f.owner_id,
                "created_at": f.created_at.isoformat() if f.created_at else "",
                "updated_at": f.updated_at.isoformat() if f.updated_at else "",
            }
            for f in folders
        ]
    }


@router.get("/folders/{folder_id}")
async def get_folder(folder_id: str):
    """Get folder detail with ancestor breadcrumb."""
    from openvort.plugins.knowledge.models import KBFolder

    sf = _get_session_factory()
    async with sf() as session:
        folder = await session.get(KBFolder, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="文件夹不存在")

        breadcrumb = []
        current = folder
        while current and current.parent_id:
            parent = await session.get(KBFolder, current.parent_id)
            if not parent:
                break
            breadcrumb.insert(0, {"id": parent.id, "name": parent.name})
            current = parent

        return {
            "id": folder.id,
            "name": folder.name,
            "parent_id": folder.parent_id,
            "description": folder.description,
            "breadcrumb": breadcrumb,
            "created_at": folder.created_at.isoformat() if folder.created_at else "",
            "updated_at": folder.updated_at.isoformat() if folder.updated_at else "",
        }


@router.post("/folders")
async def create_folder(request: Request, body: CreateFolderRequest):
    """Create a new folder."""
    from openvort.plugins.knowledge.models import KBFolder

    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="文件夹名称不能为空")

    member_id = _get_member_id(request)

    sf = _get_session_factory()
    async with sf() as session:
        if body.parent_id:
            parent = await session.get(KBFolder, body.parent_id)
            if not parent:
                raise HTTPException(status_code=400, detail="父文件夹不存在")

        folder = KBFolder(
            name=body.name.strip(),
            parent_id=body.parent_id,
            description=body.description,
            owner_id=member_id,
        )
        session.add(folder)
        await session.commit()

        return {"id": folder.id, "name": folder.name}


@router.put("/folders/{folder_id}")
async def update_folder(folder_id: str, body: UpdateFolderRequest):
    """Update folder name / parent / description."""
    from openvort.plugins.knowledge.models import KBFolder

    sf = _get_session_factory()
    async with sf() as session:
        folder = await session.get(KBFolder, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="文件夹不存在")

        if body.name is not None:
            if not body.name.strip():
                raise HTTPException(status_code=400, detail="文件夹名称不能为空")
            folder.name = body.name.strip()
        if body.parent_id is not None:
            if body.parent_id == folder_id:
                raise HTTPException(status_code=400, detail="不能将文件夹移到自身下")
            folder.parent_id = body.parent_id
        if body.description is not None:
            folder.description = body.description

        await session.commit()

    return {"ok": True}


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str):
    """Delete folder — moves children to parent, not cascade delete."""
    from openvort.plugins.knowledge.models import KBDocument, KBFolder

    sf = _get_session_factory()
    async with sf() as session:
        folder = await session.get(KBFolder, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="文件夹不存在")

        parent_id = folder.parent_id

        # move child folders to parent
        await session.execute(
            update(KBFolder)
            .where(KBFolder.parent_id == folder_id)
            .values(parent_id=parent_id)
        )
        # move child documents to parent
        await session.execute(
            update(KBDocument)
            .where(KBDocument.folder_id == folder_id)
            .values(folder_id=parent_id)
        )

        await session.delete(folder)
        await session.commit()

    return {"ok": True}


@router.post("/move")
async def move_items(body: MoveItemsRequest):
    """Batch move folders and documents to a target folder."""
    from openvort.plugins.knowledge.models import KBDocument, KBFolder

    sf = _get_session_factory()
    async with sf() as session:
        if body.target_folder_id:
            target = await session.get(KBFolder, body.target_folder_id)
            if not target:
                raise HTTPException(status_code=400, detail="目标文件夹不存在")

        if body.folder_ids:
            if body.target_folder_id in body.folder_ids:
                raise HTTPException(status_code=400, detail="不能将文件夹移到自身")
            await session.execute(
                update(KBFolder)
                .where(KBFolder.id.in_(body.folder_ids))
                .values(parent_id=body.target_folder_id)
            )
        if body.document_ids:
            await session.execute(
                update(KBDocument)
                .where(KBDocument.id.in_(body.document_ids))
                .values(folder_id=body.target_folder_id)
            )
        await session.commit()

    return {"ok": True}


# ---- Document Endpoints ----


@router.get("/documents")
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    status: str = "",
    folder_id: str = "",
):
    """List knowledge base documents, optionally filtered by folder."""
    from openvort.plugins.knowledge.models import KBDocument

    sf = _get_session_factory()
    async with sf() as session:
        stmt = select(KBDocument).order_by(KBDocument.created_at.desc())

        if folder_id is not None:
            stmt = stmt.where(KBDocument.folder_id == folder_id)
        if keyword:
            stmt = stmt.where(KBDocument.title.ilike(f"%{keyword}%"))
        if status:
            stmt = stmt.where(KBDocument.status == status)

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        # Paginate
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        docs = result.scalars().all()

    items = []
    for d in docs:
        items.append({
            "id": d.id,
            "title": d.title,
            "folder_id": d.folder_id,
            "file_name": d.file_name,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "status": d.status,
            "error_message": d.error_message,
            "chunk_count": d.chunk_count,
            "owner_id": d.owner_id,
            "created_at": d.created_at.isoformat() if d.created_at else "",
            "updated_at": d.updated_at.isoformat() if d.updated_at else "",
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/documents")
async def upload_document(
    request: Request,
    file: UploadFile = File(None),
    title: str = Form(None),
    folder_id: str = Form(""),
):
    """Upload a document file (PDF/DOCX/MD/TXT)."""
    from openvort.plugins.knowledge.chunker import parse_document
    from openvort.plugins.knowledge.models import KBDocument

    if not file:
        raise HTTPException(status_code=400, detail="请上传文件")

    # Determine file type
    file_name = file.filename or "unknown"
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "txt"
    if ext not in ("pdf", "docx", "doc", "md", "markdown", "txt", "text"):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Parse content
    try:
        content = parse_document(file_bytes, ext, file_name)
    except ImportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文档解析失败: {e}")

    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="文档内容为空，无法处理")

    member_id = _get_member_id(request)
    doc_title = title or file_name.rsplit(".", 1)[0]

    sf = _get_session_factory()
    async with sf() as session:
        doc = KBDocument(
            title=doc_title,
            folder_id=folder_id or "",
            file_name=file_name,
            file_type=ext if ext not in ("markdown", "text") else ("md" if ext == "markdown" else "txt"),
            file_size=file_size,
            content=content,
            status="pending",
            owner_id=member_id,
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    # Process in background
    asyncio.create_task(_process_document(doc_id))

    return {"id": doc_id, "title": doc_title, "status": "pending"}


@router.post("/documents/text")
async def create_text_document(request: Request, body: CreateTextDocRequest):
    """Create a text/QA document (manual entry)."""
    from openvort.plugins.knowledge.models import KBDocument

    if not body.content or not body.content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")

    member_id = _get_member_id(request)

    sf = _get_session_factory()
    async with sf() as session:
        doc = KBDocument(
            title=body.title,
            folder_id=body.folder_id or "",
            file_name="",
            file_type=body.file_type or "qa",
            file_size=len(body.content.encode("utf-8")),
            content=body.content,
            status="pending",
            owner_id=member_id,
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    asyncio.create_task(_process_document(doc_id))

    return {"id": doc_id, "title": body.title, "status": "pending"}


@router.post("/documents/git")
async def create_git_document(request: Request, body: CreateGitDocRequest):
    """Create a document linked to a Git repo file (read-only)."""
    from openvort.plugins.knowledge.models import KBDocument
    from openvort.plugins.vortgit.models import GitProvider, GitRepo

    member_id = _get_member_id(request)
    sf = _get_session_factory()

    async with sf() as session:
        repo = await session.get(GitRepo, body.repo_id)
        if not repo:
            raise HTTPException(status_code=400, detail="仓库不存在")
        provider = await session.get(GitProvider, repo.provider_id)
        if not provider:
            raise HTTPException(status_code=400, detail="Git Provider 不存在")
        repo_full_name = repo.full_name
        repo_name = repo.name
        default_branch = repo.default_branch
        provider_obj = provider

    # Fetch file content from remote
    from openvort.plugins.vortgit.router import _get_provider_instance

    client = _get_provider_instance(provider_obj)
    try:
        content = await client.get_file_content(
            repo_full_name, body.path, ref=body.branch or default_branch,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法读取文件: {exc}")
    finally:
        await client.close()

    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    doc_title = body.title or body.path.rsplit("/", 1)[-1].rsplit(".", 1)[0]

    async with sf() as session:
        doc = KBDocument(
            title=doc_title,
            folder_id=body.folder_id or "",
            file_name=body.path.rsplit("/", 1)[-1],
            file_type="git",
            file_size=len(content.encode("utf-8")),
            content=content,
            status="pending",
            owner_id=member_id,
            git_repo_id=body.repo_id,
            git_branch=body.branch or default_branch,
            git_path=body.path,
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    asyncio.create_task(_process_document(doc_id))

    return {"id": doc_id, "title": doc_title, "status": "pending"}


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get document detail."""
    from openvort.plugins.knowledge.models import KBDocument

    sf = _get_session_factory()
    async with sf() as session:
        doc = await session.get(KBDocument, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        result = {
            "id": doc.id,
            "title": doc.title,
            "folder_id": doc.folder_id,
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "content": doc.content,
            "status": doc.status,
            "error_message": doc.error_message,
            "chunk_count": doc.chunk_count,
            "owner_id": doc.owner_id,
            "created_at": doc.created_at.isoformat() if doc.created_at else "",
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else "",
            "git_repo_id": doc.git_repo_id or "",
            "git_branch": doc.git_branch or "",
            "git_path": doc.git_path or "",
        }

        if doc.file_type == "git" and doc.git_repo_id:
            from openvort.plugins.vortgit.models import GitRepo
            repo = await session.get(GitRepo, doc.git_repo_id)
            result["git_repo_name"] = repo.name if repo else ""
        else:
            result["git_repo_name"] = ""

        return result


@router.get("/documents/{doc_id}/git-content")
async def get_git_document_content(doc_id: str, branch: str = ""):
    """Fetch content of a git-linked document from a different branch."""
    from openvort.plugins.knowledge.models import KBDocument
    from openvort.plugins.vortgit.models import GitProvider, GitRepo

    sf = _get_session_factory()
    async with sf() as session:
        doc = await session.get(KBDocument, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        if doc.file_type != "git" or not doc.git_repo_id:
            raise HTTPException(status_code=400, detail="该文档非 Git 文档")

        repo = await session.get(GitRepo, doc.git_repo_id)
        if not repo:
            raise HTTPException(status_code=400, detail="关联仓库不存在")
        provider = await session.get(GitProvider, repo.provider_id)
        if not provider:
            raise HTTPException(status_code=400, detail="Git Provider 不存在")

        repo_full_name = repo.full_name
        git_path = doc.git_path
        provider_obj = provider

    from openvort.plugins.vortgit.router import _get_provider_instance

    target_branch = branch or doc.git_branch
    client = _get_provider_instance(provider_obj)
    try:
        content = await client.get_file_content(
            repo_full_name, git_path, ref=target_branch,
        )
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f"该分支下不存在该文档（{target_branch}: {git_path}）",
        )
    finally:
        await client.close()

    return {"content": content, "branch": target_branch}


@router.put("/documents/{doc_id}")
async def update_document(doc_id: str, body: UpdateDocRequest):
    """Update document title and/or content."""
    from openvort.plugins.knowledge.models import KBDocument

    sf = _get_session_factory()
    async with sf() as session:
        doc = await session.get(KBDocument, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        changed_content = False
        if body.title is not None:
            doc.title = body.title
        if body.folder_id is not None:
            doc.folder_id = body.folder_id
        if body.content is not None:
            doc.content = body.content
            doc.file_size = len(body.content.encode("utf-8"))
            changed_content = True

        await session.commit()

        if changed_content:
            asyncio.create_task(_process_document(doc_id))
            return {"ok": True, "reindexing": True}

        return {"ok": True, "reindexing": False}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete document and its chunks."""
    from openvort.plugins.knowledge.models import KBChunk, KBDocument

    sf = _get_session_factory()
    async with sf() as session:
        doc = await session.get(KBDocument, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        try:
            await session.execute(delete(KBChunk).where(KBChunk.document_id == doc_id))
        except Exception:
            pass
        await session.delete(doc)
        await session.commit()

    return {"ok": True}


@router.post("/documents/{doc_id}/reindex")
async def reindex_document(doc_id: str):
    """Re-parse and re-embed a document."""
    from openvort.plugins.knowledge.models import KBChunk, KBDocument

    sf = _get_session_factory()
    async with sf() as session:
        doc = await session.get(KBDocument, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        try:
            await session.execute(delete(KBChunk).where(KBChunk.document_id == doc_id))
        except Exception:
            pass
        doc.status = "pending"
        doc.chunk_count = 0
        await session.commit()

    asyncio.create_task(_process_document(doc_id))

    return {"ok": True, "status": "pending"}


@router.post("/search")
async def search_documents(body: SearchRequest):
    """Search knowledge base (for UI testing)."""
    from openvort.plugins.knowledge.retriever import KBRetriever

    embedding_svc = _get_embedding_service()
    if not embedding_svc or not embedding_svc.available:
        raise HTTPException(status_code=400, detail="Embedding 服务未配置")

    sf = _get_session_factory()
    retriever = KBRetriever(
        session_factory=sf,
        embedding_service=embedding_svc,
    )

    results = await retriever.search(body.query, top_k=body.top_k)

    items = []
    for r in results:
        items.append({
            "document_id": r.document_id,
            "document_title": r.document_title,
            "chunk_index": r.chunk_index,
            "content": r.content,
            "score": r.score,
        })

    return {"items": items, "count": len(items)}


@router.get("/stats")
async def get_stats():
    """Get knowledge base statistics."""
    from openvort.plugins.knowledge.models import KBChunk, KBDocument

    sf = _get_session_factory()
    doc_count = 0
    ready_count = 0
    chunk_count = 0

    async with sf() as session:
        try:
            doc_count = (await session.execute(
                select(func.count()).select_from(KBDocument)
            )).scalar() or 0

            ready_count = (await session.execute(
                select(func.count()).select_from(KBDocument).where(KBDocument.status == "ready")
            )).scalar() or 0
        except Exception:
            pass

        try:
            chunk_count = (await session.execute(
                select(func.count()).select_from(KBChunk)
            )).scalar() or 0
        except Exception:
            pass

    embedding_svc = _get_embedding_service()
    embedding_available = bool(embedding_svc and embedding_svc.available)

    return {
        "document_count": doc_count,
        "ready_count": ready_count,
        "chunk_count": chunk_count,
        "embedding_available": embedding_available,
    }
