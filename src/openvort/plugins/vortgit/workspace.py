"""WorkspaceManager — per-member isolated Git workspaces.

Each member gets a dedicated local clone for each repo, stored under:
    data_dir/git_workspaces/{member_id}/{repo_id}/

Key features:
- Shallow clone (--depth 1) to save disk
- HTTPS + access_token for auth
- Branch naming: vortgit/{member_name}/{task_id_or_timestamp}
- Concurrency safety via asyncio.Lock per workspace
- Disk usage tracking
"""

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit.workspace")

_workspace_locks: dict[str, asyncio.Lock] = {}

# CLI tool artifacts that must not be committed (Aider, Codex, Claude Code, etc.)
_CLI_ARTIFACT_PATTERNS = [
    ".aider*",
    ".codex",
    ".claude",
]


def _get_lock(workspace_key: str) -> asyncio.Lock:
    if workspace_key not in _workspace_locks:
        _workspace_locks[workspace_key] = asyncio.Lock()
    return _workspace_locks[workspace_key]


async def _run_git(args: list[str], cwd: str | Path, timeout: int = 120) -> tuple[int, str, str]:
    """Run a git command via asyncio.subprocess."""
    cmd = ["git"] + args
    log.debug(f"git {' '.join(args)} [cwd={cwd}]")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return -1, "", "git command timed out"
    return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")


def _inject_token_url(clone_url: str, token: str) -> str:
    """Inject access_token into HTTPS clone URL for authentication."""
    if not token or not clone_url.startswith("https://"):
        return clone_url
    return clone_url.replace("https://", f"https://oauth2:{token}@", 1)


def _dir_size_mb(path: Path) -> int:
    """Calculate directory size in MB (approximate)."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total // (1024 * 1024)


class WorkspaceManager:
    """Manages per-member Git workspaces."""

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            from openvort.config.settings import get_settings
            data_dir = get_settings().data_dir
        self._base_dir = data_dir / "git_workspaces"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def workspace_path(self, member_id: str, repo_id: str) -> Path:
        return self._base_dir / member_id / repo_id

    async def ensure_workspace(
        self, member_id: str, repo_id: str, clone_url: str, token: str, default_branch: str = "main"
    ) -> Path:
        """Ensure workspace exists (clone if needed, pull if exists)."""
        lock_key = f"{member_id}:{repo_id}"
        async with _get_lock(lock_key):
            ws_path = self.workspace_path(member_id, repo_id)

            if (ws_path / ".git").exists():
                await self._pull(ws_path, default_branch)
            else:
                await self._clone(clone_url, token, ws_path)

            await self._update_workspace_db(member_id, repo_id, ws_path, default_branch)
            return ws_path

    async def checkout_branch(
        self, member_id: str, repo_id: str, branch_name: str, create: bool = True
    ) -> str:
        """Checkout (or create) a branch in the workspace."""
        lock_key = f"{member_id}:{repo_id}"
        async with _get_lock(lock_key):
            ws_path = self.workspace_path(member_id, repo_id)
            if not (ws_path / ".git").exists():
                raise RuntimeError(f"Workspace not initialized: {ws_path}")

            if create:
                rc, out, err = await _run_git(["checkout", "-b", branch_name], ws_path)
                if rc != 0 and "already exists" in err:
                    rc, out, err = await _run_git(["checkout", branch_name], ws_path)
            else:
                rc, out, err = await _run_git(["checkout", branch_name], ws_path)

            if rc != 0:
                raise RuntimeError(f"Failed to checkout {branch_name}: {err}")

            await self._update_branch_db(member_id, repo_id, branch_name)
            return branch_name

    async def commit(self, member_id: str, repo_id: str, message: str, author_name: str = "", author_email: str = "") -> str:
        """Stage all changes and commit."""
        lock_key = f"{member_id}:{repo_id}"
        async with _get_lock(lock_key):
            ws_path = self.workspace_path(member_id, repo_id)

            rc, out, err = await _run_git(["add", "-A"], ws_path)
            if rc != 0:
                raise RuntimeError(f"git add failed: {err}")

            # Unstage CLI tool artifacts that shouldn't be committed
            for pattern in _CLI_ARTIFACT_PATTERNS:
                await _run_git(["rm", "--cached", "-r", "--ignore-unmatch", pattern], ws_path)

            cmd = ["commit", "-m", message]
            if author_name and author_email:
                cmd.extend(["--author", f"{author_name} <{author_email}>"])

            rc, out, err = await _run_git(cmd, ws_path)
            if rc != 0:
                if "nothing to commit" in out or "nothing to commit" in err:
                    return ""
                raise RuntimeError(f"git commit failed: {err}")

            rc2, sha_out, _ = await _run_git(["rev-parse", "HEAD"], ws_path)
            return sha_out.strip()[:12]

    async def push(self, member_id: str, repo_id: str, branch: str, clone_url: str, token: str) -> str:
        """Push current branch to remote."""
        lock_key = f"{member_id}:{repo_id}"
        async with _get_lock(lock_key):
            ws_path = self.workspace_path(member_id, repo_id)
            auth_url = _inject_token_url(clone_url, token)

            await _run_git(["remote", "set-url", "origin", auth_url], ws_path)
            rc, out, err = await _run_git(["push", "-u", "origin", branch], ws_path, timeout=180)

            if rc != 0:
                raise RuntimeError(f"git push failed: {err}")
            return out + err

    async def get_diff_summary(self, member_id: str, repo_id: str, base_branch: str = "") -> dict:
        """Get diff summary between current branch and base."""
        ws_path = self.workspace_path(member_id, repo_id)
        if not (ws_path / ".git").exists():
            return {"files_changed": [], "summary": ""}

        if base_branch:
            rc, out, err = await _run_git(["diff", "--stat", base_branch], ws_path)
        else:
            rc, out, err = await _run_git(["diff", "--stat", "HEAD~1"], ws_path)

        rc2, files_out, _ = await _run_git(
            ["diff", "--name-only", base_branch] if base_branch else ["diff", "--name-only", "HEAD~1"],
            ws_path,
        )
        files = [f for f in files_out.strip().split("\n") if f]

        return {
            "files_changed": files,
            "summary": out.strip(),
            "file_count": len(files),
        }

    async def get_status(self, member_id: str, repo_id: str) -> dict:
        """Get workspace git status."""
        ws_path = self.workspace_path(member_id, repo_id)
        if not (ws_path / ".git").exists():
            return {"exists": False}

        rc, branch_out, _ = await _run_git(["rev-parse", "--abbrev-ref", "HEAD"], ws_path)
        rc2, status_out, _ = await _run_git(["status", "--porcelain"], ws_path)

        return {
            "exists": True,
            "path": str(ws_path),
            "branch": branch_out.strip(),
            "clean": not status_out.strip(),
            "disk_usage_mb": _dir_size_mb(ws_path),
        }

    async def cleanup(self, member_id: str, repo_id: str) -> bool:
        """Remove workspace directory."""
        ws_path = self.workspace_path(member_id, repo_id)
        if ws_path.exists():
            shutil.rmtree(ws_path, ignore_errors=True)
            log.info(f"Cleaned up workspace: {ws_path}")
            return True
        return False

    # ---- internal ----

    async def _clone(self, clone_url: str, token: str, ws_path: Path) -> None:
        auth_url = _inject_token_url(clone_url, token)
        ws_path.parent.mkdir(parents=True, exist_ok=True)

        rc, out, err = await _run_git(
            ["clone", "--depth", "1", auth_url, str(ws_path)],
            cwd=ws_path.parent,
            timeout=300,
        )
        if rc != 0:
            if ws_path.exists():
                shutil.rmtree(ws_path, ignore_errors=True)
            raise RuntimeError(f"git clone failed: {err}")
        log.info(f"Cloned to {ws_path}")

    async def _pull(self, ws_path: Path, default_branch: str) -> None:
        rc, branch, _ = await _run_git(["rev-parse", "--abbrev-ref", "HEAD"], ws_path)
        current = branch.strip()

        if current != default_branch:
            await _run_git(["checkout", default_branch], ws_path)

        rc, out, err = await _run_git(["pull", "--rebase", "--autostash"], ws_path, timeout=180)
        if rc != 0:
            log.warning(f"git pull failed in {ws_path}: {err}, trying reset")
            await _run_git(["fetch", "origin"], ws_path, timeout=180)
            await _run_git(["reset", "--hard", f"origin/{default_branch}"], ws_path)

    async def _update_workspace_db(self, member_id: str, repo_id: str, ws_path: Path, branch: str) -> None:
        try:
            from openvort.db.engine import get_session_factory
            from openvort.plugins.vortgit.models import GitWorkspace

            sf = get_session_factory()
            async with sf() as session:
                ws = await session.scalar(
                    select(GitWorkspace).where(
                        GitWorkspace.repo_id == repo_id,
                        GitWorkspace.member_id == member_id,
                    )
                )
                now = datetime.utcnow()
                disk = _dir_size_mb(ws_path)
                if ws:
                    ws.local_path = str(ws_path)
                    ws.current_branch = branch
                    ws.status = "idle"
                    ws.disk_usage_mb = disk
                    ws.last_used_at = now
                else:
                    import uuid
                    ws = GitWorkspace(
                        id=uuid.uuid4().hex,
                        repo_id=repo_id,
                        member_id=member_id,
                        local_path=str(ws_path),
                        current_branch=branch,
                        status="idle",
                        disk_usage_mb=disk,
                        last_used_at=now,
                    )
                    session.add(ws)
                await session.commit()
        except Exception as e:
            log.warning(f"Failed to update workspace DB: {e}")

    async def _update_branch_db(self, member_id: str, repo_id: str, branch: str) -> None:
        try:
            from openvort.db.engine import get_session_factory
            from openvort.plugins.vortgit.models import GitWorkspace

            sf = get_session_factory()
            async with sf() as session:
                ws = await session.scalar(
                    select(GitWorkspace).where(
                        GitWorkspace.repo_id == repo_id,
                        GitWorkspace.member_id == member_id,
                    )
                )
                if ws:
                    ws.current_branch = branch
                    ws.last_used_at = datetime.utcnow()
                    await session.commit()
        except Exception as e:
            log.warning(f"Failed to update branch in DB: {e}")
