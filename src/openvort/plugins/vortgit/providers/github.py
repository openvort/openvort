"""GitHub REST API provider."""

import base64

import httpx

from openvort.plugins.vortgit.providers.base import GitProviderBase
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit.github")

_DEFAULT_API_BASE = "https://api.github.com"


class GitHubProvider(GitProviderBase):
    name = "github"

    def __init__(self, access_token: str, api_base: str = ""):
        self._token = access_token
        self._api_base = (api_base or _DEFAULT_API_BASE).rstrip("/")
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.AsyncClient(timeout=30, headers=headers)

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
        return {
            "name": raw.get("name", ""),
            "full_name": raw.get("full_name", ""),
            "description": raw.get("description") or "",
            "clone_url": raw.get("clone_url", ""),
            "ssh_url": raw.get("ssh_url", ""),
            "default_branch": raw.get("default_branch", "main"),
            "language": raw.get("language") or "",
            "private": raw.get("private", False),
            "updated_at": raw.get("updated_at", ""),
        }

    @staticmethod
    def _normalise_commit(raw: dict) -> dict:
        c = raw.get("commit", raw)
        author = c.get("author") or {}
        return {
            "sha": raw.get("sha", ""),
            "message": c.get("message", ""),
            "author_name": author.get("name", ""),
            "author_email": author.get("email", ""),
            "authored_date": author.get("date", ""),
        }

    # ---- public API ----

    async def list_repos(
        self, *, page: int = 1, per_page: int = 20, search: str = ""
    ) -> list[dict]:
        if search:
            keyword = search.lower()
            all_repos: list[dict] = []
            fetch_page = 1
            while True:
                items = await self._get(
                    "/user/repos", page=fetch_page, per_page=100, sort="updated"
                )
                if not isinstance(items, list) or not items:
                    break
                all_repos.extend(items)
                if len(items) < 100:
                    break
                fetch_page += 1
                if fetch_page > 10:
                    break
            matched = [
                r for r in all_repos
                if keyword in (r.get("full_name") or "").lower()
                or keyword in (r.get("name") or "").lower()
                or keyword in (r.get("description") or "").lower()
            ]
            start = (page - 1) * per_page
            return [self._normalise_repo(r) for r in matched[start : start + per_page]]
        else:
            items = await self._get(
                "/user/repos", page=page, per_page=per_page, sort="updated"
            )
            return [self._normalise_repo(r) for r in (items if isinstance(items, list) else [])]

    async def get_repo(self, full_name: str) -> dict:
        raw = await self._get(f"/repos/{full_name}")
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
        params: dict = {"page": page, "per_page": per_page}
        if branch:
            params["sha"] = branch
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if author:
            params["author"] = author
        items = await self._get(f"/repos/{full_name}/commits", **params)
        return [self._normalise_commit(c) for c in (items if isinstance(items, list) else [])]

    async def list_branches(self, full_name: str) -> list[dict]:
        items = await self._get(f"/repos/{full_name}/branches", per_page=100)
        if not isinstance(items, list):
            return []
        repo = await self._get(f"/repos/{full_name}")
        default_branch = repo.get("default_branch", "main") if isinstance(repo, dict) else "main"
        return [
            {
                "name": b.get("name", ""),
                "is_default": b.get("name") == default_branch,
                "last_commit_sha": (b.get("commit") or {}).get("sha", ""),
            }
            for b in items
        ]

    async def get_file_content(self, full_name: str, path: str, *, ref: str = "") -> str:
        params: dict = {}
        if ref:
            params["ref"] = ref
        data = await self._get(f"/repos/{full_name}/contents/{path}", **params)
        if isinstance(data, dict) and data.get("content"):
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return ""

    async def get_file_tree(self, full_name: str, *, path: str = "", ref: str = "") -> list[dict]:
        params: dict = {}
        if ref:
            params["ref"] = ref
        endpoint = f"/repos/{full_name}/contents/{path}" if path else f"/repos/{full_name}/contents"
        data = await self._get(endpoint, **params)
        if not isinstance(data, list):
            return []
        return [
            {
                "name": item.get("name", ""),
                "path": item.get("path", ""),
                "type": "dir" if item.get("type") == "dir" else "file",
                "size": item.get("size", 0),
            }
            for item in data
        ]

    async def list_pull_requests(
        self, full_name: str, *, state: str = "open", page: int = 1, per_page: int = 20
    ) -> list[dict]:
        items = await self._get(
            f"/repos/{full_name}/pulls", state=state, page=page, per_page=per_page
        )
        if not isinstance(items, list):
            return []
        return [
            {
                "number": pr.get("number", 0),
                "title": pr.get("title", ""),
                "state": pr.get("state", ""),
                "url": pr.get("html_url", ""),
                "head": (pr.get("head") or {}).get("ref", ""),
                "base": (pr.get("base") or {}).get("ref", ""),
                "created_at": pr.get("created_at", ""),
            }
            for pr in items
        ]

    async def get_pull_request_detail(self, full_name: str, pr_number: int) -> dict:
        pr = await self._get(f"/repos/{full_name}/pulls/{pr_number}")
        if not isinstance(pr, dict):
            return {}
        return {
            "number": pr.get("number", 0),
            "title": pr.get("title", ""),
            "body": pr.get("body", ""),
            "state": pr.get("state", ""),
            "url": pr.get("html_url", ""),
            "head": (pr.get("head") or {}).get("ref", ""),
            "base": (pr.get("base") or {}).get("ref", ""),
            "commits": pr.get("commits", 0),
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
            "changed_files": pr.get("changed_files", 0),
            "created_at": pr.get("created_at", ""),
        }

    async def get_pull_request_files(self, full_name: str, pr_number: int) -> list[dict]:
        items = await self._get(f"/repos/{full_name}/pulls/{pr_number}/files")
        if not isinstance(items, list):
            return []
        result = []
        for f in items:
            raw_patch = f.get("patch", "")
            patch = raw_patch if isinstance(raw_patch, str) else str(raw_patch)
            result.append({
                "filename": f.get("filename", ""),
                "status": f.get("status", ""),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "patch": patch,
            })
        return result

    async def create_pull_request(
        self, full_name: str, *, title: str, head: str, base: str, body: str = ""
    ) -> dict:
        data = await self._post(
            f"/repos/{full_name}/pulls",
            {"title": title, "head": head, "base": base, "body": body},
        )
        return {
            "number": data.get("number", 0),
            "url": data.get("html_url", ""),
            "title": data.get("title", ""),
        }

    async def close(self) -> None:
        await self._client.aclose()
