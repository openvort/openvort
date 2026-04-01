"""
Image upload tool — upload_image

Accept base64-encoded image data OR a local file path,
save to the OpenVort server, and return an accessible URL.
"""

import base64
import json
import re
from pathlib import Path

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.system.tools.upload_image")

_DATA_URI_RE = re.compile(
    r"^data:image/(?P<ext>[a-zA-Z0-9.+-]+);base64,(?P<data>.+)$",
    re.DOTALL,
)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


def _infer_ext(filename: str) -> str:
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "png"


class UploadImageTool(BaseTool):
    name = "upload_image"
    description = (
        "Upload an image to the OpenVort server and get an accessible URL. "
        "Accepts EITHER a local file path (file_path) OR base64-encoded data (image_data). "
        "Prefer file_path when the image exists on disk — it's more efficient than base64. "
        "Use this tool FIRST when you need to attach images to work items, "
        "then pass the returned URL to other tools (e.g. vortflow_intake_story, vortflow_create_bug) "
        "as image_urls."
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "Absolute path to an image file on the server's local filesystem. "
                        "Preferred over image_data — avoids base64 encoding overhead."
                    ),
                },
                "image_data": {
                    "type": "string",
                    "description": (
                        "Base64-encoded image data. Supports both data URI format "
                        "(e.g. 'data:image/png;base64,iVBOR...') and raw base64 string. "
                        "Use file_path instead when the image is a local file."
                    ),
                },
                "filename": {
                    "type": "string",
                    "description": "Original filename (used to infer extension). Defaults to .png if omitted.",
                    "default": "",
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        from openvort.web.upload_utils import save_upload

        file_path = (params.get("file_path") or "").strip()
        raw = params.get("image_data") or ""

        if file_path:
            return self._upload_from_path(file_path, save_upload)

        if not raw:
            return json.dumps({
                "ok": False,
                "message": "file_path or image_data is required. "
                           "Prefer file_path for local files.",
            })

        return self._upload_from_base64(raw, params.get("filename", ""), save_upload)

    @staticmethod
    def _upload_from_path(file_path: str, save_upload) -> str:
        p = Path(file_path)
        if not p.is_file():
            return json.dumps({"ok": False, "message": f"File not found: {file_path}"})

        ext = _infer_ext(p.name)
        if ext == "svg+xml":
            ext = "svg"
        if ext not in ALLOWED_EXTENSIONS:
            return json.dumps({
                "ok": False,
                "message": f"Unsupported image type: .{ext}",
            })

        try:
            image_bytes = p.read_bytes()
        except Exception as e:
            return json.dumps({"ok": False, "message": f"Failed to read file: {e}"})

        if len(image_bytes) > MAX_IMAGE_SIZE:
            return json.dumps({
                "ok": False,
                "message": f"Image too large ({len(image_bytes)} bytes), max {MAX_IMAGE_SIZE} bytes",
            })
        if len(image_bytes) < 8:
            return json.dumps({"ok": False, "message": "File too small, likely invalid"})

        try:
            url = save_upload("mcp", image_bytes, ext)
        except Exception as e:
            log.error(f"Failed to save uploaded image: {e}")
            return json.dumps({"ok": False, "message": f"Failed to save image: {e}"})

        log.info(f"MCP image uploaded from path: {url} ({len(image_bytes)} bytes)")
        return json.dumps({"ok": True, "url": url})

    @staticmethod
    def _upload_from_base64(raw: str, filename: str, save_upload) -> str:
        ext = "png"
        b64_data = raw

        m = _DATA_URI_RE.match(raw)
        if m:
            ext = m.group("ext").lower().split("+")[0]
            b64_data = m.group("data")
        elif filename:
            ext = _infer_ext(filename)

        if ext == "svg+xml":
            ext = "svg"
        if ext not in ALLOWED_EXTENSIONS:
            ext = "png"

        try:
            image_bytes = base64.b64decode(b64_data)
        except Exception:
            return json.dumps({"ok": False, "message": "Invalid base64 data"})

        if len(image_bytes) > MAX_IMAGE_SIZE:
            return json.dumps({
                "ok": False,
                "message": f"Image too large ({len(image_bytes)} bytes), max {MAX_IMAGE_SIZE} bytes",
            })
        if len(image_bytes) < 8:
            return json.dumps({"ok": False, "message": "Image data too small, likely invalid"})

        try:
            url = save_upload("mcp", image_bytes, ext)
        except Exception as e:
            log.error(f"Failed to save uploaded image: {e}")
            return json.dumps({"ok": False, "message": f"Failed to save image: {e}"})

        log.info(f"MCP image uploaded from base64: {url} ({len(image_bytes)} bytes)")
        return json.dumps({"ok": True, "url": url})
