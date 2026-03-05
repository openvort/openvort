"""
System update service — version check, database backup, pip upgrade, frontend download.
"""

import asyncio
import json
import os
import re
import shutil
import sys
import tarfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from openvort import __version__
from openvort.config.settings import get_settings
from openvort.utils.logging import get_logger

log = get_logger("updater")


class UpdateService:
    GITHUB_REPO = "nicekate/openvort"
    GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    CACHE_TTL = 4 * 3600

    def __init__(self):
        self._cache: dict | None = None
        self._cache_time: float = 0
        self._upgrading = False

    @property
    def is_upgrading(self) -> bool:
        return self._upgrading

    # ------------------------------------------------------------------ #
    #  Version check
    # ------------------------------------------------------------------ #

    async def check_update(self, force: bool = False) -> dict:
        """Check GitHub releases for a newer version. Results are cached."""
        now = time.monotonic()
        if not force and self._cache and (now - self._cache_time) < self.CACHE_TTL:
            return self._cache

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.GITHUB_API}/latest",
                    headers={"Accept": "application/vnd.github+json"},
                )
                resp.raise_for_status()
                data = resp.json()

            latest = _normalize_version(data.get("tag_name", ""))
            current = _normalize_version(__version__)

            result = {
                "current_version": __version__,
                "latest_version": latest,
                "update_available": _version_gt(latest, current),
                "release_notes": data.get("body", ""),
                "published_at": data.get("published_at", ""),
                "html_url": data.get("html_url", ""),
            }
            self._cache = result
            self._cache_time = now
            return result
        except Exception as e:
            log.warning(f"检查更新失败: {e}")
            return {
                "current_version": __version__,
                "latest_version": "",
                "update_available": False,
                "release_notes": "",
                "published_at": "",
                "html_url": "",
                "error": str(e)[:200],
            }

    async def get_releases(self, per_page: int = 20) -> list[dict]:
        """Fetch recent releases from GitHub."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.GITHUB_API,
                    params={"per_page": per_page},
                    headers={"Accept": "application/vnd.github+json"},
                )
                resp.raise_for_status()
                items = resp.json()

            current = _normalize_version(__version__)
            releases = []
            for item in items:
                if item.get("draft"):
                    continue
                ver = _normalize_version(item.get("tag_name", ""))
                releases.append({
                    "version": ver,
                    "tag_name": item["tag_name"],
                    "release_notes": item.get("body", ""),
                    "published_at": item.get("published_at", ""),
                    "html_url": item.get("html_url", ""),
                    "is_current": ver == current,
                    "is_newer": _version_gt(ver, current),
                    "assets": [
                        {"name": a["name"], "size": a["size"], "url": a["browser_download_url"]}
                        for a in item.get("assets", [])
                    ],
                })
            return releases
        except Exception as e:
            log.warning(f"获取版本列表失败: {e}")
            return []

    # ------------------------------------------------------------------ #
    #  Database backup
    # ------------------------------------------------------------------ #

    def _backup_dir(self) -> Path:
        d = get_settings().data_dir / "backups"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _parse_db_url(self) -> dict:
        """Extract connection params from database_url for pg_dump."""
        url = get_settings().database_url
        # asyncpg URL → psycopg2 style for pg_dump
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(url)
        return {
            "host": parsed.hostname or "localhost",
            "port": str(parsed.port or 5432),
            "user": parsed.username or "openvort",
            "password": parsed.password or "",
            "dbname": parsed.path.lstrip("/") or "openvort",
        }

    async def backup_database(self) -> dict:
        """Run pg_dump and return backup file info."""
        db = self._parse_db_url()
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"openvort_{ts}.sql"
        filepath = self._backup_dir() / filename

        env = os.environ.copy()
        env["PGPASSWORD"] = db["password"]
        cmd = [
            "pg_dump",
            "-h", db["host"],
            "-p", db["port"],
            "-U", db["user"],
            "-d", db["dbname"],
            "-f", str(filepath),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            raise RuntimeError(f"pg_dump 失败 (exit {proc.returncode}): {err}")

        stat = filepath.stat()
        log.info(f"数据库备份完成: {filepath} ({stat.st_size} bytes)")
        return {
            "filename": filename,
            "size": stat.st_size,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
        }

    def list_backups(self) -> list[dict]:
        """List existing backup files."""
        backups = []
        for f in sorted(self._backup_dir().glob("*.sql"), reverse=True):
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "size": stat.st_size,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
            })
        return backups

    def get_backup_path(self, filename: str) -> Path | None:
        """Return full path if backup exists."""
        p = self._backup_dir() / filename
        if p.exists() and p.suffix == ".sql":
            return p
        return None

    def delete_backup(self, filename: str) -> bool:
        p = self.get_backup_path(filename)
        if p:
            p.unlink()
            log.info(f"备份已删除: {filename}")
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Restore database
    # ------------------------------------------------------------------ #

    async def restore_database(self, filename: str):
        """Async generator yielding SSE events during database restore."""
        filepath = self.get_backup_path(filename)
        if not filepath:
            yield _sse("error", f"备份文件不存在: {filename}")
            return

        yield _sse("progress", "正在恢复数据库...", step="restoring")

        db = self._parse_db_url()
        env = os.environ.copy()
        env["PGPASSWORD"] = db["password"]
        cmd = [
            "psql",
            "-h", db["host"],
            "-p", db["port"],
            "-U", db["user"],
            "-d", db["dbname"],
            "-f", str(filepath),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        async for line in proc.stdout:
            pass  # consume output silently
        await proc.wait()

        if proc.returncode != 0:
            yield _sse("error", f"数据库恢复失败 (exit {proc.returncode})")
            return

        yield _sse("progress", "数据库恢复完成，正在重启服务...", step="restarting")
        yield _sse("done", "恢复完成，请刷新页面")

        _schedule_restart()

    # ------------------------------------------------------------------ #
    #  Apply update (upgrade / downgrade)
    # ------------------------------------------------------------------ #

    async def apply_update(self, target_version: str):
        """Async generator yielding SSE events during upgrade/downgrade."""
        if self._upgrading:
            yield _sse("error", "已有升级任务正在执行")
            return

        self._upgrading = True
        old_version = __version__
        tmp_dir = get_settings().data_dir / "upgrade_tmp"

        try:
            # Step 1: Backup database
            yield _sse("progress", "正在备份数据库...", step="backing_up")
            try:
                backup_info = await self.backup_database()
                yield _sse("progress", f"备份完成: {backup_info['filename']}", step="backed_up")
            except Exception as e:
                yield _sse("error", f"数据库备份失败: {e}")
                return

            # Step 2: Find release assets
            yield _sse("progress", "正在获取版本信息...", step="fetching")
            release = await self._find_release(target_version)
            if not release:
                yield _sse("error", f"未找到版本 {target_version} 的发布信息")
                return

            whl_asset = None
            frontend_asset = None
            for asset in release.get("assets", []):
                name = asset["name"]
                if name.endswith(".whl"):
                    whl_asset = asset
                elif "frontend" in name and name.endswith(".tar.gz"):
                    frontend_asset = asset

            if not whl_asset:
                yield _sse("error", f"版本 {target_version} 缺少 .whl 文件")
                return

            # Step 3: Download assets
            tmp_dir.mkdir(parents=True, exist_ok=True)

            yield _sse("progress", f"正在下载后端包 ({whl_asset['name']})...", step="downloading")
            whl_path = tmp_dir / whl_asset["name"]
            try:
                await self._download_asset(whl_asset["url"], whl_path)
            except Exception as e:
                yield _sse("error", f"下载后端包失败: {e}")
                return

            frontend_path = None
            if frontend_asset:
                yield _sse("progress", f"正在下载前端包 ({frontend_asset['name']})...", step="downloading_frontend")
                frontend_path = tmp_dir / frontend_asset["name"]
                try:
                    await self._download_asset(frontend_asset["url"], frontend_path)
                except Exception as e:
                    log.warning(f"下载前端包失败（跳过）: {e}")
                    frontend_path = None

            # Step 4: Install backend
            yield _sse("progress", "正在安装后端更新...", step="installing")
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", "--no-deps", str(whl_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                output, _ = await proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(output.decode(errors="replace")[-500:])
                yield _sse("progress", "后端安装完成", step="installed")
            except Exception as e:
                yield _sse("progress", f"安装失败，正在回滚到 {old_version}...", step="rolling_back")
                await self._rollback_pip(old_version)
                yield _sse("error", f"后端安装失败并已回滚: {e}")
                return

            # Step 5: Update frontend
            if frontend_path and frontend_path.exists():
                yield _sse("progress", "正在更新前端...", step="updating_frontend")
                try:
                    self._extract_frontend(frontend_path)
                    yield _sse("progress", "前端更新完成", step="frontend_updated")
                except Exception as e:
                    log.warning(f"前端更新失败（跳过）: {e}")

            # Step 6: Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
            self._cache = None

            # Step 7: Restart
            yield _sse("progress", "更新完成，正在重启服务...", step="restarting")
            yield _sse("done", f"已更新到 {target_version}，请刷新页面")

            _schedule_restart()

        except Exception as e:
            yield _sse("error", f"升级异常: {e}")
        finally:
            self._upgrading = False

    async def _find_release(self, version: str) -> dict | None:
        """Find a specific release by version."""
        normalized = _normalize_version(version)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Try exact tag first
                for tag in [f"v{normalized}", normalized, version]:
                    resp = await client.get(
                        f"{self.GITHUB_API}/tags/{tag}",
                        headers={"Accept": "application/vnd.github+json"},
                    )
                    if resp.status_code == 200:
                        return resp.json()

                # Fallback: search in recent releases
                resp = await client.get(
                    self.GITHUB_API,
                    params={"per_page": 50},
                    headers={"Accept": "application/vnd.github+json"},
                )
                resp.raise_for_status()
                for item in resp.json():
                    if _normalize_version(item.get("tag_name", "")) == normalized:
                        return item
        except Exception as e:
            log.warning(f"查找版本 {version} 失败: {e}")
        return None

    async def _download_asset(self, url: str, dest: Path) -> None:
        """Download a release asset."""
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes(8192):
                        f.write(chunk)

    def _extract_frontend(self, tarball: Path) -> None:
        """Extract frontend dist tarball to the correct location."""
        # Determine target directory
        if Path("/app/web/dist").exists():
            target = Path("/app/web/dist")
        else:
            target = Path(__file__).parent.parent.parent.parent / "web" / "dist"

        # Remove old assets
        assets_dir = target / "assets"
        if assets_dir.exists():
            shutil.rmtree(assets_dir)

        with tarfile.open(tarball, "r:gz") as tar:
            # Detect if files are inside a subdirectory
            members = tar.getmembers()
            prefix = ""
            if members and "/" in members[0].name:
                prefix = members[0].name.split("/")[0] + "/"

            for member in members:
                if member.name.startswith(prefix):
                    member.name = member.name[len(prefix):]
                if member.name and not member.name.startswith(".."):
                    tar.extract(member, target)

        log.info(f"前端已更新: {target}")

    async def _rollback_pip(self, version: str) -> None:
        """Attempt to reinstall the previous version."""
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", f"openvort=={version}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await proc.communicate()
            log.info(f"已回滚到 openvort=={version}")
        except Exception as e:
            log.error(f"回滚失败: {e}")


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

def _normalize_version(v: str) -> str:
    """Strip leading 'v' and whitespace."""
    return v.strip().lstrip("vV").strip()


def _version_gt(a: str, b: str) -> bool:
    """Return True if version a > version b."""
    try:
        def _parts(v):
            return [int(x) for x in v.split(".")]
        return _parts(a) > _parts(b)
    except (ValueError, AttributeError):
        return False


def _sse(event_type: str, message: str, **extra) -> str:
    """Format an SSE data line."""
    payload = {"type": event_type, "message": message, **extra}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _schedule_restart(delay: float = 1.5) -> None:
    """Schedule a process restart after a short delay."""
    def _do():
        time.sleep(delay)
        try:
            from openvort.cli import _cleanup_pid
            _cleanup_pid()
        except Exception:
            pass
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=_do, daemon=True).start()


# Singleton
_update_service: UpdateService | None = None


def get_update_service() -> UpdateService:
    global _update_service
    if _update_service is None:
        _update_service = UpdateService()
    return _update_service
