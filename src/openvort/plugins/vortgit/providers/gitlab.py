"""GitLab REST API v4 provider."""

import base64
from urllib.parse import quote as url_quote

import httpx

from openvort.plugins.vortgit.providers.base import GitProviderBase
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit.gitlab")

_DEFAULT_API_BASE = "https://gitlab.com/api/v4"


class GitLabProvider(GitProviderBase):
    name = "gitlab"

    def __init__(self, access_token: str, api_base: str = ""):
        self._token = access_token
        self._api_base = (api_base or _DEFAULT_API_BASE).rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=30,
            headers={"PRIVATE-TOKEN": self._token},
        )

    @staticmethod
    def _encode_project(full_name: str) -> str:
        """URL-encode project path for GitLab API (e.g. 'org/repo' -> 'org%2Frepo')."""
        return url_quote(full_name, safe="")

    async def _get(self, path: str, **params) -> dict | list:
        url = f"{self._api_base}{path}"
        resp = await self._client.get(url, params={k: str(v) for k, v in params.items() if v})
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, body: dict | None = None) -> dict:
        url = f"{self._api_base}{path}"
        resp = await self._client.post(url, json=body or {})
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _normalise_repo(raw: dict) -> dict:
        ns = raw.get("namespace") or {}
        full_name = raw.get("path_with_namespace", "")
        http_url = raw.get("http_url_to_repo", "")
        return {
            "name": raw.get("name", ""),
            "full_name": full_name,
            "description": raw.get("description") or "",
            "clone_url": http_url,
            "ssh_url": raw.get("ssh_url_to_repo", ""),
            "default_branch": raw.get("default_branch", "main"),
            "language": "",
            "private": raw.get("visibility", "private") == "private",
            "updated_at": raw.get("last_activity_at", ""),
        }

    @staticmethod
    def _normalise_commit(raw: dict) -> dict:
        return {
            "sha": raw.get("id") or raw.get("short_id", ""),
            "message": raw.get("message") or raw.get("title", ""),
            "author_name": raw.get("author_name", ""),
            "author_email": raw.get("author_email", ""),
            "authored_date": raw.get("authored_date") or raw.get("created_at", ""),
        }

    # ---- public API ----

    async def list_repos(
        self, *, page: int = 1, per_page: int = 20, search: str = ""
    ) -> list[dict]:
        params: dict = {
            "membership": "true",
            "page": page,
            "per_page": per_page,
            "order_by": "updated_at",
            "sort": "desc",
        }
        if search:
            params["search"] = search
        items = await self._get("/projects", **params)
        return [self._normalise_repo(r) for r in (items if isinstance(items, list) else [])]

    async def get_repo(self, full_name: str) -> dict:
        pid = self._encode_project(full_name)
        raw = await self._get(f"/projects/{pid}")
        return self._normalise_repo(raw)

    async def list_commits(
        self,
        full_name: str,
        *,
        branch: str = "",
        since: str = "",
        until: str = "",
        author: str = "",
        page: int = 1,
        per_page: int = 20,
    ) -> list[dict]:
        pid = self._encode_project(full_name)
        params: dict = {"page": page, "per_page": per_page}
        if branch:
            params["ref_name"] = branch
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if author:
            params["author"] = author
        items = await self._get(f"/projects/{pid}/repository/commits", **params)
        return [self._normalise_commit(c) for c in (items if isinstance(items, list) else [])]

    async def list_branches(self, full_name: str) -> list[dict]:
        pid = self._encode_project(full_name)
        items = await self._get(f"/projects/{pid}/repository/branches", per_page=100)
        if not isinstance(items, list):
            return []
        return [
            {
                "name": b.get("name", ""),
                "is_default": b.get("default", False),
                "last_commit_sha": (b.get("commit") or {}).get("id", ""),
            }
            for b in items
        ]

    async def get_file_content(self, full_name: str, path: str, *, ref: str = "") -> str:
        pid = self._encode_project(full_name)
        encoded_path = url_quote(path, safe="")
        params: dict = {}
        if ref:
            params["ref"] = ref
        data = await self._get(f"/projects/{pid}/repository/files/{encoded_path}", **params)
        if isinstance(data, dict) and data.get("content"):
            encoding = data.get("encoding", "base64")
            if encoding == "base64":
                return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return data["content"]
        return ""

    async def get_file_tree(self, full_name: str, *, path: str = "", ref: str = "") -> list[dict]:
        pid = self._encode_project(full_name)
        params: dict = {"per_page": 100}
        if path:
            params["path"] = path
        if ref:
            params["ref"] = ref
        data = await self._get(f"/projects/{pid}/repository/tree", **params)
        if not isinstance(data, list):
            return []
        return [
            {
                "name": item.get("name", ""),
                "path": item.get("path", ""),
                "type": "dir" if item.get("type") == "tree" else "file",
                "size": 0,
            }
            for item in data
        ]

    async def list_pull_requests(
        self, full_name: str, *, state: str = "open", page: int = 1, per_page: int = 20
    ) -> list[dict]:
        pid = self._encode_project(full_name)
        gl_state = {"open": "opened", "closed": "closed", "merged": "merged"}.get(state, "opened")
        items = await self._get(
            f"/projects/{pid}/merge_requests",
            state=gl_state, page=page, per_page=per_page,
        )
        if not isinstance(items, list):
            return []
        return [
            {
                "number": mr.get("iid", 0),
                "title": mr.get("title", ""),
                "state": mr.get("state", ""),
                "url": mr.get("web_url", ""),
                "head": mr.get("source_branch", ""),
                "base": mr.get("target_branch", ""),
                "created_at": mr.get("created_at", ""),
            }
            for mr in items
        ]

    async def get_pull_request_detail(self, full_name: str, pr_number: int) -> dict:
        pid = self._encode_project(full_name)
        mr = await self._get(f"/projects/{pid}/merge_requests/{pr_number}")
        if not isinstance(mr, dict):
            return {}
        changes = mr.get("changes_count", "0")
        return {
            "number": mr.get("iid", 0),
            "title": mr.get("title", ""),
            "body": mr.get("description", ""),
            "state": mr.get("state", ""),
            "url": mr.get("web_url", ""),
            "head": mr.get("source_branch", ""),
            "base": mr.get("target_branch", ""),
            "commits": 0,
            "additions": 0,
            "deletions": 0,
            "changed_files": int(changes) if str(changes).isdigit() else 0,
            "created_at": mr.get("created_at", ""),
        }

    async def get_pull_request_files(self, full_name: str, pr_number: int) -> list[dict]:
        pid = self._encode_project(full_name)
        data = await self._get(f"/projects/{pid}/merge_requests/{pr_number}/changes")
        if not isinstance(data, dict):
            return []
        changes = data.get("changes", [])
        if not isinstance(changes, list):
            return []
        return [
            {
                "filename": c.get("new_path") or c.get("old_path", ""),
                "status": self._diff_status(c),
                "additions": 0,
                "deletions": 0,
                "patch": c.get("diff", ""),
            }
            for c in changes
        ]

    @staticmethod
    def _diff_status(change: dict) -> str:
        if change.get("new_file"):
            return "added"
        if change.get("deleted_file"):
            return "removed"
        if change.get("renamed_file"):
            return "renamed"
        return "modified"

    async def create_pull_request(
        self, full_name: str, *, title: str, head: str, base: str, body: str = ""
    ) -> dict:
        pid = self._encode_project(full_name)
        data = await self._post(
            f"/projects/{pid}/merge_requests",
            {
                "title": title,
                "source_branch": head,
                "target_branch": base,
                "description": body,
            },
        )
        return {
            "number": data.get("iid", 0),
            "url": data.get("web_url", ""),
            "title": data.get("title", ""),
        }

    async def close(self) -> None:
        await self._client.aclose()
