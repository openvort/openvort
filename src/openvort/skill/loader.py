"""
Skill 加载器

扫描内置 Skill 和用户 workspace Skill，解析 frontmatter，注册到 PluginRegistry。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from openvort.config.settings import get_settings
from openvort.plugin.registry import PluginRegistry
from openvort.utils.logging import get_logger

log = get_logger("skill.loader")

# frontmatter 解析正则：匹配 --- 开头和结尾的 YAML 块
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class Skill:
    """Skill 数据模型"""

    name: str
    description: str = ""
    content: str = ""  # markdown 正文（不含 frontmatter）
    source: str = ""  # "builtin" | "workspace"
    enabled: bool = True
    path: Path = field(default_factory=lambda: Path())


def _parse_skill_file(skill_path: Path, source: str) -> Skill | None:
    """解析 SKILL.md 文件，提取 frontmatter 和正文"""
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

        # 简易 YAML 解析（避免引入 pyyaml 依赖）
        for line in frontmatter.splitlines():
            line = line.strip()
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("enabled:"):
                val = line.split(":", 1)[1].strip().lower()
                enabled = val not in ("false", "no", "0", "off")

    return Skill(
        name=name,
        description=description,
        content=content.strip(),
        source=source,
        enabled=enabled,
        path=skill_path,
    )


class SkillLoader:
    """Skill 加载器"""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry
        self._skills: dict[str, Skill] = {}

    def load_all(self) -> None:
        """加载所有 Skill（内置 + workspace）"""
        self._load_builtin_skills()
        self._load_workspace_skills()

        # 将 enabled 的 skill 注册为 prompt
        enabled_count = 0
        for skill in self._skills.values():
            if skill.enabled and skill.content:
                self.registry.register_prompt(skill.content)
                enabled_count += 1

        log.info(
            f"已加载 {len(self._skills)} 个 Skill"
            f"（{enabled_count} 个启用）"
        )

    def get_skills(self) -> list[Skill]:
        """返回所有已加载的 Skill"""
        return list(self._skills.values())

    def get_skill(self, name: str) -> Skill | None:
        """获取指定 Skill"""
        return self._skills.get(name)

    def enable_skill(self, name: str) -> bool:
        """启用 Skill（修改 frontmatter）"""
        return self._set_skill_enabled(name, True)

    def disable_skill(self, name: str) -> bool:
        """禁用 Skill（修改 frontmatter）"""
        return self._set_skill_enabled(name, False)

    def create_skill(self, name: str) -> Path | None:
        """在 workspace 创建新 Skill 模板"""
        skills_dir = get_settings().data_dir / "workspace" / "skills"
        skill_dir = skills_dir / name
        if skill_dir.exists():
            log.warning(f"Skill '{name}' 已存在: {skill_dir}")
            return None

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            f"---\nname: {name}\ndescription: \nenabled: true\n---\n\n# {name}\n\n在此编写 Skill 内容...\n",
            encoding="utf-8",
        )
        log.info(f"已创建 Skill 模板: {skill_file}")
        return skill_file

    def _load_builtin_skills(self) -> None:
        """扫描 src/openvort/skills/*/SKILL.md"""
        builtin_dir = Path(__file__).parent.parent / "skills"
        self._scan_skills_dir(builtin_dir, "builtin")

    def _load_workspace_skills(self) -> None:
        """扫描 ~/.openvort/workspace/skills/*/SKILL.md"""
        workspace_dir = get_settings().data_dir / "workspace" / "skills"
        self._scan_skills_dir(workspace_dir, "workspace")

    def _scan_skills_dir(self, base_dir: Path, source: str) -> None:
        """扫描指定目录下的 Skill"""
        if not base_dir.exists():
            return

        for skill_dir in sorted(base_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            skill = _parse_skill_file(skill_file, source)
            if skill:
                if skill.name in self._skills:
                    log.warning(
                        f"Skill '{skill.name}' 重复"
                        f"（{self._skills[skill.name].source} vs {source}），"
                        f"workspace 覆盖 builtin"
                    )
                    if source != "workspace":
                        continue
                self._skills[skill.name] = skill
                log.info(f"已加载 Skill: {skill.name} ({source})")

    def _set_skill_enabled(self, name: str, enabled: bool) -> bool:
        """修改 Skill 的 enabled 状态（回写 frontmatter）"""
        skill = self._skills.get(name)
        if not skill:
            return False

        try:
            raw = skill.path.read_text(encoding="utf-8")
        except Exception:
            return False

        match = _FRONTMATTER_RE.match(raw)
        if not match:
            # 没有 frontmatter，添加一个
            new_raw = f"---\nname: {name}\nenabled: {str(enabled).lower()}\n---\n\n{raw}"
        else:
            frontmatter = match.group(1)
            body = raw[match.end():]

            # 替换或添加 enabled 字段
            lines = frontmatter.splitlines()
            found = False
            for i, line in enumerate(lines):
                if line.strip().startswith("enabled:"):
                    lines[i] = f"enabled: {str(enabled).lower()}"
                    found = True
                    break
            if not found:
                lines.append(f"enabled: {str(enabled).lower()}")

            new_raw = "---\n" + "\n".join(lines) + "\n---\n\n" + body

        try:
            skill.path.write_text(new_raw, encoding="utf-8")
            skill.enabled = enabled
            return True
        except Exception as e:
            log.error(f"写入 Skill 文件失败 {skill.path}: {e}")
            return False
