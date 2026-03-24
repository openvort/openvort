"""
Image upload tool — upload_image

Accept base64-encoded image data from MCP clients (Cursor / Claude Desktop),
save to the OpenVort server, and return an accessible URL.
"""

import base64
import json
import re

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.system.tools.upload_image")

_DATA_URI_RE = re.compile(
    r"^data:image/(?P<ext>[a-zA-Z0-9.+-]+);base64,(?P<data>.+)$",
    re.DOTALL,
)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB decoded


class UploadImageTool(BaseTool):
    name = "upload_image"
    description = (
        "Upload a base64-encoded image to the OpenVort server and get an accessible URL. "
        "Use this tool FIRST when you have local image files or base64 image data, "
        "then pass the returned URL to other tools (e.g. vortflow_intake_story, vortflow_create_bug) "
        "as image_urls."
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "image_data": {
                    "type": "string",
                    "description": (
                        "Base64-encoded image data. Supports both data URI format "
                        "(e.g. 'data:image/png;base64,iVBOR...') and raw base64 string."
                    ),
                },
                "filename": {
                    "type": "string",
                    "description": "Original filename (used to infer extension). Defaults to .png if omitted.",
                    "default": "",
                },
            },
            "required": ["image_data"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.web.upload_utils import save_upload

        raw = params.get("image_data", "")
        if not raw:
            return json.dumps({"ok": False, "message": "image_data is required"})

        ext = "png"
        b64_data = raw

        m = _DATA_URI_RE.match(raw)
        if m:
            ext = m.group("ext").lower().split("+")[0]
            b64_data = m.group("data")
        elif params.get("filename"):
            fn = params["filename"]
            if "." in fn:
                ext = fn.rsplit(".", 1)[-1].lower()

        if ext == "svg+xml":
            ext = "svg"
        if ext not in ALLOWED_EXTENSIONS:
            ext = "png"

        try:
            image_bytes = base64.b64decode(b64_data)
        except Exception:
            return json.dumps({"ok": False, "message": "Invalid base64 data"})

        if len(image_bytes) > MAX_IMAGE_SIZE:
            return json.dumps({"ok": False, "message": f"Image too large ({len(image_bytes)} bytes), max {MAX_IMAGE_SIZE} bytes"})

        if len(image_bytes) < 8:
            return json.dumps({"ok": False, "message": "Image data too small, likely invalid"})

        try:
            url = save_upload("mcp", image_bytes, ext)
        except Exception as e:
            log.error(f"Failed to save uploaded image: {e}")
            return json.dumps({"ok": False, "message": f"Failed to save image: {e}"})

        log.info(f"MCP image uploaded: {url} ({len(image_bytes)} bytes)")
        return json.dumps({"ok": True, "url": url})
