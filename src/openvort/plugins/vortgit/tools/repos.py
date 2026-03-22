"""
VortGit repo tools — git_list_repos, git_repo_info

Read-only tools for listing and inspecting registered Git repositories.
"""

import json

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit.tools.repos")


class ListReposTool(BaseTool):
    name = "git_list_repos"
    description = (
        "列出已注册的 Git 代码仓库。"
        "可按关联的 VortFlow 项目过滤，也可按仓库名/路径搜索。"
        "返回仓库名称、语言、类型、关联项目等信息。"
    )
    required_permission = "vortgit.read"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "按 VortFlow 项目 ID 筛选（可选）",
                    "default": "",
                },
                "keyword": {
                    "type": "string",
                    "description": "按仓库名/路径搜索（可选）",
                    "default": "",
                },
                "provider_id": {
                    "type": "string",
                    "description": "按 Git 平台 ID 筛选（可选）",
                    "default": "",
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortgit.models import GitRepo

        project_id = params.get("project_id", "")
        keyword = params.get("keyword", "")
        provider_id = params.get("provider_id", "")

        sf = get_session_factory()
        async with sf() as session:
            stmt = select(GitRepo).order_by(GitRepo.updated_at.desc())
            if project_id:
                stmt = stmt.where(GitRepo.project_id == project_id)
            if provider_id:
                stmt = stmt.where(GitRepo.provider_id == provider_id)
            if keyword:
                stmt = stmt.where(
                    GitRepo.name.contains(keyword) | GitRepo.full_name.contains(keyword)
                )
            stmt = stmt.limit(50)

            result = await session.execute(stmt)
            repos = result.scalars().all()

            data = [
                {
                    "id": r.id,
                    "name": r.name,
                    "full_name": r.full_name,
                    "language": r.language,
                    "repo_type": r.repo_type,
                    "default_branch": r.default_branch,
                    "description": r.description[:200] if r.description else "",
                    "project_id": r.project_id or "",
                    "is_private": r.is_private,
                }
                for r in repos
            ]

        return json.dumps(
            {"ok": True, "count": len(data), "repos": data},
            ensure_ascii=False,
        )


class RepoInfoTool(BaseTool):
    name = "git_repo_info"
    description = (
        "查看指定仓库的详细信息，包括基本属性、分支列表和最近提交记录。"
        "需要提供仓库 ID 或仓库完整路径（full_name）。"
    )
    required_permission = "vortgit.read"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "repo_id": {
                    "type": "string",
                    "description": "仓库 ID（repo_id 和 full_name 二选一）",
                    "default": "",
                },
                "full_name": {
                    "type": "string",
                    "description": "仓库完整路径，如 org/repo（repo_id 和 full_name 二选一）",
                    "default": "",
                },
                "include_branches": {
                    "type": "boolean",
                    "description": "是否包含分支列表（默认 true）",
                    "default": True,
                },
                "include_commits": {
                    "type": "boolean",
                    "description": "是否包含最近提交（默认 true）",
                    "default": True,
                },
                "commit_count": {
                    "type": "integer",
                    "description": "返回的最近提交数量（默认 10）",
                    "default": 10,
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortgit.models import GitProvider, GitRepo

        repo_id = params.get("repo_id", "")
        full_name = params.get("full_name", "")
        include_branches = params.get("include_branches", True)
        include_commits = params.get("include_commits", True)
        commit_count = min(params.get("commit_count", 10), 50)

        if not repo_id and not full_name:
            return json.dumps({"ok": False, "message": "请提供 repo_id 或 full_name"})

        sf = get_session_factory()
        async with sf() as session:
            if repo_id:
                repo = await session.get(GitRepo, repo_id)
            else:
                repo = await session.scalar(
                    select(GitRepo).where(GitRepo.full_name == full_name)
                )
            if not repo:
                return json.dumps({"ok": False, "message": "仓库不存在"})

            provider = await session.get(GitProvider, repo.provider_id)
            if not provider:
                return json.dumps({"ok": False, "message": "仓库关联的 Git 平台不存在"})

        info: dict = {
            "id": repo.id,
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "language": repo.language,
            "repo_type": repo.repo_type,
            "default_branch": repo.default_branch,
            "clone_url": repo.clone_url,
            "is_private": repo.is_private,
            "project_id": repo.project_id or "",
            "last_synced_at": repo.last_synced_at.isoformat() if repo.last_synced_at else None,
        }

        client = self._create_provider(provider)
        try:
            if include_branches:
                try:
                    info["branches"] = await client.list_branches(repo.full_name)
                except Exception as e:
                    log.warning(f"Failed to fetch branches for {repo.full_name}: {e}")
                    info["branches"] = []
                    info["branches_error"] = str(e)

            if include_commits:
                try:
                    info["recent_commits"] = await client.list_commits(
                        repo.full_name,
                        branch=repo.default_branch,
                        per_page=commit_count,
                    )
                except Exception as e:
                    log.warning(f"Failed to fetch commits for {repo.full_name}: {e}")
                    info["recent_commits"] = []
                    info["commits_error"] = str(e)
        finally:
            await client.close()

        return json.dumps({"ok": True, "repo": info}, ensure_ascii=False)

    @staticmethod
    def _create_provider(provider):
        """Create a provider client from DB record."""
        from openvort.plugins.vortgit.crypto import decrypt_token

        token = decrypt_token(provider.access_token) if provider.access_token else ""
        if provider.platform == "gitee":
            from openvort.plugins.vortgit.providers.gitee import GiteeProvider
            return GiteeProvider(access_token=token, api_base=provider.api_base)
        raise ValueError(f"Unsupported platform: {provider.platform}")
