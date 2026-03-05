"""
GitHub Skills 导入器

支持从 GitHub 导入 Skills：
1. 从 URL 克隆仓库并解析 SKILL.md
2. 搜索 GitHub 上的 Skills
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from openvort.skill.directories import SkillDirectoryManager
from openvort.skill.loader import _parse_skill_file
from openvort.utils.logging import get_logger

log = get_logger("skill.importer")


class GitHubImporter:
    """从 GitHub 导入 Skills"""

    def __init__(self):
        self.user_skills_dir = SkillDirectoryManager.ensure_user_dir()
        self.github_token = os.getenv("GITHUB_TOKEN")

    async def import_from_url(self, url: str, owner_id: str = "") -> dict:
        """
        从 GitHub URL 导入 Skill

        Args:
            url: GitHub 仓库 URL 或 SKILL.md 文件 URL
            owner_id: 可选，拥有者 ID（用于 personal scope）

        Returns:
            dict: 导入的 Skill 信息
        """
        # 1. 解析 URL
        parsed = urlparse(url)
        if "github.com" not in parsed.netloc:
            raise ValueError("仅支持 GitHub 仓库")

        # 提取 owner/repo
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError("无效的 GitHub URL 格式")

        owner = path_parts[0]
        repo = path_parts[1].replace(".git", "")
        skill_name = repo  # 默认使用 repo 名作为 skill 名

        # 检查是否指向特定文件
        is_skill_md = "SKILL.md" in parsed.path or "skill.md" in parsed.path.lower()
        file_path = "/".join(path_parts[2:]) if len(path_parts) > 2 else ""

        log.info(f"准备从 GitHub 导入: {owner}/{repo}, is_skill_md={is_skill_md}")

        # 2. 克隆或更新仓库
        repo_dir = self.user_skills_dir / f"{owner}_{repo}"

        if repo_dir.exists():
            # 更新仓库
            log.info(f"更新已有仓库: {repo_dir}")
            try:
                subprocess.run(
                    ["git", "fetch", "--all"],
                    cwd=repo_dir,
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    ["git", "reset", "--hard", "origin/main"],
                    cwd=repo_dir,
                    capture_output=True,
                    check=True,
                )
            except subprocess.CalledProcessError:
                # 可能是 master 分支
                try:
                    subprocess.run(
                        ["git", "reset", "--hard", "origin/master"],
                        cwd=repo_dir,
                        capture_output=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    log.warning(f"更新仓库失败: {e}")
        else:
            # 克隆仓库
            clone_url = f"https://github.com/{owner}/{repo}.git"
            if self.github_token:
                clone_url = f"https://{self.github_token}@github.com/{owner}/{repo}.git"

            log.info(f"克隆仓库: {clone_url}")
            result = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(repo_dir)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise ValueError(f"克隆仓库失败: {result.stderr}")

        # 3. 查找 SKILL.md
        if is_skill_md and file_path:
            # 用户指定了具体文件
            skill_file = repo_dir / file_path
            if not skill_file.exists():
                raise ValueError(f"文件不存在: {file_path}")
            skill_name = skill_file.parent.name
        else:
            # 自动搜索 SKILL.md
            skill_files = list(repo_dir.glob("**/SKILL.md")) + list(repo_dir.glob("**/skill.md"))
            if not skill_files:
                raise ValueError("仓库中未找到 SKILL.md 文件")

            # 使用第一个找到的
            skill_file = skill_files[0]
            # 使用目录名作为 skill 名
            skill_name = skill_file.parent.name

        # 4. 解析 Skill 文件
        parsed_skill = _parse_skill_file(skill_file)
        if not parsed_skill:
            raise ValueError("解析 SKILL.md 失败")

        # 5. 如果需要，移动到以 skill 名命名的目录
        target_dir = self.user_skills_dir / skill_name
        if skill_file.parent != target_dir:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.move(str(skill_file.parent), str(target_dir))
            # 清理空目录
            if repo_dir.exists() and not list(repo_dir.iterdir()):
                shutil.rmtree(repo_dir)

        log.info(f"成功导入 Skill: {skill_name}")

        return {
            "name": parsed_skill.get("name", skill_name),
            "description": parsed_skill.get("description", ""),
            "path": str(target_dir),
            "scope": "personal",
            "source": "github",
            "url": url,
        }

    async def search(self, keyword: str, limit: int = 10) -> list[dict]:
        """
        搜索 GitHub 上的 Skills

        Args:
            keyword: 搜索关键词
            limit: 返回结果数量

        Returns:
            list: 匹配的 Skills 列表
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        search_queries = [
            f"{keyword} SKILL.md in:path language:markdown",
            f"{keyword} skill.md in:path language:markdown",
            f"{keyword} AI assistant skill",
        ]

        results = []
        seen_repos = set()

        async with aiohttp.ClientSession() as session:
            for query in search_queries:
                if len(results) >= limit * 2:
                    break

                url = "https://api.github.com/search/code"
                params = {
                    "q": query,
                    "per_page": min(limit, 30),
                }

                try:
                    async with session.get(url, params=params, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for item in data.get("items", []):
                                repo_name = item["repository"]["full_name"]
                                if repo_name in seen_repos:
                                    continue
                                seen_repos.add(repo_name)

                                results.append({
                                    "repo": repo_name,
                                    "name": item["repository"]["name"],
                                    "url": item["html_url"],
                                    "description": item.get("snippet", "")[:200],
                                    "stars": item["repository"].get("stargazers_count", 0),
                                    "path": item["path"],
                                })
                        elif resp.status == 403:
                            log.warning("GitHub API rate limit exceeded")
                            break
                except Exception as e:
                    log.warning(f"搜索 GitHub 失败: {e}")

        # 按 stars 排序
        results.sort(key=lambda x: x.get("stars", 0), reverse=True)

        return results[:limit]

    async def get_readme_from_repo(self, repo_url: str) -> dict | None:
        """获取仓库的 README 信息"""
        # 从 URL 提取 owner/repo
        parsed = urlparse(repo_url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            return None

        owner = path_parts[0]
        repo = path_parts[1].replace(".git", "")

        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        async with aiohttp.ClientSession() as session:
            url = f"https://api.github.com/repos/{owner}/{repo}"
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "name": data.get("name"),
                            "description": data.get("description"),
                            "stars": data.get("stargazers_count", 0),
                            "url": data.get("html_url"),
                        }
            except Exception as e:
                log.warning(f"获取仓库信息失败: {e}")

        return None
