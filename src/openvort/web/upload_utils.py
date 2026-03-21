"""Upload utilities — shared helpers for file upload endpoints."""

import uuid
from pathlib import Path

from openvort.config.settings import get_settings


def get_upload_dir(*sub: str) -> Path:
    """Return (and ensure exists) a subdirectory under data_dir/uploads."""
    d = get_settings().data_dir / "uploads"
    for s in sub:
        d = d / s
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_upload_url(relative_path: str) -> str:
    """Optionally prepend site_url to a relative upload path.

    If OPENVORT_WEB_SITE_URL is configured, returns an absolute URL;
    otherwise returns the relative path as-is (e.g. ``/uploads/editor/xxx.png``).
    """
    site_url = get_settings().web.site_url.rstrip("/")
    if site_url:
        return f"{site_url}{relative_path}"
    return relative_path


def save_upload(sub_dir: str, data: bytes, ext: str) -> str:
    """Save bytes to uploads/<sub_dir>/<uuid>.<ext> and return the URL."""
    upload_dir = get_upload_dir(sub_dir)
    filename = f"{uuid.uuid4().hex}.{ext}"
    (upload_dir / filename).write_bytes(data)
    return get_upload_url(f"/uploads/{sub_dir}/{filename}")
