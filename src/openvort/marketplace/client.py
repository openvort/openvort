"""
Marketplace HTTP client for openvort.com public API.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MARKETPLACE_URL = "https://openvort.com/api"
TIMEOUT = 30


class MarketplaceClient:
    """HTTP client to interact with the OpenVort extensions marketplace."""

    def __init__(self, base_url: str = DEFAULT_MARKETPLACE_URL):
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=TIMEOUT)
        return self._client

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

        resp = await client.get(f"{self.base_url}/extensions", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_skill(self, slug: str, author: str = "") -> dict[str, Any]:
        """Get skill install data (includes content)."""
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
        """Get plugin install info (includes packageName)."""
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
