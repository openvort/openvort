"""
Skill AI 发现模块

支持 AI 分析用户消息，自动发现需要的 Skills：
1. 分析用户消息意图
2. 搜索 GitHub 上的相关 Skills
3. 返回推荐列表供用户选择
"""

import json
from typing import Optional

from openvort.skill.importer import GitHubImporter
from openvort.skill.loader import SkillLoader
from openvort.utils.logging import get_logger

log = get_logger("skill.discovery")


class SkillDiscovery:
    """AI Skill 发现与推荐"""

    def __init__(self, loader: SkillLoader):
        self.loader = loader
        self.importer = GitHubImporter()

    async def analyze_message(self, message: str, member_id: str) -> dict:
        """
        分析用户消息，判断是否需要安装新 Skill

        Args:
            message: 用户消息
            member_id: 成员 ID

        Returns:
            dict: 分析结果
            {
                "need_skill": bool,
                "keywords": list[str],
                "reason": str,
            }
        """
        # 获取已安装的 Skills
        from openvort.db.models import Skill as SkillModel
        from sqlalchemy import select

        installed_skills = []
        if self.loader._session_factory:
            async with self.loader._session_factory() as db:
                result = await db.execute(
                    select(SkillModel).where(SkillModel.enabled == True)  # noqa: E712
                )
                installed_skills = [row.name for row in result.scalars().all()]

        # 简单的关键词匹配（实际可以调用 LLM）
        keywords = self._extract_keywords(message)

        if not keywords:
            return {
                "need_skill": False,
                "keywords": [],
                "reason": "未识别到需要特定 Skill 的意图",
            }

        # 检查是否已有相关 Skill
        installed_lower = [s.lower() for s in installed_skills]
        matched = []
        for kw in keywords:
            for skill in installed_skills:
                if kw.lower() in skill.lower():
                    matched.append(skill)

        if matched:
            return {
                "need_skill": False,
                "keywords": keywords,
                "reason": f"已安装相关 Skills: {', '.join(matched)}",
            }

        return {
            "need_skill": True,
            "keywords": keywords,
            "reason": f"需要安装与 {', '.join(keywords)} 相关的 Skill",
        }

    def _extract_keywords(self, message: str) -> list[str]:
        """从消息中提取关键词"""
        import re

        message_lower = message.lower()

        # 预定义关键词映射
        keyword_map = {
            "代码评审": "code review",
            "代码审查": "code review",
            "review": "code review",
            "日报": "daily report",
            "周报": "weekly report",
            "月报": "monthly report",
            "报告": "report",
            "禅道": "zentao",
            "项目管理": "project management",
            "任务": "task",
            "bug": "bug",
            "测试": "testing",
            "git": "git",
            "仓库": "repository",
            "代码": "code",
            "前端": "frontend",
            "后端": "backend",
            "设计": "design",
            "产品": "product",
        }

        matched = []
        for chinese, english in keyword_map.items():
            if chinese in message_lower or english in message_lower:
                matched.append(english)

        return list(set(matched))

    async def search_online(self, keywords: list[str], limit: int = 5) -> list[dict]:
        """
        根据关键词搜索 GitHub 上的 Skills

        Args:
            keywords: 搜索关键词
            limit: 返回数量

        Returns:
            list: 搜索结果
        """
        all_results = []

        for kw in keywords:
            try:
                results = await self.importer.search(kw, limit=limit)
                all_results.extend(results)
            except Exception as e:
                log.warning(f"搜索关键词 '{kw}' 失败: {e}")

        # 去重
        seen = set()
        unique_results = []
        for r in all_results:
            repo = r.get("repo", "")
            if repo and repo not in seen:
                seen.add(repo)
                unique_results.append(r)

        return unique_results[:limit]

    async def discover_and_recommend(self, message: str, member_id: str) -> dict:
        """
        完整的发现+推荐流程

        Returns:
            dict: {
                "type": "none" | "recommend",
                "message": str,
                "keywords": list[str],
                "recommendations": list[dict],
            }
        """
        # 1. 分析消息
        analysis = await self.analyze_message(message, member_id)

        if not analysis.get("need_skill"):
            return {
                "type": "none",
                "message": analysis.get("reason", ""),
                "keywords": analysis.get("keywords", []),
                "recommendations": [],
            }

        # 2. 搜索 GitHub
        keywords = analysis.get("keywords", [])
        recommendations = await self.search_online(keywords)

        if not recommendations:
            return {
                "type": "none",
                "message": f"未找到与 {', '.join(keywords)} 相关的 Skills",
                "keywords": keywords,
                "recommendations": [],
            }

        return {
            "type": "recommend",
            "message": analysis.get("reason", ""),
            "keywords": keywords,
            "recommendations": recommendations,
        }
