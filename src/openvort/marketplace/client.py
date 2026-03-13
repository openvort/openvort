"""
Marketplace HTTP client for openvort.com public API.
"""

import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MARKETPLACE_URL = "https://openvort.com/api"
TIMEOUT = 30
DOWNLOAD_TIMEOUT = 300


class MarketplaceClient:
    """HTTP client to interact with the OpenVort extensions marketplace."""

    def __init__(self, base_url: str = DEFAULT_MARKETPLACE_URL, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=TIMEOUT)
        return self._client

    def _auth_headers(self) -> dict[str, str]:
        if self.token:
            return {"Authorization": f"Basic {self.token}"}
        return {}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def search(
        self,
        query: str = "",
        type: str = "all",
        category: str = "",
        sort: str = "latest",
        page: int = 1,
        limit: int = 12,
    ) -> dict[str, Any]:
        """Search the marketplace for extensions."""
        client = await self._get_client()
        params: dict[str, Any] = {
            "page": page,
            "limit": limit,
            "sort": sort,
        }
        if query:
            params["search"] = query
        if type and type != "all":
            params["type"] = type
        if category:
            params["category"] = category

        url = f"{self.base_url}/extensions"
        logger.info("Marketplace upstream request: url=%s params=%s", url, params)
        try:
            resp = await client.get(url, params=params)
            logger.info("Marketplace upstream response: url=%s status=%s", url, resp.status_code)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Marketplace upstream request failed: url=%s params=%s", url, params)
            raise

    async def get_skill(self, slug: str, author: str = "") -> dict[str, Any]:
        """Get skill install data (includes content + bundle info)."""
        client = await self._get_client()
        params = {}
        if author:
            params["author"] = author

        resp = await client.get(
            f"{self.base_url}/marketplace/skills/{slug}",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_plugin(self, slug: str, author: str = "") -> dict[str, Any]:
        """Get plugin install info (includes packageName + bundle info)."""
        client = await self._get_client()
        params = {}
        if author:
            params["author"] = author

        resp = await client.get(
            f"{self.base_url}/marketplace/plugins/{slug}",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def report_download(self, ext_id: str) -> None:
        """Report a download to increment the counter."""
        try:
            client = await self._get_client()
            await client.post(f"{self.base_url}/extensions/{ext_id}/download")
        except Exception:
            logger.debug("Failed to report download for %s", ext_id, exc_info=True)

    async def get_extension_detail(self, slug: str, author: str = "") -> dict[str, Any]:
        """Get full extension detail by slug."""
        client = await self._get_client()
        params = {}
        if author:
            params["author"] = author

        resp = await client.get(
            f"{self.base_url}/extensions/{slug}",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def download_bundle(self, bundle_url: str, dest: Path) -> Path:
        """Download a bundle zip from the marketplace and save to dest."""
        url = bundle_url if bundle_url.startswith("http") else f"{self.base_url.rsplit('/api', 1)[0]}{bundle_url}"

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as dl_client:
            resp = await dl_client.get(url)
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)

        logger.info("Bundle downloaded: %s -> %s (%d bytes)", url, dest, dest.stat().st_size)
        return dest

    async def upload_bundle(
        self,
        slug: str,
        ext_type: str,
        zip_path: Path,
    ) -> dict[str, Any]:
        """Upload a bundle zip to the marketplace. Returns bundle info."""
        client = await self._get_client()
        with open(zip_path, "rb") as f:
            files = {"bundle": (zip_path.name, f, "application/zip")}
            data = {"slug": slug, "type": ext_type}
            resp = await client.post(
                f"{self.base_url.rsplit('/api', 1)[0]}/api/extensions/upload-bundle",
                files=files,
                data=data,
                headers=self._auth_headers(),
                timeout=DOWNLOAD_TIMEOUT,
            )
        resp.raise_for_status()
        return resp.json()

    async def publish_extension(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create or update an extension on the marketplace."""
        client = await self._get_client()

        # Try to find existing
        slug = body.get("slug", "")
        try:
            existing = await self.get_extension_detail(slug)
            if existing:
                resp = await client.put(
                    f"{self.base_url}/extensions/{existing['id']}",
                    json=body,
                    headers=self._auth_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise

        resp = await client.post(
            f"{self.base_url}/extensions",
            json=body,
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()
