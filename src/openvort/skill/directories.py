"""
Skill 目录配置

支持多目录扫描：内置目录、用户目录、企业目录。
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from openvort.utils.logging import get_logger

log = get_logger("skill.directories")


@dataclass
class SkillDirectory:
    """Skill 目录配置"""
    key: str  # builtin / user / organization
    name: str
    path: Path
    scope: str  # 对应的 scope
    description: str = ""
    enabled: bool = True
    writable: bool = False


class SkillDirectoryManager:
    """Skill 目录管理器"""

    # 默认目录配置
    DEFAULT_DIRECTORIES: list[SkillDirectory] = []

    @classmethod
    def get_default_directories(cls) -> list[SkillDirectory]:
        """获取默认目录配置"""
        if cls.DEFAULT_DIRECTORIES:
            return cls.DEFAULT_DIRECTORIES

        # 内置目录
        builtin_dir = Path(__file__).parent.parent / "skills"

        # 用户目录
        user_dir = Path.home() / ".openvort" / "skills"

        # 企业目录（可选）
        org_dir = Path("/etc/openvort/skills")

        cls.DEFAULT_DIRECTORIES = [
            SkillDirectory(
                key="builtin",
                name="内置 Skills",
                path=builtin_dir,
                scope="builtin",
                description="系统内置的 Skills",
                enabled=True,
                writable=False,
            ),
            SkillDirectory(
                key="user",
                name="用户 Skills",
                path=user_dir,
                scope="personal",
                description="用户自定义 Skills",
                enabled=True,
                writable=True,
            ),
            SkillDirectory(
                key="organization",
                name="企业 Skills",
                path=org_dir,
                scope="public",
                description="企业共享的 Skills（需管理员配置）",
                enabled=org_dir.exists(),
                writable=False,
            ),
        ]

        # 确保用户目录存在
        user_dir.mkdir(parents=True, exist_ok=True)

        return cls.DEFAULT_DIRECTORIES

    @classmethod
    def get_directory(cls, key: str) -> Optional[SkillDirectory]:
        """获取指定目录"""
        for d in cls.get_default_directories():
            if d.key == key:
                return d
        return None

    @classmethod
    def get_enabled_directories(cls) -> list[SkillDirectory]:
        """获取所有启用的目录"""
        return [d for d in cls.get_default_directories() if d.enabled]

    @classmethod
    def get_all_directories(cls) -> list[dict]:
        """获取所有目录（用于 API 返回）"""
        result = []
        for d in cls.get_default_directories():
            # 检查目录是否存在
            exists = d.path.exists() if d.enabled else False

            # 统计 Skills 数量
            skill_count = 0
            if exists and d.path.is_dir():
                skill_count = len(list(d.path.iterdir()))

            result.append({
                "key": d.key,
                "name": d.name,
                "path": str(d.path),
                "scope": d.scope,
                "description": d.description,
                "enabled": d.enabled,
                "writable": d.writable,
                "exists": exists,
                "skill_count": skill_count,
            })
        return result

    @classmethod
    def get_user_skills_dir(cls) -> Path:
        """获取用户 Skills 目录"""
        return cls.get_directory("user").path

    @classmethod
    def ensure_user_dir(cls) -> Path:
        """确保用户目录存在"""
        user_dir = cls.get_user_skills_dir()
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
