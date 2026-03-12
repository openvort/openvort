"""
Marketplace installer - installs skills/plugins from the marketplace into local OpenVort.
"""

import json
import logging
import subprocess
import sys
from typing import Any

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from openvort.db.models import Skill
from openvort.marketplace.client import MarketplaceClient
from openvort.plugin.registry import PluginRegistry

logger = logging.getLogger(__name__)


class MarketplaceInstaller:
    """Handles installing and uninstalling marketplace extensions."""

    def __init__(
        self,
        client: MarketplaceClient,
        session_factory,
        registry: PluginRegistry,
    ):
        self.client = client
        self.session_factory = session_factory
        self.registry = registry

    async def install_skill(self, slug: str, author: str = "") -> dict[str, Any]:
        """
        Install a skill from the marketplace:
        1. Fetch skill data from marketplace API
        2. Write to local DB (scope='marketplace')
        3. Register prompt to PluginRegistry (takes effect immediately)
        4. Report download
        """
        data = await self.client.get_skill(slug, author=author)
        skill_name = data.get("name", slug)

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
                existing_skill.content = data.get("content", "")
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
                    content=data.get("content", ""),
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

        content = data.get("content", "")
        if content:
            self.registry.register_prompt(content, f"skill:{skill_name}")

        await self.client.report_download(slug)

        logger.info("Marketplace skill %s: %s/%s", action, author, slug)
        return {
            "action": action,
            "name": skill_name,
            "slug": slug,
            "author": data.get("author", author),
            "version": data.get("version", "1.0.0"),
        }

    async def install_plugin(self, slug: str, author: str = "") -> dict[str, Any]:
        """
        Install a plugin from the marketplace:
        1. Fetch plugin info from marketplace API
        2. pip install the package
        3. Return info (requires restart to take effect)
        4. Report download
        """
        data = await self.client.get_plugin(slug, author=author)
        package_name = data.get("packageName")

        if not package_name:
            raise ValueError(f"Plugin {slug} has no packageName defined")

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

        await self.client.report_download(slug)

        logger.info("Plugin installed: %s (restart required)", package_name)
        return {
            "action": "installed",
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

        logger.info("Marketplace skill uninstalled: %s", slug)
        return {"action": "uninstalled", "slug": slug, "name": skill_name}

    async def list_installed(self) -> list[dict[str, Any]]:
        """List all marketplace-installed skills."""
        async with self.session_factory() as session:
            session: AsyncSession
            result = await session.execute(
                select(Skill).where(Skill.scope == "marketplace")
            )
            skills = result.scalars().all()

        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "slug": s.marketplace_slug,
                "author": s.marketplace_author,
                "version": s.marketplace_version,
                "skill_type": s.skill_type,
                "enabled": s.enabled,
                "scope": "marketplace",
            }
            for s in skills
        ]

    async def check_updates(self) -> list[dict[str, Any]]:
        """Check if any installed marketplace extensions have updates available."""
        installed = await self.list_installed()
        updates = []

        for item in installed:
            slug = item.get("slug", "")
            if not slug:
                continue
            try:
                remote = await self.client.get_skill(slug, author=item.get("author", ""))
                remote_version = remote.get("version", "")
                local_version = item.get("version", "")
                if remote_version and remote_version != local_version:
                    updates.append({
                        "slug": slug,
                        "name": item["name"],
                        "local_version": local_version,
                        "remote_version": remote_version,
                    })
            except Exception:
                logger.debug("Failed to check update for %s", slug, exc_info=True)

        return updates
