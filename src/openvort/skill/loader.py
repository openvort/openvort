"""
Skill 加载器

DB 驱动的三级 Skill 体系（builtin / public / personal）。
启动时扫描内置文件同步到 DB，运行时全部通过 DB 读写。
"""

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from openvort.plugin.registry import PluginRegistry
from openvort.utils.logging import get_logger

log = get_logger("skill.loader")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class Skill:
    """Skill 数据模型（内存视图）"""

    id: str = ""
    name: str = ""
    description: str = ""
    content: str = ""
    scope: str = ""  # builtin / public / personal
    owner_id: str = ""
    enabled: bool = True
    sort_order: int = 0
    path: Path = field(default_factory=lambda: Path())


def _parse_skill_file(skill_path: Path) -> dict | None:
    """Parse SKILL.md, return dict with name/description/content."""
    try:
        raw = skill_path.read_text(encoding="utf-8")
    except Exception as e:
        log.warning(f"读取 Skill 文件失败 {skill_path}: {e}")
        return None

    name = skill_path.parent.name
    description = ""
    enabled = True
    content = raw

    match = _FRONTMATTER_RE.match(raw)
    if match:
        frontmatter = match.group(1)
        content = raw[match.end():]
        for line in frontmatter.splitlines():
            line = line.strip()
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("enabled:"):
                val = line.split(":", 1)[1].strip().lower()
                enabled = val not in ("false", "no", "0", "off")

    return {
        "name": name,
        "description": description,
        "content": content.strip(),
        "enabled": enabled,
    }


class SkillLoader:
    """DB-driven Skill loader with builtin file sync."""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def load_all(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Sync builtin files to DB, then register enabled global skills."""
        self._session_factory = session_factory

        await self._sync_builtin_to_db()

        async with session_factory() as db:
            from openvort.db.models import Skill as SkillModel
            result = await db.execute(
                select(SkillModel).where(
                    SkillModel.scope.in_(["builtin", "public"]),
                    SkillModel.enabled == True,  # noqa: E712
                )
            )
            rows = result.scalars().all()

        enabled_count = 0
        for row in rows:
            if row.content:
                self.registry.register_prompt(row.content)
                enabled_count += 1

        log.info(f"已加载 {len(rows)} 个全局 Skill（{enabled_count} 个启用）")

    def load_all_sync(self) -> None:
        """Legacy sync loader for CLI commands without DB.
        Scans files only, registers to PluginRegistry.
        """
        builtin_dir = Path(__file__).parent.parent / "skills"
        count = 0
        if builtin_dir.exists():
            for skill_dir in sorted(builtin_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                parsed = _parse_skill_file(skill_file)
                if parsed and parsed["enabled"] and parsed["content"]:
                    self.registry.register_prompt(parsed["content"])
                    count += 1
        log.info(f"已加载 {count} 个内置 Skill（同步模式）")

    async def _sync_builtin_to_db(self) -> None:
        """Scan builtin SKILL.md files and upsert into DB."""
        from openvort.db.models import Skill as SkillModel

        builtin_dir = Path(__file__).parent.parent / "skills"
        if not builtin_dir.exists():
            return

        file_skills: dict[str, dict] = {}
        for skill_dir in sorted(builtin_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            parsed = _parse_skill_file(skill_file)
            if parsed:
                file_skills[parsed["name"]] = parsed

        if not file_skills:
            return

        async with self._session_factory() as db:
            result = await db.execute(
                select(SkillModel).where(SkillModel.scope == "builtin")
            )
            existing = {row.name: row for row in result.scalars().all()}

            for name, data in file_skills.items():
                if name in existing:
                    row = existing[name]
                    row.description = data["description"]
                    row.content = data["content"]
                else:
                    db.add(SkillModel(
                        id=uuid.uuid4().hex,
                        name=name,
                        description=data["description"],
                        content=data["content"],
                        scope="builtin",
                        enabled=data["enabled"],
                    ))

            # Remove DB builtins that no longer exist on disk
            for name, row in existing.items():
                if name not in file_skills:
                    await db.delete(row)

            await db.commit()

    async def get_member_skills_content(self, member_id: str) -> list[str]:
        """Return content list of a member's personal + subscribed public skills."""
        if not self._session_factory:
            return []

        from openvort.db.models import Skill as SkillModel, MemberSkill

        async with self._session_factory() as db:
            # Personal skills
            result = await db.execute(
                select(SkillModel).where(
                    SkillModel.scope == "personal",
                    SkillModel.owner_id == member_id,
                    SkillModel.enabled == True,  # noqa: E712
                ).order_by(SkillModel.sort_order)
            )
            personal = [r.content for r in result.scalars().all() if r.content]

            # Subscribed public skills
            result = await db.execute(
                select(SkillModel).join(
                    MemberSkill, MemberSkill.skill_id == SkillModel.id
                ).where(
                    MemberSkill.member_id == member_id,
                    MemberSkill.enabled == True,  # noqa: E712
                    SkillModel.scope == "public",
                    SkillModel.enabled == True,  # noqa: E712
                ).order_by(SkillModel.sort_order)
            )
            subscribed = [r.content for r in result.scalars().all() if r.content]

        return personal + subscribed
