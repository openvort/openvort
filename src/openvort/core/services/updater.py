"""
System update service — version check, database backup, pip upgrade, frontend download.
"""

import asyncio
import json
import os
import platform
import re
import shutil
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from openvort import __version__
from openvort.config.settings import get_settings
from openvort.utils.logging import get_logger

log = get_logger("updater")


GITHUB_PROXIES = [
    "https://ghfast.com/",
    "https://mirror.ghproxy.com/",
    "https://gh-proxy.com/",
]


class UpdateService:
    GITHUB_REPO = "openvort/openvort"
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
        _require_pg_tool("pg_dump")

        db = self._parse_db_url()
        await _check_pg_dump_compat(db)
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
        try:
            _require_pg_tool("psql")
        except RuntimeError as e:
            yield _sse("error", str(e))
            return

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
        total_steps = 7

        def _p(message, *, step, current_step, percent, **kw):
            return _sse("progress", message, step=step,
                        current_step=current_step, total_steps=total_steps,
                        percent=percent, **kw)

        try:
            # Step 1: Backup database  (0% → 15%)
            yield _p("正在备份数据库...", step="backing_up", current_step=1, percent=0)
            try:
                backup_info = await self.backup_database()
                yield _p(f"备份完成: {backup_info['filename']}", step="backed_up",
                         current_step=1, percent=15)
            except Exception as e:
                yield _sse("error", f"数据库备份失败: {e}")
                return

            # Step 2: Find release assets  (15% → 20%)
            yield _p("正在获取版本信息...", step="fetching", current_step=2, percent=15)
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

            yield _p("版本信息获取完成", step="fetching", current_step=2, percent=20)

            # Step 3: Download backend  (20% → 50%)
            tmp_dir.mkdir(parents=True, exist_ok=True)
            whl_path = tmp_dir / whl_asset["name"]
            try:
                yield _p(f"正在下载后端包 ({whl_asset['name']})...",
                         step="downloading", current_step=3, percent=20)
                dl_q: asyncio.Queue[tuple[int, int] | None] = asyncio.Queue()

                async def _dl_whl():
                    try:
                        await self._download_asset(
                            whl_asset["browser_download_url"], whl_path,
                            on_progress=lambda d, t: dl_q.put_nowait((d, t)))
                    finally:
                        dl_q.put_nowait(None)

                task = asyncio.create_task(_dl_whl())
                while True:
                    item = await dl_q.get()
                    if item is None:
                        break
                    d, t = item
                    dp = int(d * 100 / t) if t else 0
                    yield _p(f"正在下载后端包 ({_fmt_bytes(d)}/{_fmt_bytes(t)})",
                             step="downloading", current_step=3,
                             percent=20 + int(dp * 0.30))
                await task
                _validate_wheel(whl_path)
            except Exception as e:
                yield _sse("error", f"下载后端包失败: {e}")
                return

            # Step 4: Download frontend  (50% → 70%)
            frontend_path = None
            if frontend_asset:
                frontend_path = tmp_dir / frontend_asset["name"]
                try:
                    yield _p(f"正在下载前端包 ({frontend_asset['name']})...",
                             step="downloading_frontend", current_step=4, percent=50)
                    dl_q2: asyncio.Queue[tuple[int, int] | None] = asyncio.Queue()

                    async def _dl_fe():
                        try:
                            await self._download_asset(
                                frontend_asset["browser_download_url"], frontend_path,
                                on_progress=lambda d, t: dl_q2.put_nowait((d, t)))
                        finally:
                            dl_q2.put_nowait(None)

                    task2 = asyncio.create_task(_dl_fe())
                    while True:
                        item = await dl_q2.get()
                        if item is None:
                            break
                        d, t = item
                        dp = int(d * 100 / t) if t else 0
                        yield _p(f"正在下载前端包 ({_fmt_bytes(d)}/{_fmt_bytes(t)})",
                                 step="downloading_frontend", current_step=4,
                                 percent=50 + int(dp * 0.20))
                    await task2
                except Exception as e:
                    log.warning(f"下载前端包失败（跳过）: {e}")
                    frontend_path = None

            # Step 5: Install backend  (70% → 85%)
            yield _p("正在安装后端更新...", step="installing", current_step=5, percent=70)
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", "--no-deps", str(whl_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                output, _ = await proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(output.decode(errors="replace")[-500:])
                yield _p("后端安装完成", step="installed", current_step=5, percent=85)
            except Exception as e:
                yield _p(f"安装失败，正在回滚到 {old_version}...",
                         step="rolling_back", current_step=5, percent=75)
                await self._rollback_pip(old_version)
                yield _sse("error", f"后端安装失败并已回滚: {e}")
                return

            # Step 6: Update frontend  (85% → 92%)
            if frontend_path and frontend_path.exists():
                yield _p("正在更新前端...", step="updating_frontend",
                         current_step=6, percent=85)
                try:
                    self._extract_frontend(frontend_path)
                    yield _p("前端更新完成", step="frontend_updated",
                             current_step=6, percent=92)
                except Exception as e:
                    log.warning(f"前端更新失败（跳过）: {e}")

            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
            self._cache = None

            # Step 7: Restart  (95% → 100%)
            yield _p("更新完成，正在重启服务...", step="restarting",
                     current_step=7, percent=95)
            yield _sse("done", f"已更新到 {target_version}，请刷新页面", percent=100)

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

    async def _download_asset(self, url: str, dest: Path,
                              on_progress=None) -> None:
        """Download a release asset, auto-fallback to proxy mirrors if direct fails."""
        custom_proxy = os.environ.get("OPENVORT_GITHUB_PROXY", "").strip().rstrip("/")

        if custom_proxy:
            urls = [f"{custom_proxy}/{url}"]
        else:
            urls = [url] + [f"{p}{url}" for p in GITHUB_PROXIES]

        last_err: Exception | None = None
        for i, target_url in enumerate(urls):
            is_direct = (i == 0 and not custom_proxy)
            timeout = 5 if is_direct else 300
            label = "直连" if is_direct else target_url.split("/")[2]
            try:
                log.info(f"下载 ({label}): {target_url[:120]}")
                await self._do_download(target_url, dest, timeout=timeout,
                                        on_progress=on_progress)
                return
            except Exception as e:
                last_err = e
                log.warning(f"下载失败 ({label}): {e}")
                if dest.exists():
                    dest.unlink()
        raise RuntimeError(f"所有下载源均失败: {last_err}")

    async def _do_download(self, url: str, dest: Path, timeout: int = 300,
                           on_progress=None) -> None:
        """Execute the actual HTTP download.

        on_progress: optional sync callback(downloaded_bytes, total_bytes),
                     throttled to fire at most every ~2 percentage-points.
        """
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                ct = resp.headers.get("content-type", "")
                if "text/html" in ct:
                    raise RuntimeError(f"响应为 HTML 页面而非文件 (Content-Type: {ct})")
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                last_pct = -1
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes(8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total > 0:
                            pct = int(downloaded * 100 / total)
                            if pct >= last_pct + 3 or downloaded >= total:
                                last_pct = pct
                                on_progress(downloaded, total)

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

def _require_pg_tool(name: str) -> None:
    """Raise RuntimeError with install instructions if *name* is not on PATH."""
    if shutil.which(name):
        return
    system = platform.system()
    if system == "Darwin":
        hint = f"请安装 PostgreSQL 客户端工具: brew install libpq && brew link --force libpq"
    elif system == "Linux":
        hint = f"请安装 PostgreSQL 客户端工具: apt-get install -y postgresql-client"
    else:
        hint = f"请安装 PostgreSQL 客户端工具以获取 {name} 命令"
    raise RuntimeError(f"未找到 {name} 命令。{hint}")


def _get_pg_tool_major_version(name: str) -> int | None:
    """Return the major version of a PG client tool (pg_dump / psql), or None."""
    path = shutil.which(name)
    if not path:
        return None
    try:
        import subprocess
        out = subprocess.check_output([path, "--version"], text=True, timeout=5)
        m = re.search(r"(\d+)\.\d+", out)
        return int(m.group(1)) if m else None
    except Exception:
        return None


async def _get_server_major_version(db_params: dict) -> int | None:
    """Query the PG server major version via psql, or None on failure."""
    psql = shutil.which("psql")
    if not psql:
        return None
    env = os.environ.copy()
    env["PGPASSWORD"] = db_params.get("password", "")
    try:
        proc = await asyncio.create_subprocess_exec(
            psql,
            "-h", db_params["host"],
            "-p", db_params["port"],
            "-U", db_params["user"],
            "-d", db_params["dbname"],
            "-t", "-A", "-c", "SHOW server_version;",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        m = re.search(r"(\d+)\.\d+", stdout.decode().strip())
        return int(m.group(1)) if m else None
    except Exception:
        return None


async def _check_pg_dump_compat(db_params: dict) -> None:
    """Raise RuntimeError if pg_dump major version < server major version.

    On Linux (Debian/Ubuntu), automatically attempts to install the matching
    postgresql-client package before raising.
    """
    dump_ver = _get_pg_tool_major_version("pg_dump")
    server_ver = await _get_server_major_version(db_params)

    if dump_ver is None or server_ver is None:
        return

    if dump_ver >= server_ver:
        return

    system = platform.system()

    if system == "Linux":
        log.warning(
            f"pg_dump 版本 ({dump_ver}) < 服务器版本 ({server_ver})，"
            f"尝试自动安装 postgresql-client-{server_ver} ..."
        )
        installed = await _auto_install_pg_client(server_ver)
        if installed:
            new_ver = _get_pg_tool_major_version("pg_dump")
            if new_ver and new_ver >= server_ver:
                log.info(f"postgresql-client-{server_ver} 安装成功，pg_dump 版本: {new_ver}")
                return
            log.warning(f"安装后 pg_dump 版本仍为 {new_ver}，期望 >= {server_ver}")

    if system == "Linux":
        codename = _get_debian_codename() or "bookworm"
        hint = (
            f"解决方法：安装与服务器匹配的客户端工具\n"
            f"  curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc "
            f"| gpg --dearmor -o /usr/share/keyrings/pgdg.gpg\n"
            f"  echo 'deb [signed-by=/usr/share/keyrings/pgdg.gpg] "
            f"http://apt.postgresql.org/pub/repos/apt {codename}-pgdg main' "
            f"> /etc/apt/sources.list.d/pgdg.list\n"
            f"  apt-get update && apt-get install -y postgresql-client-{server_ver}"
        )
    elif system == "Darwin":
        hint = f"解决方法: brew install postgresql@{server_ver}"
    else:
        hint = f"解决方法: 安装 PostgreSQL {server_ver} 的客户端工具"
    raise RuntimeError(
        f"pg_dump 版本 ({dump_ver}) 低于数据库服务器版本 ({server_ver})，"
        f"无法执行备份。\n{hint}"
    )


def _get_debian_codename() -> str | None:
    """Read VERSION_CODENAME from /etc/os-release."""
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_CODENAME="):
                    return line.strip().split("=", 1)[1].strip('"')
    except Exception:
        pass
    return None


async def _auto_install_pg_client(server_ver: int) -> bool:
    """Try to install postgresql-client-<server_ver> via apt on Debian/Ubuntu.

    Returns True if the install command succeeded.
    """
    codename = _get_debian_codename()
    if not codename:
        log.warning("无法检测发行版 codename，跳过自动安装")
        return False

    for prereq in ("curl", "gpg"):
        if not shutil.which(prereq):
            try:
                log.info(f"安装前置依赖: {prereq}")
                proc = await asyncio.create_subprocess_exec(
                    "apt-get", "update",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
                proc = await asyncio.create_subprocess_exec(
                    "apt-get", "install", "-y", "--no-install-recommends",
                    prereq, "ca-certificates",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, err = await proc.communicate()
                if proc.returncode != 0:
                    log.warning(f"安装 {prereq} 失败: {err.decode(errors='replace')[:200]}")
                    return False
            except Exception as e:
                log.warning(f"安装 {prereq} 异常: {e}")
                return False

    keyring = "/usr/share/keyrings/pgdg.gpg"
    list_file = "/etc/apt/sources.list.d/pgdg.list"

    try:
        if not os.path.exists(keyring):
            cmd = f"curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o {keyring}"
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate()
            if proc.returncode != 0:
                log.warning(f"导入 PGDG GPG key 失败: {err.decode(errors='replace')[:200]}")
                return False

        repo_line = (
            f"deb [signed-by={keyring}] "
            f"http://apt.postgresql.org/pub/repos/apt {codename}-pgdg main"
        )
        if not os.path.exists(list_file):
            with open(list_file, "w") as f:
                f.write(repo_line + "\n")

        log.info(f"apt-get update && apt-get install postgresql-client-{server_ver} ...")
        proc = await asyncio.create_subprocess_exec(
            "apt-get", "update",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        proc = await asyncio.create_subprocess_exec(
            "apt-get", "install", "-y", "--no-install-recommends",
            f"postgresql-client-{server_ver}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        if proc.returncode != 0:
            log.warning(
                f"安装 postgresql-client-{server_ver} 失败 (exit {proc.returncode}): "
                f"{out.decode(errors='replace')[-300:]}"
            )
            return False

        return True
    except Exception as e:
        log.warning(f"自动安装 postgresql-client-{server_ver} 异常: {e}")
        return False


def _validate_wheel(path: Path) -> None:
    """Raise if the downloaded file is not a valid wheel archive."""
    size = path.stat().st_size
    if size < 2048:
        raise RuntimeError(f"文件过小 ({size} bytes)，下载可能被代理劫持或截断")
    if not zipfile.is_zipfile(path):
        raise RuntimeError("文件不是有效的 wheel 包（非 zip 格式），下载内容可能已损坏")
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        has_metadata = any(n.endswith("/METADATA") for n in names)
        has_wheel = any(n.endswith("/WHEEL") for n in names)
        if not (has_metadata and has_wheel):
            raise RuntimeError("wheel 包结构不完整，缺少 METADATA 或 WHEEL 文件")


def _fmt_bytes(n: int) -> str:
    """Human-readable byte size."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


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
