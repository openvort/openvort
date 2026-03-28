"""
VortGit commit tools — git_query_commits, git_work_summary

Read-only tools for querying commit history and generating multi-dimensional
work reports combining Git activity with VortFlow task progress.
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit.tools.commits")


def _create_provider(provider):
    """Create a provider client from DB record."""
    from openvort.plugins.vortgit.crypto import decrypt_token
    from openvort.plugins.vortgit.providers import create_provider

    token = decrypt_token(provider.access_token) if provider.access_token else ""
    return create_provider(provider.platform, access_token=token, api_base=provider.api_base)


class QueryCommitsTool(BaseTool):
    name = "git_query_commits"
    description = (
        "查询 Git 提交记录。支持按仓库、分支、作者、日期范围筛选。"
        "可指定单个仓库，也可跨多个仓库查询某个作者的提交。"
    )
    required_permission = "vortgit.read"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "repo_id": {
                    "type": "string",
                    "description": "仓库 ID（可选，不填则查所有仓库）",
                    "default": "",
                },
                "branch": {
                    "type": "string",
                    "description": "分支名（可选，默认仓库主分支）",
                    "default": "",
                },
                "author": {
                    "type": "string",
                    "description": "作者名称或邮箱（可选）",
                    "default": "",
                },
                "since": {
                    "type": "string",
                    "description": "起始时间（ISO 格式 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS）",
                    "default": "",
                },
                "until": {
                    "type": "string",
                    "description": "结束时间（ISO 格式）",
                    "default": "",
                },
                "page": {
                    "type": "integer",
                    "description": "页码（默认 1）",
                    "default": 1,
                },
                "per_page": {
                    "type": "integer",
                    "description": "每页数量（默认 20，最大 50）",
                    "default": 20,
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortgit.models import GitProvider, GitRepo

        repo_id = params.get("repo_id", "")
        branch = params.get("branch", "")
        author = params.get("author", "")
        since = params.get("since", "")
        until = params.get("until", "")
        page = max(params.get("page", 1), 1)
        per_page = min(max(params.get("per_page", 20), 1), 50)

        sf = get_session_factory()
        all_commits: list[dict] = []

        async with sf() as session:
            if repo_id:
                repos = [await session.get(GitRepo, repo_id)]
                repos = [r for r in repos if r is not None]
            else:
                result = await session.execute(
                    select(GitRepo).order_by(GitRepo.updated_at.desc()).limit(20)
                )
                repos = list(result.scalars().all())

            if not repos:
                return json.dumps({"ok": False, "message": "未找到仓库"})

            provider_cache: dict = {}
            for repo in repos:
                if repo.provider_id not in provider_cache:
                    p = await session.get(GitProvider, repo.provider_id)
                    if p:
                        provider_cache[repo.provider_id] = p

        for repo in repos:
            provider = provider_cache.get(repo.provider_id)
            if not provider:
                continue
            client = _create_provider(provider)
            try:
                commits = await client.list_commits(
                    repo.full_name,
                    branch=branch or repo.default_branch,
                    since=since,
                    until=until,
                    author=author,
                    page=page,
                    per_page=per_page,
                )
                for c in commits:
                    c["repo_name"] = repo.name
                    c["repo_full_name"] = repo.full_name
                all_commits.extend(commits)
            except Exception as e:
                log.warning(f"Failed to fetch commits from {repo.full_name}: {e}")
            finally:
                await client.close()

        all_commits.sort(key=lambda c: c.get("authored_date", ""), reverse=True)

        return json.dumps(
            {"ok": True, "count": len(all_commits), "commits": all_commits},
            ensure_ascii=False,
        )


class WorkSummaryTool(BaseTool):
    name = "git_work_summary"
    description = (
        "生成多维度工作汇报，综合 Git 提交记录和 VortFlow 任务完成情况。"
        "分析提交数、活跃仓库、完成的需求/任务/Bug，可按成员、项目、时间范围筛选。"
        "适合生成日报、周报、月报。"
    )
    required_permission = "vortgit.read"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "member_name": {
                    "type": "string",
                    "description": "成员名称（匹配 Git 提交作者名和 VortFlow 任务负责人，可选）",
                    "default": "",
                },
                "project_id": {
                    "type": "string",
                    "description": "VortFlow 项目 ID（可选，限定项目范围）",
                    "default": "",
                },
                "period": {
                    "type": "string",
                    "description": "时间范围：today / week / month / custom（默认 week）",
                    "default": "week",
                },
                "since": {
                    "type": "string",
                    "description": "自定义起始时间 YYYY-MM-DD（period=custom 时必填）",
                    "default": "",
                },
                "until": {
                    "type": "string",
                    "description": "自定义结束时间 YYYY-MM-DD（period=custom 时必填）",
                    "default": "",
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        member_name = params.get("member_name", "")
        project_id = params.get("project_id", "")
        period = params.get("period", "week")
        custom_since = params.get("since", "")
        custom_until = params.get("until", "")

        since_dt, until_dt = self._resolve_period(period, custom_since, custom_until)

        since_str = since_dt.strftime("%Y-%m-%dT00:00:00+08:00")
        until_str = until_dt.strftime("%Y-%m-%dT23:59:59+08:00")

        git_summary = await self._collect_git_data(
            project_id, member_name, since_str, until_str
        )
        vortflow_summary = await self._collect_vortflow_data(
            project_id, member_name, since_dt, until_dt
        )
        references = self._extract_references(git_summary.get("commits", []))

        report = {
            "ok": True,
            "period": {
                "label": self._period_label(period),
                "since": since_dt.strftime("%Y-%m-%d"),
                "until": until_dt.strftime("%Y-%m-%d"),
            },
            "git": {
                "total_commits": git_summary["total_commits"],
                "active_repos": git_summary["active_repos"],
                "authors": git_summary["authors"],
                "repo_breakdown": git_summary["repo_breakdown"],
            },
            "vortflow": vortflow_summary,
            "cross_references": references,
        }

        if member_name:
            report["member"] = member_name

        return json.dumps(report, ensure_ascii=False)

    # ---- Git data collection ----

    async def _collect_git_data(
        self, project_id: str, author: str, since: str, until: str
    ) -> dict:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortgit.models import GitProvider, GitRepo

        sf = get_session_factory()
        async with sf() as session:
            stmt = select(GitRepo).order_by(GitRepo.updated_at.desc())
            if project_id:
                stmt = stmt.where(GitRepo.project_id == project_id)
            stmt = stmt.limit(30)
            result = await session.execute(stmt)
            repos = list(result.scalars().all())

            provider_cache: dict = {}
            for repo in repos:
                if repo.provider_id not in provider_cache:
                    p = await session.get(GitProvider, repo.provider_id)
                    if p:
                        provider_cache[repo.provider_id] = p

        all_commits: list[dict] = []
        repo_breakdown: list[dict] = []

        for repo in repos:
            provider = provider_cache.get(repo.provider_id)
            if not provider:
                continue
            client = _create_provider(provider)
            try:
                commits = await client.list_commits(
                    repo.full_name,
                    branch=repo.default_branch,
                    since=since,
                    until=until,
                    author=author,
                    per_page=50,
                )
                if commits:
                    repo_breakdown.append({
                        "repo": repo.full_name,
                        "repo_type": repo.repo_type,
                        "commits": len(commits),
                    })
                    all_commits.extend(commits)
            except Exception as e:
                log.warning(f"Failed to fetch commits from {repo.full_name}: {e}")
            finally:
                await client.close()

        authors: dict[str, int] = defaultdict(int)
        for c in all_commits:
            name = c.get("author_name", "unknown")
            authors[name] += 1

        return {
            "total_commits": len(all_commits),
            "active_repos": len(repo_breakdown),
            "authors": [{"name": k, "commits": v} for k, v in sorted(authors.items(), key=lambda x: -x[1])],
            "repo_breakdown": sorted(repo_breakdown, key=lambda x: -x["commits"]),
            "commits": all_commits,
        }

    # ---- VortFlow data collection ----

    async def _collect_vortflow_data(
        self, project_id: str, member_name: str, since_dt: datetime, until_dt: datetime
    ) -> dict:
        try:
            from openvort.plugins.vortflow.models import FlowStory, FlowTask, FlowBug
        except ImportError:
            return {"available": False, "message": "VortFlow 插件未安装"}

        from openvort.db.engine import get_session_factory

        member_id = ""
        if member_name:
            member_id = await self._resolve_member_id(member_name)

        sf = get_session_factory()
        async with sf() as session:
            stories_completed = await self._count_completed(
                session, FlowStory, project_id, member_id, since_dt, until_dt,
                state_field="state", done_states=("closed", "verified", "done"),
                assignee_field="pm_id",
            )
            tasks_completed = await self._count_completed(
                session, FlowTask, project_id, member_id, since_dt, until_dt,
                state_field="state", done_states=("done", "closed"),
                assignee_field="assignee_id",
            )
            bugs_fixed = await self._count_completed(
                session, FlowBug, project_id, member_id, since_dt, until_dt,
                state_field="state", done_states=("closed", "verified", "resolved"),
                assignee_field="assignee_id",
            )

            stories_in_progress = await self._count_in_state(
                session, FlowStory, project_id, member_id,
                states=("developing", "reviewing", "testing"),
                assignee_field="pm_id",
            )
            tasks_in_progress = await self._count_in_state(
                session, FlowTask, project_id, member_id,
                states=("doing", "in_progress"),
                assignee_field="assignee_id",
            )

        return {
            "available": True,
            "stories_completed": stories_completed,
            "tasks_completed": tasks_completed,
            "bugs_fixed": bugs_fixed,
            "stories_in_progress": stories_in_progress,
            "tasks_in_progress": tasks_in_progress,
        }

    @staticmethod
    async def _count_completed(session, model, project_id, member_id, since_dt, until_dt,
                                state_field, done_states, assignee_field):
        conditions = [
            getattr(model, state_field).in_(done_states),
        ]
        if hasattr(model, "updated_at"):
            conditions.append(model.updated_at >= since_dt)
            conditions.append(model.updated_at <= until_dt)
        if project_id and hasattr(model, "project_id"):
            conditions.append(model.project_id == project_id)
        if member_id and hasattr(model, assignee_field):
            conditions.append(getattr(model, assignee_field) == member_id)
        try:
            result = await session.scalar(
                select(func.count()).select_from(model).where(and_(*conditions))
            )
            return result or 0
        except Exception:
            return 0

    @staticmethod
    async def _count_in_state(session, model, project_id, member_id, states, assignee_field):
        conditions = [model.state.in_(states)]
        if project_id and hasattr(model, "project_id"):
            conditions.append(model.project_id == project_id)
        if member_id and hasattr(model, assignee_field):
            conditions.append(getattr(model, assignee_field) == member_id)
        try:
            result = await session.scalar(
                select(func.count()).select_from(model).where(and_(*conditions))
            )
            return result or 0
        except Exception:
            return 0

    @staticmethod
    async def _resolve_member_id(name: str) -> str:
        """Try to resolve member name to member_id."""
        try:
            from openvort.contacts.models import Member
            from openvort.db.engine import get_session_factory

            sf = get_session_factory()
            async with sf() as session:
                result = await session.scalar(
                    select(Member.id).where(Member.name == name)
                )
                return result or ""
        except Exception:
            return ""

    # ---- Cross-reference extraction ----

    @staticmethod
    def _extract_references(commits: list[dict]) -> list[dict]:
        """Extract #story-xxx / #task-xxx references from commit messages."""
        pattern = re.compile(r"#(story|task|bug)-([a-zA-Z0-9]+)")
        refs: list[dict] = []
        seen = set()
        for c in commits:
            msg = c.get("message", "")
            for match in pattern.finditer(msg):
                entity_type, entity_id = match.group(1), match.group(2)
                key = f"{entity_type}-{entity_id}"
                if key not in seen:
                    seen.add(key)
                    refs.append({
                        "type": entity_type,
                        "id": entity_id,
                        "commit_sha": c.get("sha", "")[:8],
                        "commit_message": msg[:100],
                    })
        return refs

    # ---- Period helpers ----

    @staticmethod
    def _resolve_period(period: str, custom_since: str, custom_until: str):
        now = datetime.now()
        if period == "today":
            return now.replace(hour=0, minute=0, second=0), now
        elif period == "week":
            start = now - timedelta(days=now.weekday())
            return start.replace(hour=0, minute=0, second=0), now
        elif period == "month":
            return now.replace(day=1, hour=0, minute=0, second=0), now
        elif period == "custom" and custom_since:
            since_dt = datetime.strptime(custom_since, "%Y-%m-%d")
            if custom_until:
                until_dt = datetime.strptime(custom_until, "%Y-%m-%d")
            else:
                until_dt = now
            return since_dt, until_dt
        else:
            start = now - timedelta(days=now.weekday())
            return start.replace(hour=0, minute=0, second=0), now

    @staticmethod
    def _period_label(period: str) -> str:
        return {"today": "今日", "week": "本周", "month": "本月", "custom": "自定义"}.get(period, "本周")
