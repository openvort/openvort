"""
Marketplace installer - installs skills/plugins from the marketplace into local OpenVort.
Supports both content-only (text) and bundle (zip) installation modes.
"""

import hashlib
import json
import logging
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from openvort.db.models import Skill
from openvort.marketplace.client import MarketplaceClient
from openvort.plugin.registry import PluginRegistry

logger = logging.getLogger(__name__)


def _compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MarketplaceInstaller:
    """Handles installing and uninstalling marketplace extensions."""

    def __init__(
        self,
        client: MarketplaceClient,
        session_factory,
        registry: PluginRegistry,
        data_dir: Path | None = None,
    ):
        self.client = client
        self.session_factory = session_factory
        self.registry = registry
        self.data_dir = data_dir or Path.home() / ".openvort"
        self.bundles_dir = self.data_dir / "marketplace" / "bundles"
        self.plugins_local_dir = self.data_dir / "plugins" / "local"

    async def install_skill(self, slug: str, author: str = "") -> dict[str, Any]:
        """
        Install a skill from the marketplace:
        1. Fetch skill data from marketplace API
        2. If bundle available, download and extract
        3. Write to local DB (scope='marketplace')
        4. Register prompt to PluginRegistry
        5. Report download
        """
        data = await self.client.get_skill(slug, author=author)
        skill_name = data.get("name", slug)
        bundle_url = data.get("bundleUrl")
        has_bundle = bool(bundle_url)

        if has_bundle:
            dest = self.bundles_dir / "skills" / slug
            zip_path = dest / "bundle.zip"
            await self.client.download_bundle(bundle_url, zip_path)

            remote_hash = data.get("bundleHash", "")
            if remote_hash:
                local_hash = _compute_hash(zip_path.read_bytes())
                if local_hash != remote_hash:
                    logger.warning("Bundle hash mismatch for %s: expected %s, got %s", slug, remote_hash, local_hash)

            extract_dir = dest / "files"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)

            content = data.get("content", "")
            if not content:
                skill_md = _find_file(extract_dir, "SKILL.md")
                if skill_md:
                    content = skill_md.read_text(encoding="utf-8")

            logger.info("Skill bundle extracted to %s", extract_dir)
        else:
            content = data.get("content", "")

        async with self.session_factory() as session:
            session: AsyncSession
            existing = await session.execute(
                select(Skill).where(
                    Skill.scope == "marketplace",
                    Skill.name == skill_name,
                )
            )
            existing_skill = existing.scalar_one_or_none()

            if existing_skill:
                existing_skill.content = content
                existing_skill.description = data.get("description", "")
                existing_skill.skill_type = data.get("skillType", "workflow")
                existing_skill.tags = json.dumps(data.get("tags", []))
                existing_skill.marketplace_slug = slug
                existing_skill.marketplace_author = data.get("author", author)
                existing_skill.marketplace_version = data.get("version", "1.0.0")
                action = "updated"
            else:
                from openvort.db.models import _uuid
                skill = Skill(
                    id=_uuid(),
                    name=skill_name,
                    description=data.get("description", ""),
                    content=content,
                    scope="marketplace",
                    skill_type=data.get("skillType", "workflow"),
                    tags=json.dumps(data.get("tags", [])),
                    enabled=True,
                    marketplace_slug=slug,
                    marketplace_author=data.get("author", author),
                    marketplace_version=data.get("version", "1.0.0"),
                )
                session.add(skill)
                action = "installed"

            await session.commit()

        if content:
            self.registry.register_prompt(content, f"skill:{skill_name}")

        ext_id = data.get("id", slug)
        await self.client.report_download(ext_id)

        logger.info("Marketplace skill %s: %s/%s", action, author, slug)
        return {
            "action": action,
            "name": skill_name,
            "slug": slug,
            "author": data.get("author", author),
            "version": data.get("version", "1.0.0"),
            "has_bundle": has_bundle,
        }

    async def install_plugin(self, slug: str, author: str = "") -> dict[str, Any]:
        """
        Install a plugin from the marketplace:
        - If bundle available: download zip and extract to plugins/local/<slug>/
        - If no bundle: pip install the package
        Both require restart to take effect.
        """
        data = await self.client.get_plugin(slug, author=author)
        bundle_url = data.get("bundleUrl")
        package_name = data.get("packageName")

        if bundle_url:
            dest = self.plugins_local_dir / slug
            zip_path = self.bundles_dir / "plugins" / slug / "bundle.zip"
            await self.client.download_bundle(bundle_url, zip_path)

            remote_hash = data.get("bundleHash", "")
            if remote_hash:
                local_hash = _compute_hash(zip_path.read_bytes())
                if local_hash != remote_hash:
                    logger.warning("Bundle hash mismatch for plugin %s", slug)

            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(dest)

            ext_id = data.get("id", slug)
            await self.client.report_download(ext_id)

            logger.info("Plugin bundle installed to %s (restart required)", dest)
            return {
                "action": "installed",
                "method": "bundle",
                "slug": slug,
                "author": data.get("author", author),
                "version": data.get("version", "1.0.0"),
                "install_path": str(dest),
                "restart_required": True,
            }

        if not package_name:
            raise ValueError(f"Plugin {slug} has no bundle or packageName defined")

        logger.info("Installing plugin package: %s", package_name)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.error("pip install failed: %s", result.stderr)
            raise RuntimeError(f"pip install {package_name} failed: {result.stderr}")

        ext_id = data.get("id", slug)
        await self.client.report_download(ext_id)

        logger.info("Plugin installed via pip: %s (restart required)", package_name)
        return {
            "action": "installed",
            "method": "pip",
            "packageName": package_name,
            "slug": slug,
            "author": data.get("author", author),
            "version": data.get("version", "1.0.0"),
            "restart_required": True,
        }

    async def uninstall_skill(self, slug: str) -> dict[str, Any]:
        """Remove a marketplace-installed skill."""
        async with self.session_factory() as session:
            session: AsyncSession
            result = await session.execute(
                select(Skill).where(
                    Skill.scope == "marketplace",
                    Skill.marketplace_slug == slug,
                )
            )
            skill = result.scalar_one_or_none()

            if not skill:
                raise ValueError(f"Marketplace skill '{slug}' not found")

            skill_name = skill.name
            self.registry.unregister_prompt(f"skill:{skill_name}")

            await session.execute(
                delete(Skill).where(Skill.id == skill.id)
            )
            await session.commit()

        bundle_dir = self.bundles_dir / "skills" / slug
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir, ignore_errors=True)

        logger.info("Marketplace skill uninstalled: %s", slug)
        return {"action": "uninstalled", "slug": slug, "name": skill_name}

    async def uninstall_plugin(self, slug: str) -> dict[str, Any]:
        """Remove a marketplace-installed plugin bundle."""
        plugin_dir = self.plugins_local_dir / slug
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir, ignore_errors=True)
            logger.info("Plugin bundle removed: %s (restart required)", slug)
        bundle_dir = self.bundles_dir / "plugins" / slug
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir, ignore_errors=True)
        return {"action": "uninstalled", "slug": slug, "restart_required": True}

    async def list_installed(self) -> list[dict[str, Any]]:
        """List all marketplace-installed skills + local plugin bundles."""
        items: list[dict[str, Any]] = []

        async with self.session_factory() as session:
            session: AsyncSession
            result = await session.execute(
                select(Skill).where(Skill.scope == "marketplace")
            )
            skills = result.scalars().all()

        for s in skills:
            items.append({
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "slug": s.marketplace_slug,
                "author": s.marketplace_author,
                "version": s.marketplace_version,
                "skill_type": s.skill_type,
                "enabled": s.enabled,
                "scope": "marketplace",
                "type": "skill",
            })

        if self.plugins_local_dir.exists():
            for d in self.plugins_local_dir.iterdir():
                if d.is_dir():
                    items.append({
                        "name": d.name,
                        "slug": d.name,
                        "type": "plugin",
                        "method": "bundle",
                        "install_path": str(d),
                        "scope": "marketplace",
                    })

        return items

    async def check_updates(self) -> list[dict[str, Any]]:
        """Check if any installed marketplace extensions have updates."""
        installed = await self.list_installed()
        updates = []

        for item in installed:
            slug = item.get("slug", "")
            if not slug:
                continue
            try:
                if item.get("type") == "plugin":
                    remote = await self.client.get_plugin(slug, author=item.get("author", ""))
                else:
                    remote = await self.client.get_skill(slug, author=item.get("author", ""))

                remote_version = remote.get("version", "")
                local_version = item.get("version", "")
                remote_hash = remote.get("bundleHash", "")

                needs_update = False
                if remote_version and remote_version != local_version:
                    needs_update = True
                elif remote_hash:
                    local_hash = self._get_local_hash(item)
                    if local_hash and local_hash != remote_hash:
                        needs_update = True

                if needs_update:
                    updates.append({
                        "slug": slug,
                        "name": item.get("name", slug),
                        "type": item.get("type", "skill"),
                        "local_version": local_version,
                        "remote_version": remote_version,
                        "hash_changed": remote_hash and self._get_local_hash(item) != remote_hash,
                    })
            except Exception:
                logger.debug("Failed to check update for %s", slug, exc_info=True)

        return updates

    def _get_local_hash(self, item: dict[str, Any]) -> str:
        """Get the local bundle hash for comparison."""
        slug = item.get("slug", "")
        ext_type = item.get("type", "skill")
        bundle_zip = self.bundles_dir / f"{ext_type}s" / slug / "bundle.zip"
        if bundle_zip.exists():
            return _compute_hash(bundle_zip.read_bytes())
        return ""


def _find_file(directory: Path, name: str) -> Path | None:
    """Recursively find a file by name (case-insensitive)."""
    lower = name.lower()
    for p in directory.rglob("*"):
        if p.is_file() and p.name.lower() == lower:
            return p
    return None
