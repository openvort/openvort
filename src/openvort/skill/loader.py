"""
Skill 加载器

DB 驱动的三级 Skill 体系（builtin / public / personal）。
启动时扫描多目录同步到 DB，运行时全部通过 DB 读写。

支持目录：
- 内置目录 (skills/) - builtin scope
- 用户目录 (~/.openvort/skills/) - personal scope
- 企业目录 (/etc/openvort/skills/) - public scope

辅助脚本：
- Skill 文件夹内可包含任意辅助文件（脚本、配置等）
- 在 SKILL.md 中使用 {baseDir} 引用 Skill 文件夹路径
- 支持 requires 声明依赖（bins / env / packages / plugins）
"""

import json as _json_mod
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from openvort.plugin.registry import PluginRegistry
from openvort.skill.directories import SkillDirectoryManager
from openvort.utils.logging import get_logger

log = get_logger("skill.loader")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Skill name -> skill_type mapping for builtin skills
BUILTIN_SKILL_TYPES: dict[str, str] = {
    "developer": "role",
    "pm": "role",
    "qa": "role",
    "designer": "role",
    "assistant": "role",
    "code-review": "workflow",
    "daily-report": "workflow",
}

# skill_type -> tag label mapping (for migration from fixed categories to tags)
SKILL_TYPE_TO_TAG: dict[str, str] = {
    "role": "角色人设",
    "workflow": "工作流程",
    "knowledge": "知识库",
    "template": "输出模板",
    "guideline": "规范准则",
    "report": "输出模板",
    "system": "规范准则",
}

# Builtin skill name -> default tags
BUILTIN_SKILL_TAGS: dict[str, list[str]] = {
    "developer": ["角色人设"],
    "pm": ["角色人设"],
    "qa": ["角色人设"],
    "designer": ["角色人设"],
    "assistant": ["角色人设"],
    "code-review": ["工作流程", "规范准则"],
    "daily-report": ["工作流程", "输出模板"],
}

# 默认岗位-技能映射配置
DEFAULT_POST_SKILLS = {
    "developer": [
        {"skill_name": "developer", "priority": 1},
        {"skill_name": "code-review", "priority": 2},
    ],
    "pm": [
        {"skill_name": "pm", "priority": 1},
        {"skill_name": "daily-report", "priority": 2},
    ],
    "qa": [
        {"skill_name": "qa", "priority": 1},
    ],
    "designer": [
        {"skill_name": "designer", "priority": 1},
    ],
    "assistant": [
        {"skill_name": "assistant", "priority": 1},
    ],
}

# 保留旧名称的别名，保持向后兼容
DEFAULT_ROLE_SKILLS = DEFAULT_POST_SKILLS


@dataclass
class Skill:
    """Skill 数据模型（内存视图）"""

    id: str = ""
    name: str = ""
    description: str = ""
    content: str = ""
    scope: str = ""  # builtin / public / personal / marketplace
    owner_id: str = ""
    enabled: bool = True
    sort_order: int = 0
    path: Path = field(default_factory=lambda: Path())
    requires_bins: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)
    requires_packages: list[str] = field(default_factory=list)
    requires_plugins: list[str] = field(default_factory=list)


def _resolve_skill_base_dir(name: str, scope: str, marketplace_slug: str = "") -> Path:
    """Resolve the filesystem base directory for a skill based on its scope."""
    if scope == "builtin":
        dir_info = SkillDirectoryManager.get_directory("builtin")
        return dir_info.path / name if dir_info else Path()
    elif scope == "personal":
        dir_info = SkillDirectoryManager.get_directory("user")
        return dir_info.path / name if dir_info else Path()
    elif scope == "public":
        dir_info = SkillDirectoryManager.get_directory("organization")
        return dir_info.path / name if dir_info else Path()
    elif scope == "marketplace":
        slug = marketplace_slug or name
        return Path.home() / ".openvort" / "marketplace" / "bundles" / "skills" / slug / "files"
    return Path()


def _apply_content_template(content: str, base_dir: Path) -> str:
    """Replace {baseDir} placeholder in skill content with actual path."""
    if not content or not base_dir:
        return content
    return content.replace("{baseDir}", str(base_dir))


def _parse_yaml_list(val: str) -> list[str]:
    """Parse a YAML inline list like '[a, b, c]' into a Python list."""
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        return [s.strip().strip("\"'") for s in val[1:-1].split(",") if s.strip()]
    return [val] if val else []


def _check_skill_requirements(requires: dict[str, list[str]]) -> tuple[bool, list[str]]:
    """Check if skill requirements are satisfied. Returns (satisfied, missing_items)."""
    missing: list[str] = []

    for bin_name in requires.get("bins", []):
        if not shutil.which(bin_name):
            missing.append(f"bin:{bin_name}")

    for env_name in requires.get("env", []):
        if not os.environ.get(env_name):
            missing.append(f"env:{env_name}")

    return len(missing) == 0, missing


def _parse_skill_file(skill_path: Path) -> dict | None:
    """Parse SKILL.md, return dict with name/description/content/requires."""
    try:
        raw = skill_path.read_text(encoding="utf-8")
    except Exception as e:
        log.warning(f"读取 Skill 文件失败 {skill_path}: {e}")
        return None

    name = skill_path.parent.name
    description = ""
    enabled = True
    content = raw
    requires: dict[str, list[str]] = {}

    match = _FRONTMATTER_RE.match(raw)
    if match:
        frontmatter = match.group(1)
        content = raw[match.end():]
        lines = frontmatter.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("name:"):
                name = stripped.split(":", 1)[1].strip().strip("\"'")
            elif stripped.startswith("description:"):
                description = stripped.split(":", 1)[1].strip().strip("\"'")
            elif stripped.startswith("enabled:"):
                val = stripped.split(":", 1)[1].strip().lower()
                enabled = val not in ("false", "no", "0", "off")
            elif stripped.startswith("requires:"):
                i += 1
                while i < len(lines) and lines[i] and (lines[i][0] in (" ", "\t")):
                    sub = lines[i].strip()
                    if ":" in sub:
                        key, val = sub.split(":", 1)
                        requires[key.strip()] = _parse_yaml_list(val)
                    i += 1
                continue
            i += 1

    return {
        "name": name,
        "description": description,
        "content": content.strip(),
        "enabled": enabled,
        "requires": requires,
    }


class SkillLoader:
    """DB-driven Skill loader with builtin file sync."""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._migration_done = False

    async def load_all(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Sync builtin/user/organization files to DB, then register enabled global skills."""
        self._session_factory = session_factory

        # 启动时自动迁移数据库结构
        if not self._migration_done:
            await self._migrate_schema()
            self._migration_done = True

        # 同步各目录到 DB
        await self._sync_builtin_to_db()
        await self._sync_user_to_db()
        await self._sync_organization_to_db()
        await self._sync_role_skills_to_db()
        await self._sync_posts_to_db()

        async with session_factory() as db:
            from openvort.db.models import Skill as SkillModel
            result = await db.execute(
                select(SkillModel).where(
                    SkillModel.scope.in_(["builtin", "public", "marketplace"]),
                    SkillModel.enabled == True,  # noqa: E712
                )
            )
            rows = result.scalars().all()

        enabled_count = 0
        skipped_count = 0
        for row in rows:
            if not row.content:
                continue

            requires = _json_mod.loads(row.requires_json) if getattr(row, "requires_json", None) else {}
            if requires:
                satisfied, missing = _check_skill_requirements(requires)
                if not satisfied:
                    log.warning(f"Skill '{row.name}' 缺少依赖: {', '.join(missing)}，跳过")
                    skipped_count += 1
                    continue

            base_dir = _resolve_skill_base_dir(row.name, row.scope, getattr(row, "marketplace_slug", ""))
            content = _apply_content_template(row.content, base_dir)
            self.registry.register_prompt(content, source=f"skill:{row.name}")
            enabled_count += 1

        msg = f"已加载 {enabled_count} 个全局 Skill"
        if skipped_count:
            msg += f"（{skipped_count} 个因缺少依赖跳过）"
        log.info(msg)

        from openvort.skill.tools import SkillUseTool
        self.registry.register_tool(SkillUseTool())

    async def _migrate_schema(self) -> None:
        """自动迁移数据库结构"""
        from sqlalchemy import text

        async with self._session_factory() as db:
            # 1. skills 表添加 skill_type 字段
            try:
                await db.execute(text(
                    "ALTER TABLE skills ADD COLUMN IF NOT EXISTS skill_type VARCHAR(16) DEFAULT 'workflow'"
                ))
                await db.commit()
                log.info("Migration: added skills.skill_type")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration skill_type: {e}")

            # 2. member_skills 表添加 source 字段
            try:
                await db.execute(text(
                    "ALTER TABLE member_skills ADD COLUMN IF NOT EXISTS source VARCHAR(32) DEFAULT 'personal'"
                ))
                await db.commit()
                log.info("Migration: added member_skills.source")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration source: {e}")

            # 3. member_skills 表添加 custom_content 字段
            try:
                await db.execute(text(
                    "ALTER TABLE member_skills ADD COLUMN IF NOT EXISTS custom_content TEXT DEFAULT ''"
                ))
                await db.commit()
                log.info("Migration: added member_skills.custom_content")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration custom_content: {e}")

            # 4. 创建 role_skills 表
            try:
                await db.execute(text("""
                    CREATE TABLE IF NOT EXISTS role_skills (
                        id SERIAL PRIMARY KEY,
                        role VARCHAR(32) NOT NULL,
                        post VARCHAR(32) DEFAULT NULL,
                        skill_id VARCHAR(32) NOT NULL,
                        priority INTEGER DEFAULT 0
                    )
                """))
                await db.commit()
                log.info("Migration: created role_skills table")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration role_skills: {e}")

            # 5. 创建索引
            try:
                await db.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_role_skills_role ON role_skills(role)"
                ))
                await db.commit()
                log.info("Migration: created role_skills index")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration index: {e}")

            # 5.1 添加 role_skills.post 字段
            try:
                await db.execute(text(
                    "ALTER TABLE role_skills ADD COLUMN IF NOT EXISTS post VARCHAR(32) DEFAULT NULL"
                ))
                await db.commit()
                log.info("Migration: added role_skills.post")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration role_skills.post: {e}")

            # 5.2 添加 schedule_jobs.target_member_id 字段
            try:
                await db.execute(text(
                    "ALTER TABLE schedule_jobs ADD COLUMN IF NOT EXISTS target_member_id VARCHAR(32) DEFAULT NULL"
                ))
                await db.commit()
                log.info("Migration: added schedule_jobs.target_member_id")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration schedule_jobs.target_member_id: {e}")

            # 6. 更新已有 builtin skill 的 skill_type
            role_names = ", ".join(f"'{n}'" for n in BUILTIN_SKILL_TYPES if BUILTIN_SKILL_TYPES[n] == "role")
            try:
                await db.execute(text(
                    f"UPDATE skills SET skill_type = 'role' WHERE scope = 'builtin' AND name IN ({role_names}) AND skill_type != 'role'"
                ))
                await db.commit()
                log.info("Migration: updated builtin skill types")
            except Exception as e:
                await db.rollback()
                log.warning(f"Migration update skill_type: {e}")

            # 7. 创建 virtual_roles 表
            try:
                await db.execute(text("""
                    CREATE TABLE IF NOT EXISTS virtual_roles (
                        id VARCHAR(32) PRIMARY KEY,
                        key VARCHAR(32) UNIQUE NOT NULL,
                        name VARCHAR(64) NOT NULL,
                        description VARCHAR(256) DEFAULT '',
                        icon VARCHAR(32) DEFAULT '',
                        default_persona TEXT DEFAULT '',
                        default_auto_report BOOLEAN DEFAULT FALSE,
                        default_report_frequency VARCHAR(16) DEFAULT 'daily',
                        enabled BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                await db.commit()
                log.info("Migration: created virtual_roles table")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration virtual_roles: {e}")

            # 8. 创建索引
            try:
                await db.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_virtual_roles_key ON virtual_roles(key)"
                ))
                await db.commit()
                log.info("Migration: created virtual_roles index")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration virtual_roles index: {e}")

            # 9. members 表添加 avatar_source 字段（头像来源优先级）
            try:
                await db.execute(text(
                    "ALTER TABLE members ADD COLUMN IF NOT EXISTS avatar_source VARCHAR(16) DEFAULT ''"
                ))
                await db.commit()
                log.info("Migration: added members.avatar_source")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration members.avatar_source: {e}")

            # 10. skills 表添加 tags 字段，并从 skill_type 自动迁移
            try:
                await db.execute(text(
                    "ALTER TABLE skills ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT ''"
                ))
                await db.commit()
                log.info("Migration: added skills.tags")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration skills.tags: {e}")

            # 10.1 迁移已有 skill_type 到 tags（仅空 tags 的行）
            try:
                import json as _json
                result = await db.execute(text(
                    "SELECT id, skill_type FROM skills WHERE tags IS NULL OR tags = '' OR tags = '[]'"
                ))
                rows = result.fetchall()
                for row in rows:
                    tag = SKILL_TYPE_TO_TAG.get(row[1], row[1])
                    if tag:
                        await db.execute(text(
                            "UPDATE skills SET tags = :tags WHERE id = :id"
                        ), {"tags": _json.dumps([tag], ensure_ascii=False), "id": row[0]})
                await db.commit()
                if rows:
                    log.info(f"Migration: migrated {len(rows)} skills from skill_type to tags")
            except Exception as e:
                await db.rollback()
                log.warning(f"Migration skill_type->tags: {e}")

            # 11. skills 表添加 marketplace 相关字段
            for col, col_type in [
                ("marketplace_slug", "VARCHAR(128) DEFAULT ''"),
                ("marketplace_author", "VARCHAR(128) DEFAULT ''"),
                ("marketplace_version", "VARCHAR(32) DEFAULT ''"),
            ]:
                try:
                    await db.execute(text(
                        f"ALTER TABLE skills ADD COLUMN IF NOT EXISTS {col} {col_type}"
                    ))
                    await db.commit()
                    log.info(f"Migration: added skills.{col}")
                except Exception as e:
                    await db.rollback()
                    if "already exists" not in str(e).lower():
                        log.warning(f"Migration skills.{col}: {e}")

            try:
                await db.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_skills_marketplace_slug ON skills(marketplace_slug)"
                ))
                await db.commit()
                log.info("Migration: created skills marketplace_slug index")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration marketplace_slug index: {e}")

            # 12. skills 表添加 requires_json 字段（依赖声明）
            try:
                await db.execute(text(
                    "ALTER TABLE skills ADD COLUMN IF NOT EXISTS requires_json TEXT DEFAULT ''"
                ))
                await db.commit()
                log.info("Migration: added skills.requires_json")
            except Exception as e:
                await db.rollback()
                if "already exists" not in str(e).lower():
                    log.warning(f"Migration skills.requires_json: {e}")

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
                if not parsed or not parsed["enabled"] or not parsed["content"]:
                    continue

                requires = parsed.get("requires", {})
                if requires:
                    satisfied, missing = _check_skill_requirements(requires)
                    if not satisfied:
                        log.warning(f"Skill '{parsed['name']}' 缺少依赖: {', '.join(missing)}，跳过")
                        continue

                content = _apply_content_template(parsed["content"], skill_dir)
                self.registry.register_prompt(content, source=f"skill:{parsed['name']}")
                count += 1
        log.info(f"已加载 {count} 个内置 Skill（同步模式）")

    async def _sync_builtin_to_db(self) -> None:
        """Scan builtin SKILL.md files and upsert into DB."""
        from openvort.db.models import Skill as SkillModel

        builtin_dir = SkillDirectoryManager.get_directory("builtin")
        if not builtin_dir or not builtin_dir.path.exists():
            return

        await self._sync_directory_to_db(builtin_dir.path, "builtin", SkillDirectoryManager.get_directory("builtin").key)

    async def _sync_user_to_db(self) -> None:
        """Scan user SKILL.md files and upsert into DB."""
        from openvort.db.models import Skill as SkillModel

        user_dir = SkillDirectoryManager.get_directory("user")
        if not user_dir or not user_dir.path.exists():
            return

        await self._sync_directory_to_db(user_dir.path, "personal", user_dir.key)

    async def _sync_organization_to_db(self) -> None:
        """Scan organization SKILL.md files and upsert into DB."""
        from openvort.db.models import Skill as SkillModel

        org_dir = SkillDirectoryManager.get_directory("organization")
        if not org_dir or not org_dir.enabled or not org_dir.path.exists():
            return

        await self._sync_directory_to_db(org_dir.path, "public", org_dir.key)

    async def _sync_directory_to_db(self, directory: Path, scope: str, dir_key: str) -> None:
        """Scan a directory for SKILL.md files and sync to DB."""
        from openvort.db.models import Skill as SkillModel

        file_skills: dict[str, dict] = {}
        if not directory.exists():
            return

        for skill_dir in sorted(directory.iterdir()):
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

        import json as _json

        async with self._session_factory() as db:
            result = await db.execute(
                select(SkillModel).where(SkillModel.scope == scope)
            )
            existing = {row.name: row for row in result.scalars().all()}

            for name, data in file_skills.items():
                stype = BUILTIN_SKILL_TYPES.get(name, "workflow")
                default_tags = BUILTIN_SKILL_TAGS.get(name) or [SKILL_TYPE_TO_TAG.get(stype, stype)]
                requires = data.get("requires", {})
                requires_str = _json.dumps(requires, ensure_ascii=False) if requires else ""

                if name in existing:
                    row = existing[name]
                    row.description = data["description"]
                    row.content = data["content"]
                    row.skill_type = stype
                    if requires_str:
                        row.requires_json = requires_str
                    if not row.tags or row.tags in ("", "[]"):
                        row.tags = _json.dumps(default_tags, ensure_ascii=False)
                else:
                    db.add(SkillModel(
                        id=uuid.uuid4().hex,
                        name=name,
                        description=data["description"],
                        content=data["content"],
                        scope=scope,
                        skill_type=stype,
                        tags=_json.dumps(default_tags, ensure_ascii=False),
                        requires_json=requires_str,
                        enabled=data["enabled"],
                    ))

            # Remove DB entries that no longer exist on disk (only for non-builtin)
            if scope != "builtin":
                for name, row in existing.items():
                    if name not in file_skills:
                        await db.delete(row)

            await db.commit()
        log.info(f"已同步 {dir_key} 目录 {len(file_skills)} 个 Skills 到 DB (scope={scope})")

    async def _sync_role_skills_to_db(self) -> None:
        """同步岗位-技能映射到数据库"""
        from openvort.db.models import PostSkill as PostSkillModel, Skill as SkillModel

        async with self._session_factory() as db:
            # 获取所有已存在的映射（使用 role 字段）
            result = await db.execute(select(PostSkillModel))
            existing = {(row.role, row.skill_id): row for row in result.scalars().all()}

            # 遍历默认配置，创建映射
            for post, skill_configs in DEFAULT_POST_SKILLS.items():
                for config in skill_configs:
                    skill_name = config["skill_name"]
                    priority = config["priority"]

                    # 查找对应的 Skill
                    result = await db.execute(
                        select(SkillModel).where(SkillModel.name == skill_name)
                    )
                    skill = result.scalar_one_or_none()
                    if not skill:
                        continue

                    key = (post, skill.id)
                    if key not in existing:
                        db.add(PostSkillModel(
                            role=post,  # 数据库使用 role 列
                            post=post,  # 保留 post 字段
                            skill_id=skill.id,
                            priority=priority,
                        ))

            await db.commit()
        log.info("岗位-技能映射已同步")

    # 保留旧方法名，保持向后兼容
    async def _sync_posts_to_db(self) -> None:
        """同步岗位元数据到数据库"""
        from openvort.db.models import Post as PostModel

        # 默认岗位配置
        DEFAULT_POSTS = [
            {
                "key": "developer",
                "name": "开发工程师",
                "description": "代码、Git、Debug 专家",
                "icon": "",
                "default_persona": "你是一位经验丰富的开发工程师，擅长代码编写、调试和优化。",
                "default_auto_report": False,
                "default_report_frequency": "daily",
            },
            {
                "key": "pm",
                "name": "产品经理",
                "description": "需求、任务、需求评审",
                "icon": "",
                "default_persona": "你是一位专业的产品经理，擅长需求分析、产品规划和团队协作。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
            {
                "key": "qa",
                "name": "测试工程师",
                "description": "用例、测试、质量把控",
                "icon": "",
                "default_persona": "你是一位细致的测试工程师，擅长用例设计、缺陷追踪和质量把控。",
                "default_auto_report": False,
                "default_report_frequency": "daily",
            },
            {
                "key": "designer",
                "name": "设计师",
                "description": "UI/UX、设计稿规范",
                "icon": "",
                "default_persona": "你是一位创意的设计师，擅长 UI/UX 设计和用户体验优化。",
                "default_auto_report": False,
                "default_report_frequency": "weekly",
            },
            {
                "key": "assistant",
                "name": "通用助手",
                "description": "处理日常事务的 AI 助手",
                "icon": "",
                "default_persona": "你是一位乐于助人的 AI 助手，擅长回答问题、提供建议和协助完成各种任务。",
                "default_auto_report": False,
                "default_report_frequency": "daily",
            },
            {
                "key": "operations",
                "name": "运营专员",
                "description": "内容运营、用户运营、活动策划",
                "icon": "",
                "default_persona": "你是一位专业的运营专员，擅长内容策划、用户增长和活动运营。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
            {
                "key": "marketing",
                "name": "市场营销",
                "description": "品牌推广、市场分析、营销策划",
                "icon": "",
                "default_persona": "你是一位资深的市场营销专家，擅长品牌建设、市场推广和营销策略制定。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
            {
                "key": "sales",
                "name": "销售代表",
                "description": "客户开发、需求挖掘、商务谈判",
                "icon": "",
                "default_persona": "你是一位专业的销售代表，擅长客户开发、需求挖掘和商务谈判。",
                "default_auto_report": True,
                "default_report_frequency": "daily",
            },
            {
                "key": "customer_service",
                "name": "客服专员",
                "description": "咨询解答、问题处理、用户反馈",
                "icon": "",
                "default_persona": "你是一位耐心的客服专员，擅长解答咨询、处理问题和收集用户反馈。",
                "default_auto_report": True,
                "default_report_frequency": "daily",
            },
            {
                "key": "hr",
                "name": "人力资源",
                "description": "招聘、培训、员工关系",
                "icon": "",
                "default_persona": "你是一位专业的人力资源专员，擅长招聘选拔、培训发展和员工关系维护。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
            {
                "key": "finance",
                "name": "财务专员",
                "description": "账务处理、预算管理、报表分析",
                "icon": "",
                "default_persona": "你是一位严谨的财务专员，擅长账务处理、预算管理和财务分析。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
            {
                "key": "legal",
                "name": "法务专员",
                "description": "合同审核、法律咨询、风险防控",
                "icon": "",
                "default_persona": "你是一位专业的法务专员，擅长合同审核、法律咨询和风险防控。",
                "default_auto_report": False,
                "default_report_frequency": "weekly",
            },
            {
                "key": "data_analyst",
                "name": "数据分析师",
                "description": "数据分析、报表可视化、洞察发现",
                "icon": "",
                "default_persona": "你是一位专业的数据分析师，擅长数据挖掘、趋势分析和可视化呈现。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
            {
                "key": "architect",
                "name": "架构师",
                "description": "系统设计、技术规划、架构评审",
                "icon": "",
                "default_persona": "你是一位资深的架构师，擅长系统设计、技术规划和架构优化。",
                "default_auto_report": False,
                "default_report_frequency": "weekly",
            },
            {
                "key": "devops",
                "name": "运维工程师",
                "description": "系统运维、自动化部署、监控告警",
                "icon": "",
                "default_persona": "你是一位专业的运维工程师，擅长系统运维、自动化和性能优化。",
                "default_auto_report": False,
                "default_report_frequency": "daily",
            },
            {
                "key": "security",
                "name": "安全工程师",
                "description": "安全防护、漏洞扫描、风险评估",
                "icon": "",
                "default_persona": "你是一位专业的安全工程师，擅长安全防护、漏洞扫描和风险评估。",
                "default_auto_report": False,
                "default_report_frequency": "weekly",
            },
            {
                "key": "editor",
                "name": "内容编辑",
                "description": "内容创作、文案撰写、稿件审核",
                "icon": "",
                "default_persona": "你是一位优秀的内容编辑，擅长文案创作、内容策划和编辑审核。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
            {
                "key": "business_dev",
                "name": "商务拓展",
                "description": "合作伙伴开拓、资源对接、商务合作",
                "icon": "",
                "default_persona": "你是一位专业的商务拓展专家，擅长合作伙伴开发和商务谈判。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
            {
                "key": "product_ops",
                "name": "产品运营",
                "description": "产品优化、数据分析、用户研究",
                "icon": "",
                "default_persona": "你是一位专业的产品运营专员，擅长产品优化、数据分析和用户研究。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
            {
                "key": "project_manager",
                "name": "项目经理",
                "description": "项目规划、进度管理、风险控制",
                "icon": "",
                "default_persona": "你是一位资深的项目经理，擅长项目规划、进度管理和团队协调。",
                "default_auto_report": True,
                "default_report_frequency": "weekly",
            },
        ]

        async with self._session_factory() as db:
            # 获取所有已存在的岗位
            result = await db.execute(select(PostModel))
            existing = {row.key: row for row in result.scalars().all()}

            for config in DEFAULT_POSTS:
                if config["key"] in existing:
                    # 更新已有岗位
                    row = existing[config["key"]]
                    row.name = config["name"]
                    row.description = config["description"]
                    row.icon = config["icon"]
                    row.default_persona = config["default_persona"]
                    row.default_auto_report = config["default_auto_report"]
                    row.default_report_frequency = config["default_report_frequency"]
                else:
                    # 创建新岗位
                    db.add(PostModel(
                        id=uuid.uuid4().hex,
                        key=config["key"],
                        name=config["name"],
                        description=config["description"],
                        icon=config["icon"],
                        default_persona=config["default_persona"],
                        default_auto_report=config["default_auto_report"],
                        default_report_frequency=config["default_report_frequency"],
                    ))

            await db.commit()
        log.info("岗位元数据已同步")

    async def get_member_skills_content(self, member_id: str) -> list[str]:
        """Return content list of ALL member skills: role-based + subscribed + personal."""
        if not self._session_factory:
            return []

        from openvort.db.models import Skill as SkillModel, MemberSkill

        seen_ids: set[str] = set()
        contents: list[str] = []

        async with self._session_factory() as db:
            # 1. Role-based skills (MemberSkill with source like 'role:*')
            result = await db.execute(
                select(SkillModel, MemberSkill).join(
                    MemberSkill, MemberSkill.skill_id == SkillModel.id
                ).where(
                    MemberSkill.member_id == member_id,
                    MemberSkill.enabled == True,  # noqa: E712
                    MemberSkill.source.like("role:%"),
                    SkillModel.enabled == True,  # noqa: E712
                ).order_by(SkillModel.sort_order)
            )
            for skill, ms in result.all():
                content = ms.custom_content or skill.content
                if content and skill.id not in seen_ids:
                    seen_ids.add(skill.id)
                    base_dir = _resolve_skill_base_dir(skill.name, skill.scope, getattr(skill, "marketplace_slug", ""))
                    contents.append(_apply_content_template(content, base_dir))

            # 2. Public skills: default all enabled, minus user opt-outs
            disabled_result = await db.execute(
                select(MemberSkill.skill_id).where(
                    MemberSkill.member_id == member_id,
                    MemberSkill.enabled == False,  # noqa: E712
                    ~MemberSkill.source.like("role:%"),
                )
            )
            disabled_skill_ids = {row[0] for row in disabled_result.all()}

            query = select(SkillModel).where(
                SkillModel.scope == "public",
                SkillModel.enabled == True,  # noqa: E712
            )
            if disabled_skill_ids:
                query = query.where(SkillModel.id.notin_(disabled_skill_ids))
            query = query.order_by(SkillModel.sort_order)

            result = await db.execute(query)
            for skill in result.scalars().all():
                if skill.content and skill.id not in seen_ids:
                    seen_ids.add(skill.id)
                    base_dir = _resolve_skill_base_dir(skill.name, skill.scope, getattr(skill, "marketplace_slug", ""))
                    contents.append(_apply_content_template(skill.content, base_dir))

            # 3. Personal skills (scope=personal, owner_id=member_id)
            result = await db.execute(
                select(SkillModel).where(
                    SkillModel.scope == "personal",
                    SkillModel.owner_id == member_id,
                    SkillModel.enabled == True,  # noqa: E712
                ).order_by(SkillModel.sort_order)
            )
            for r in result.scalars().all():
                if r.content and r.id not in seen_ids:
                    seen_ids.add(r.id)
                    base_dir = _resolve_skill_base_dir(r.name, r.scope, getattr(r, "marketplace_slug", ""))
                    contents.append(_apply_content_template(r.content, base_dir))

        return contents

    async def get_member_skills_with_source(self, member_id: str) -> list[dict]:
        """获取成员技能列表（含来源信息）"""
        if not self._session_factory:
            return []

        from openvort.db.models import Skill as SkillModel, MemberSkill

        async with self._session_factory() as db:
            # 查询成员订阅的技能（含 MemberSkill 信息）
            result = await db.execute(
                select(SkillModel, MemberSkill).join(
                    MemberSkill, MemberSkill.skill_id == SkillModel.id
                ).where(
                    MemberSkill.member_id == member_id,
                )
            )
            rows = result.all()

            skills = []
            for skill, member_skill in rows:
                skills.append({
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "content": member_skill.custom_content or skill.content,
                    "scope": skill.scope,
                    "skill_type": skill.skill_type,
                    "source": member_skill.source,
                    "enabled": member_skill.enabled,
                })

            # 也返回 personal 技能
            result = await db.execute(
                select(SkillModel).where(
                    SkillModel.scope == "personal",
                    SkillModel.owner_id == member_id,
                    SkillModel.enabled == True,  # noqa: E712
                )
            )
            for skill in result.scalars().all():
                skills.append({
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "content": skill.content,
                    "scope": skill.scope,
                    "skill_type": skill.skill_type,
                    "source": "personal",
                    "enabled": skill.enabled,
                })

        return skills

    async def get_role_skills(self, role: str) -> list[dict]:
        """获取角色对应的推荐技能"""
        if not self._session_factory:
            return []

        from openvort.db.models import PostSkill as RoleSkillModel, Skill as SkillModel

        async with self._session_factory() as db:
            result = await db.execute(
                select(SkillModel, RoleSkillModel).join(
                    RoleSkillModel, RoleSkillModel.skill_id == SkillModel.id
                ).where(
                    RoleSkillModel.role == role,
                ).order_by(RoleSkillModel.priority)
            )
            rows = result.all()

            skills = []
            for skill, _ in rows:
                skills.append({
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "content": skill.content,
                    "scope": skill.scope,
                    "skill_type": skill.skill_type,
                })
            return skills