"""
VortGit coding tools — git_code_task, git_commit_push, git_create_pr

AI-driven coding workflow: prepare workspace → run CLI tool → commit → push → create PR.
"""

import json
import uuid
from datetime import datetime

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit.tools.coding")


def _create_provider(provider):
    """Create a provider client from DB record."""
    from openvort.plugins.vortgit.crypto import decrypt_token

    token = decrypt_token(provider.access_token) if provider.access_token else ""
    if provider.platform == "gitee":
        from openvort.plugins.vortgit.providers.gitee import GiteeProvider
        return GiteeProvider(access_token=token, api_base=provider.api_base)
    if provider.platform == "github":
        from openvort.plugins.vortgit.providers.github import GitHubProvider
        return GitHubProvider(access_token=token, api_base=provider.api_base)
    raise ValueError(f"Unsupported platform: {provider.platform}")


async def _get_repo_and_provider(repo_id: str):
    """Load repo + provider from DB. Returns (repo, provider, token) or raises."""
    from openvort.db.engine import get_session_factory
    from openvort.plugins.vortgit.crypto import decrypt_token
    from openvort.plugins.vortgit.models import GitProvider, GitRepo

    sf = get_session_factory()
    async with sf() as session:
        repo = await session.get(GitRepo, repo_id)
        if not repo:
            raise ValueError(f"Repo not found: {repo_id}")
        provider = await session.get(GitProvider, repo.provider_id)
        if not provider:
            raise ValueError(f"Provider not found for repo: {repo.full_name}")
        token = decrypt_token(provider.access_token) if provider.access_token else ""
    return repo, provider, token


def _extract_stream_text(line: str) -> str:
    """Extract human-readable text from a Claude Code stream-json line.

    Claude Code stream-json emits one JSON object per line.  We care about:
    - assistant text deltas (content_block_delta with text_delta)
    - tool use starts (tool name + input summary)
    - tool results (brief)
    """
    line = line.strip()
    if not line:
        return ""
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return line  # fallback: raw text

    msg_type = obj.get("type", "")

    # stream_event wraps the real event
    if msg_type == "stream_event":
        event = obj.get("event", {})
        delta = event.get("delta", {})
        delta_type = delta.get("type", "")
        if delta_type == "text_delta":
            return delta.get("text", "")
        if delta_type == "input_json_delta":
            return ""
        return ""

    # Top-level assistant message
    if msg_type == "assistant":
        content = obj.get("message", {}).get("content", [])
        parts = []
        for block in content:
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                parts.append(f"[调用工具: {block.get('name', '?')}]")
        return "".join(parts)

    # Tool result
    if msg_type == "result":
        result_text = obj.get("result", "")
        if result_text and len(result_text) > 200:
            result_text = result_text[:200] + "..."
        return f"\n✅ {result_text}" if result_text else ""

    return ""


def _get_coding_env():
    """Create CodingEnvironment from VortGit settings."""
    from openvort.core.coding_env import CodingEnvironment
    from openvort.plugins.vortgit.config import VortGitSettings

    settings = VortGitSettings()
    return CodingEnvironment(
        image=settings.cli_docker_image,
        timeout=settings.cli_timeout,
    )


def _get_cli_runner():
    from openvort.plugins.vortgit.cli_runner import CLIRunner
    return CLIRunner(_get_coding_env())


def _get_workspace_manager():
    from openvort.plugins.vortgit.workspace import WorkspaceManager
    return WorkspaceManager()


class CodeTaskTool(BaseTool):
    """Full AI coding workflow: workspace → CLI → commit → push → PR."""

    name = "git_code_task"
    description = (
        "在 Git 仓库中执行 AI 编码任务（修 Bug、实现需求、代码优化），"
        "自动创建分支、运行 CLI 编码工具修改代码、提交并创建 PR。"
        "执行时间较长（1-5 分钟），适合明确的代码修改任务。"
    )
    required_permission = "vortgit.write"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "repo_id": {
                    "type": "string",
                    "description": "目标仓库 ID",
                },
                "task_description": {
                    "type": "string",
                    "description": "编码任务的详细描述（修什么 Bug / 实现什么功能 / 如何修改）",
                },
                "bug_id": {
                    "type": "string",
                    "description": "关联的 VortFlow Bug ID（可选，会自动获取 Bug 详情作为上下文）",
                    "default": "",
                },
                "task_id": {
                    "type": "string",
                    "description": "关联的 VortFlow 任务 ID（可选）",
                    "default": "",
                },
                "story_id": {
                    "type": "string",
                    "description": "关联的 VortFlow 需求 ID（可选）",
                    "default": "",
                },
                "branch_name": {
                    "type": "string",
                    "description": "工作分支名（可选，自动生成如 fix/bug-42 或 feat/task-xxx）",
                    "default": "",
                },
                "base_branch": {
                    "type": "string",
                    "description": "基础分支（可选，默认仓库主分支）",
                    "default": "",
                },
                "cli_tool": {
                    "type": "string",
                    "enum": ["claude-code", "aider"],
                    "description": "使用的 CLI 编码工具（默认 claude-code）",
                    "default": "claude-code",
                },
                "auto_pr": {
                    "type": "boolean",
                    "description": "完成后是否自动创建 PR",
                    "default": True,
                },
            },
            "required": ["repo_id", "task_description"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.core.coding_env import EnvMode

        repo_id = params["repo_id"]
        task_desc = params["task_description"]
        bug_id = params.get("bug_id", "")
        task_id = params.get("task_id", "")
        story_id = params.get("story_id", "")
        branch_name = params.get("branch_name", "")
        base_branch = params.get("base_branch", "")
        auto_pr = params.get("auto_pr", True)
        member_id = params.get("_member_id", "system")
        output_queue = params.pop("_output_queue", None)

        # 1. Load CLI config from DB (tool + model chain)
        cli_tool, model_chain = await self._load_cli_config(
            params.get("cli_tool", ""),
        )

        # 2. Check coding environment
        env = _get_coding_env()
        mode = env.detect_mode()
        if mode == EnvMode.UNAVAILABLE:
            status = await env.get_status()
            return json.dumps({
                "ok": False,
                "error": "coding_env_not_ready",
                "message": "AI 编码环境未就绪，需要管理员配置",
                "details": status.to_dict(),
                "setup_guide": "管理员在服务器执行: openvort coding setup",
                "who_can_fix": "admin",
            }, ensure_ascii=False)

        # 3. Load repo info
        try:
            repo, provider, token = await _get_repo_and_provider(repo_id)
        except ValueError as e:
            return json.dumps({"ok": False, "message": str(e)}, ensure_ascii=False)

        effective_base = base_branch or repo.default_branch

        # 4. Generate branch name
        if not branch_name:
            branch_name = self._generate_branch_name(bug_id, task_id, story_id)

        # 5. Build enriched prompt
        prompt = await self._build_coding_prompt(task_desc, bug_id, task_id, story_id, repo)

        # 6. Create task record
        task_record_id = await self._create_task_record(
            repo_id, member_id, story_id, task_id, bug_id, cli_tool, task_desc, branch_name
        )

        try:
            return await self._run_coding_workflow(
                task_record_id, repo, provider, token, effective_base,
                member_id, repo_id, branch_name, cli_tool, prompt,
                task_desc, bug_id, task_id, auto_pr,
                model_chain=model_chain,
                output_queue=output_queue,
            )
        except Exception as e:
            log.error(f"Coding task unexpected error: {e}", exc_info=True)
            await self._update_task_status(task_record_id, "failed", stderr=str(e))
            return json.dumps({
                "ok": False, "message": f"编码任务异常终止: {e}"
            }, ensure_ascii=False)

    async def _run_coding_workflow(
        self, task_record_id, repo, provider, token, effective_base,
        member_id, repo_id, branch_name, cli_tool, prompt,
        task_desc, bug_id, task_id, auto_pr,
        model_chain: list[dict] | None = None,
        output_queue=None,
    ) -> str:
        """Core workflow, wrapped so execute() can catch any unhandled exception."""

        def _on_output(line: str):
            if not output_queue:
                return
            text = _extract_stream_text(line)
            if text:
                try:
                    output_queue.put_nowait(text)
                except Exception:
                    pass

        # Prepare workspace
        ws_mgr = _get_workspace_manager()
        try:
            ws_path = await ws_mgr.ensure_workspace(
                member_id, repo_id, repo.clone_url, token, effective_base
            )
            await ws_mgr.checkout_branch(member_id, repo_id, branch_name, create=True)
        except Exception as e:
            await self._update_task_status(task_record_id, "failed", stderr=str(e))
            return json.dumps({
                "ok": False, "message": f"工作空间准备失败: {e}"
            }, ensure_ascii=False)

        # Run CLI tool with model chain failover
        runner = _get_cli_runner()
        result = await self._run_with_model_chain(
            runner, cli_tool, ws_path, prompt, model_chain,
            on_output=_on_output if output_queue else None,
        )

        if not result.success:
            await self._update_task_status(
                task_record_id, "failed",
                stdout=result.stdout, stderr=result.stderr,
                duration=result.duration_seconds,
            )
            return json.dumps({
                "ok": False,
                "message": f"CLI 工具 {cli_tool} 执行失败",
                "stderr": result.stderr[:1000],
                "duration_seconds": result.duration_seconds,
            }, ensure_ascii=False)

        # 8. Commit changes
        try:
            commit_msg = f"fix: {task_desc[:80]}"
            if bug_id:
                commit_msg = f"fix: #{bug_id} {task_desc[:60]}"
            elif task_id:
                commit_msg = f"feat: #{task_id} {task_desc[:60]}"

            sha = await ws_mgr.commit(member_id, repo_id, commit_msg)
            if not sha:
                await self._update_task_status(task_record_id, "failed", stderr="No changes to commit")
                return json.dumps({
                    "ok": False,
                    "message": "CLI 工具未产生任何代码变更",
                    "duration_seconds": result.duration_seconds,
                }, ensure_ascii=False)
        except Exception as e:
            await self._update_task_status(task_record_id, "failed", stderr=str(e))
            return json.dumps({
                "ok": False, "message": f"提交失败: {e}"
            }, ensure_ascii=False)

        # 9. Push
        try:
            await ws_mgr.push(member_id, repo_id, branch_name, repo.clone_url, token)
        except Exception as e:
            await self._update_task_status(task_record_id, "failed", stderr=str(e))
            return json.dumps({
                "ok": False, "message": f"推送失败: {e}"
            }, ensure_ascii=False)

        # 10. Create PR
        pr_url = ""
        if auto_pr:
            try:
                client = _create_provider(provider)
                try:
                    pr = await client.create_pull_request(
                        repo.full_name,
                        title=commit_msg,
                        head=branch_name,
                        base=effective_base,
                        body=self._build_pr_body(task_desc, bug_id, task_id, result),
                    )
                    pr_url = pr.get("url", "")
                finally:
                    await client.close()
            except Exception as e:
                log.warning(f"Failed to create PR: {e}")

        # 11. Get diff summary
        diff = await ws_mgr.get_diff_summary(member_id, repo_id, effective_base)

        # 12. Update task record
        await self._update_task_status(
            task_record_id, "review" if pr_url else "success",
            stdout=result.stdout, stderr=result.stderr,
            duration=result.duration_seconds,
            pr_url=pr_url,
            files_changed=result.files_changed,
            diff_summary=diff.get("summary", ""),
        )

        return json.dumps({
            "ok": True,
            "message": "编码任务完成",
            "branch": branch_name,
            "commit_sha": sha,
            "files_changed": result.files_changed,
            "file_count": len(result.files_changed),
            "diff_summary": diff.get("summary", ""),
            "pr_url": pr_url,
            "duration_seconds": result.duration_seconds,
            "cli_tool": cli_tool,
        }, ensure_ascii=False)

    # ---- Helpers ----

    @staticmethod
    async def _load_cli_config(override_tool: str = "") -> tuple[str, list[dict]]:
        """Load CLI tool name and model chain from DB config.

        Returns (cli_tool, model_chain). model_chain may be empty if
        no CLI model is configured (falls back to legacy env vars).
        """
        try:
            from openvort.db.engine import get_session_factory
            from openvort.config.config_service import ConfigService

            sf = get_session_factory()
            cs = ConfigService(sf)
            await cs.load_all()
            cfg = await cs.get_cli_config()
            tool = override_tool or cfg["cli_default_tool"] or "claude-code"
            chain = await cs.get_cli_model_chain()
            return tool, chain
        except Exception as e:
            log.debug(f"Failed to load CLI config from DB, using defaults: {e}")
            fallback_tool = override_tool or "claude-code"
            try:
                from openvort.plugins.vortgit.config import VortGitSettings
                fallback_tool = override_tool or VortGitSettings().cli_default_tool
            except Exception:
                pass
            return fallback_tool, []

    @staticmethod
    async def _run_with_model_chain(
        runner, cli_tool: str, ws_path, prompt: str,
        model_chain: list[dict],
        on_output=None,
    ):
        """Run CLI with model chain failover.

        Tries primary model first, then each fallback in order.
        If model_chain is empty, runs without model config (legacy).
        """
        from openvort.plugins.vortgit.cli_runner import CLIResult

        if not model_chain:
            return await runner.run(
                cli_tool, ws_path, prompt, on_output=on_output,
            )

        last_result: CLIResult | None = None
        for i, model_cfg in enumerate(model_chain):
            model_name = model_cfg.get("model", "?")
            label = "primary" if i == 0 else f"fallback#{i}"
            log.info(f"CLI model {label}: {model_cfg.get('provider')}/{model_name}")

            result = await runner.run(
                cli_tool, ws_path, prompt,
                model_config=model_cfg,
                on_output=on_output,
            )
            if result.success:
                return result

            last_result = result
            if i < len(model_chain) - 1:
                log.warning(
                    f"CLI {label} model {model_name} failed, "
                    f"trying next fallback..."
                )

        return last_result or CLIResult(
            success=False, stderr="No models configured", tool_name=cli_tool,
        )

    def _get_default_tool(self) -> str:
        try:
            from openvort.plugins.vortgit.config import VortGitSettings
            return VortGitSettings().cli_default_tool
        except Exception:
            return "claude-code"

    @staticmethod
    def _generate_branch_name(bug_id: str, task_id: str, story_id: str) -> str:
        if bug_id:
            return f"fix/bug-{bug_id[:12]}"
        if task_id:
            return f"feat/task-{task_id[:12]}"
        if story_id:
            return f"feat/story-{story_id[:12]}"
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"vortgit/ai-{ts}"

    @staticmethod
    async def _build_coding_prompt(
        task_desc: str, bug_id: str, task_id: str, story_id: str, repo
    ) -> str:
        parts = []

        # Fetch VortFlow context if available
        if bug_id or task_id or story_id:
            ctx = await CodeTaskTool._fetch_vortflow_context(bug_id, task_id, story_id)
            if ctx:
                parts.append(ctx)

        parts.append(f"## Task\n{task_desc}")

        parts.append(
            f"## Repository\n- Name: {repo.full_name}\n"
            f"- Language: {repo.language or 'unknown'}\n"
            f"- Type: {repo.repo_type}"
        )

        parts.append(
            "## Constraints\n"
            "- Only modify necessary files\n"
            "- Keep existing code style consistent\n"
            "- Add or update tests if test files exist\n"
            "- Do not remove unrelated code"
        )

        return "\n\n".join(parts)

    @staticmethod
    async def _fetch_vortflow_context(bug_id: str, task_id: str, story_id: str) -> str:
        """Try to fetch Bug/Task/Story details from VortFlow."""
        try:
            from openvort.db.engine import get_session_factory

            sf = get_session_factory()
            parts = []
            async with sf() as session:
                if bug_id:
                    from openvort.plugins.vortflow.models import FlowBug
                    bug = await session.get(FlowBug, bug_id)
                    if bug:
                        parts.append(
                            f"## Bug Info\n"
                            f"- Title: {bug.title}\n"
                            f"- Severity: {getattr(bug, 'severity', 'N/A')}\n"
                            f"- Description: {getattr(bug, 'description', '')[:500]}\n"
                            f"- Steps to reproduce: {getattr(bug, 'steps', '')[:500]}"
                        )
                if task_id:
                    from openvort.plugins.vortflow.models import FlowTask
                    task = await session.get(FlowTask, task_id)
                    if task:
                        parts.append(
                            f"## Task Info\n"
                            f"- Title: {task.title}\n"
                            f"- Description: {getattr(task, 'description', '')[:500]}"
                        )
                if story_id:
                    from openvort.plugins.vortflow.models import FlowStory
                    story = await session.get(FlowStory, story_id)
                    if story:
                        parts.append(
                            f"## Story Info\n"
                            f"- Title: {story.title}\n"
                            f"- Description: {getattr(story, 'description', '')[:500]}"
                        )
            return "\n\n".join(parts)
        except Exception as e:
            log.debug(f"Failed to fetch VortFlow context: {e}")
            return ""

    @staticmethod
    def _build_pr_body(task_desc: str, bug_id: str, task_id: str, result) -> str:
        lines = ["## Summary", f"{task_desc}", ""]
        if bug_id:
            lines.append(f"Fixes #{bug_id}")
        if task_id:
            lines.append(f"Relates to #{task_id}")
        if result.files_changed:
            lines.extend(["", "## Changed Files"])
            for f in result.files_changed[:20]:
                lines.append(f"- `{f}`")
        lines.extend(["", "*Generated by OpenVort AI Coding*"])
        return "\n".join(lines)

    @staticmethod
    async def _create_task_record(
        repo_id, member_id, story_id, task_id, bug_id, cli_tool, task_desc, branch_name
    ) -> str:
        try:
            from openvort.db.engine import get_session_factory
            from openvort.plugins.vortgit.models import GitCodeTask

            record_id = uuid.uuid4().hex
            sf = get_session_factory()
            async with sf() as session:
                record = GitCodeTask(
                    id=record_id,
                    repo_id=repo_id,
                    member_id=member_id,
                    story_id=story_id or None,
                    task_id=task_id or None,
                    bug_id=bug_id or None,
                    cli_tool=cli_tool,
                    task_description=task_desc,
                    branch_name=branch_name,
                    status="running",
                )
                session.add(record)
                await session.commit()
            return record_id
        except Exception as e:
            log.warning(f"Failed to create task record: {e}")
            return ""

    @staticmethod
    async def _update_task_status(
        record_id: str, status: str, *,
        stdout: str = "", stderr: str = "", duration: int = 0,
        pr_url: str = "", files_changed: list | None = None, diff_summary: str = "",
    ) -> None:
        if not record_id:
            return
        try:
            from openvort.db.engine import get_session_factory
            from openvort.plugins.vortgit.models import GitCodeTask

            sf = get_session_factory()
            async with sf() as session:
                record = await session.get(GitCodeTask, record_id)
                if record:
                    record.status = status
                    record.cli_stdout = stdout[:50000]
                    record.cli_stderr = stderr[:10000]
                    record.duration_seconds = duration
                    record.pr_url = pr_url
                    if files_changed is not None:
                        record.files_changed = json.dumps(files_changed)
                    record.diff_summary = diff_summary[:10000]
                    await session.commit()
        except Exception as e:
            log.warning(f"Failed to update task record: {e}")


class CommitPushTool(BaseTool):
    """Commit and push changes in an existing workspace."""

    name = "git_commit_push"
    description = (
        "在已有的 Git 工作空间中提交所有变更并推送到远程。"
        "用于手动控制编码流程后的提交步骤。"
    )
    required_permission = "vortgit.write"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "repo_id": {
                    "type": "string",
                    "description": "仓库 ID",
                },
                "commit_message": {
                    "type": "string",
                    "description": "提交信息",
                },
            },
            "required": ["repo_id", "commit_message"],
        }

    async def execute(self, params: dict) -> str:
        repo_id = params["repo_id"]
        message = params["commit_message"]
        member_id = params.get("_member_id", "system")

        try:
            repo, provider, token = await _get_repo_and_provider(repo_id)
        except ValueError as e:
            return json.dumps({"ok": False, "message": str(e)}, ensure_ascii=False)

        ws_mgr = _get_workspace_manager()

        status = await ws_mgr.get_status(member_id, repo_id)
        if not status.get("exists"):
            return json.dumps({
                "ok": False, "message": "工作空间不存在，请先通过 git_code_task 创建"
            }, ensure_ascii=False)

        try:
            sha = await ws_mgr.commit(member_id, repo_id, message)
            if not sha:
                return json.dumps({
                    "ok": False, "message": "没有需要提交的变更"
                }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "message": f"提交失败: {e}"}, ensure_ascii=False)

        try:
            branch = status.get("branch", "main")
            await ws_mgr.push(member_id, repo_id, branch, repo.clone_url, token)
        except Exception as e:
            return json.dumps({"ok": False, "message": f"推送失败: {e}"}, ensure_ascii=False)

        return json.dumps({
            "ok": True,
            "message": "提交并推送成功",
            "commit_sha": sha,
            "branch": branch,
        }, ensure_ascii=False)


class CreatePRTool(BaseTool):
    """Create a Pull Request on the Git platform."""

    name = "git_create_pr"
    description = (
        "在 Git 平台上创建 Pull Request（合并请求）。"
        "指定源分支和目标分支，可用于 AI 编码后创建 PR 或手动创建。"
    )
    required_permission = "vortgit.write"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "repo_id": {
                    "type": "string",
                    "description": "仓库 ID",
                },
                "title": {
                    "type": "string",
                    "description": "PR 标题",
                },
                "head": {
                    "type": "string",
                    "description": "源分支（如 fix/bug-42）",
                },
                "base": {
                    "type": "string",
                    "description": "目标分支（可选，默认仓库主分支）",
                    "default": "",
                },
                "body": {
                    "type": "string",
                    "description": "PR 描述（可选）",
                    "default": "",
                },
            },
            "required": ["repo_id", "title", "head"],
        }

    async def execute(self, params: dict) -> str:
        repo_id = params["repo_id"]
        title = params["title"]
        head = params["head"]
        base = params.get("base", "")
        body = params.get("body", "")

        try:
            repo, provider, token = await _get_repo_and_provider(repo_id)
        except ValueError as e:
            return json.dumps({"ok": False, "message": str(e)}, ensure_ascii=False)

        effective_base = base or repo.default_branch

        client = _create_provider(provider)
        try:
            pr = await client.create_pull_request(
                repo.full_name,
                title=title,
                head=head,
                base=effective_base,
                body=body,
            )
            return json.dumps({
                "ok": True,
                "message": "PR 创建成功",
                "pr_number": pr.get("number"),
                "pr_url": pr.get("url", ""),
                "title": title,
                "head": head,
                "base": effective_base,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "ok": False, "message": f"创建 PR 失败: {e}"
            }, ensure_ascii=False)
        finally:
            await client.close()
