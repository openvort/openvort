"""通用文件上传路由"""

import uuid

from fastapi import APIRouter, Request, UploadFile, File

from openvort.web.app import require_auth
from openvort.web.upload_utils import get_upload_dir, get_upload_url

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_FILE_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "svg",
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "md", "csv", "json", "xml", "yaml", "yml",
    "zip", "rar", "7z", "tar", "gz",
    "mp4", "mp3", "wav",
    "log", "sql", "html", "css", "js", "ts",
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/editor/image")
async def upload_editor_image(file: UploadFile = File(...)):
    """Upload an image for the rich-text editor (VortEditor)."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        return {"error": "仅支持 jpg/png/gif/webp 格式"}

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        return {"error": "文件大小不能超过 10MB"}

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "png"
    upload_dir = get_upload_dir("editor")
    filename = f"{uuid.uuid4().hex}.{ext}"
    (upload_dir / filename).write_bytes(content)

    url = get_upload_url(f"/uploads/editor/{filename}")
    return {"success": True, "url": url}


@router.post("/vortflow/file")
async def upload_vortflow_file(request: Request, file: UploadFile = File(...)):
    """Upload a file attachment for VortFlow work items."""
    require_auth(request)
    original_name = file.filename or "file"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in ALLOWED_FILE_EXTENSIONS:
        return {"error": f"不支持的文件类型: .{ext}"}

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return {"error": "文件大小不能超过 20MB"}

    upload_dir = get_upload_dir("vortflow")
    saved_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    (upload_dir / saved_name).write_bytes(content)

    url = get_upload_url(f"/uploads/vortflow/{saved_name}")
    return {"url": url, "name": original_name, "size": len(content)}
