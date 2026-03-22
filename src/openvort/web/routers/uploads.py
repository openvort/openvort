"""通用文件上传路由"""

import uuid

from fastapi import APIRouter, UploadFile, File

from openvort.web.upload_utils import get_upload_dir, get_upload_url

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


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
