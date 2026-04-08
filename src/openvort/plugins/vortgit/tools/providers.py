"""
VortGit provider tools — git_manage_provider

Write tools for managing Git platform configurations via AI conversation.
"""

import json
import uuid

from sqlalchemy import select, func

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit.tools.providers")

_PLATFORM_DEFAULTS = {
    "gitee": "https://gitee.com/api/v5",
    "github": "https://api.github.com",
    "gitlab": "https://gitlab.com/api/v4",
}


class ManageProviderTool(BaseTool):
    name = "git_manage_provider"
    description = (
        "管理 Git 代码托管平台配置。支持以下操作：\n"
        "- list: 列出所有已配置的 Git 平台\n"
        "- create: 添加新的 Git 平台（如 Gitee、GitHub、GitLab）\n"
        "- verify: 验证平台 Token 是否有效（调用平台 API 获取用户信息）\n"
        "- delete: 删除指定平台配置\n"
        "当用户说'帮我配置 Gitee'、'添加 Git 平台'、'录入 GitHub'时使用。\n"
        "创建平台需要用户提供 Access Token（私人令牌），"
        "如果用户未提供，应引导用户去对应平台生成令牌。"
    )
    required_permission = "vortgit.admin"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "verify", "delete"],
                    "description": "操作类型",
                },
                "name": {
                    "type": "string",
                    "description": "平台显示名称，如'公司 Gitee'、'个人 GitHub'（create 时必填）",
                    "default": "",
                },
                "platform": {
                    "type": "string",
                    "enum": ["gitee", "github", "gitlab"],
                    "description": "平台类型（create 时必填）",
                    "default": "gitee",
                },
                "access_token": {
                    "type": "string",
                    "description": "平台 Access Token / 私人令牌（create 时必填）",
                    "default": "",
                },
                "api_base": {
                    "type": "string",
                    "description": "自定义 API 地址，留空使用平台默认地址（自建 GitLab 需填写）",
                    "default": "",
                },
                "is_default": {
                    "type": "boolean",
                    "description": "是否设为默认平台",
                    "default": False,
                },
                "provider_id": {
                    "type": "string",
                    "description": "平台 ID（verify/delete 时使用）",
                    "default": "",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        action = params.get("action", "")
        if action == "list":
            return await self._list()
        elif action == "create":
            return await self._create(params)
        elif action == "verify":
            return await self._verify(params)
        elif action == "delete":
            return await self._delete(params)
        return json.dumps({"ok": False, "message": f"未知操作: {action}"})

    async def _list(self) -> str:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortgit.models import GitProvider

        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(
                select(GitProvider).order_by(GitProvider.created_at.desc())
            )
            providers = result.scalars().all()
            data = [
                {
                    "id": p.id,
                    "name": p.name,
                    "platform": p.platform,
                    "api_base": p.api_base or _PLATFORM_DEFAULTS.get(p.platform, ""),
                    "has_token": bool(p.access_token),
                    "is_default": p.is_default,
                }
                for p in providers
            ]

        if not data:
            return json.dumps(
                {
                    "ok": True,
                    "count": 0,
                    "providers": [],
                    "hint": "尚未配置任何 Git 平台。可以帮用户添加 Gitee/GitHub/GitLab 平台。",
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {"ok": True, "count": len(data), "providers": data},
            ensure_ascii=False,
        )

    async def _create(self, params: dict) -> str:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortgit.crypto import encrypt_token
        from openvort.plugins.vortgit.models import GitProvider

        name = params.get("name", "").strip()
        platform = params.get("platform", "gitee")
        access_token = params.get("access_token", "").strip()
        api_base = params.get("api_base", "").strip()
        is_default = params.get("is_default", False)

        if not name:
            return json.dumps(
                {"ok": False, "message": "请提供平台名称（name），如'个人 Gitee'"},
                ensure_ascii=False,
            )
        if not access_token:
            hints = {
                "gitee": "请用户前往 https://gitee.com/personal_access_tokens 生成私人令牌，勾选 projects、pull_requests、issues 权限。",
                "github": "请用户前往 https://github.com/settings/tokens 生成 Personal Access Token，勾选 repo 权限。",
                "gitlab": "请用户前往 GitLab → Settings → Access Tokens 生成令牌，勾选 api 权限。",
            }
            return json.dumps(
                {
                    "ok": False,
                    "message": "缺少 Access Token",
                    "hint": hints.get(platform, "请提供平台的 Access Token。"),
                },
                ensure_ascii=False,
            )

        if not api_base:
            api_base = _PLATFORM_DEFAULTS.get(platform, "")

        sf = get_session_factory()
        async with sf() as session:
            provider = GitProvider(
                id=uuid.uuid4().hex,
                name=name,
                platform=platform,
                api_base=api_base,
                access_token=encrypt_token(access_token) if access_token else "",
                is_default=is_default,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)

            return json.dumps(
                {
                    "ok": True,
                    "message": f"已成功添加 Git 平台「{name}」({platform})",
                    "provider": {
                        "id": provider.id,
                        "name": provider.name,
                        "platform": provider.platform,
                        "api_base": provider.api_base,
                        "is_default": provider.is_default,
                    },
                    "next_step": "可以使用 verify 操作验证 Token 是否有效，或直接导入仓库。",
                },
                ensure_ascii=False,
            )

    async def _verify(self, params: dict) -> str:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortgit.crypto import decrypt_token
        from openvort.plugins.vortgit.models import GitProvider

        provider_id = params.get("provider_id", "").strip()

        sf = get_session_factory()
        async with sf() as session:
            if provider_id:
                provider = await session.get(GitProvider, provider_id)
            else:
                provider = await session.scalar(
                    select(GitProvider).order_by(GitProvider.created_at.desc()).limit(1)
                )

            if not provider:
                return json.dumps({"ok": False, "message": "未找到平台配置，请先创建。"})

            if not provider.access_token:
                return json.dumps({"ok": False, "message": f"平台「{provider.name}」未配置 Token。"})

            token = decrypt_token(provider.access_token)
            platform = provider.platform
            p_name = provider.name
            p_id = provider.id

        try:
            from openvort.plugins.vortgit.providers import create_provider

            client = create_provider(platform, access_token=token)
            try:
                repos = await client.list_repos(page=1, per_page=1)
                return json.dumps(
                    {
                        "ok": True,
                        "message": f"平台「{p_name}」Token 验证成功！可以正常访问仓库。",
                        "provider_id": p_id,
                        "sample_repo": repos[0]["full_name"] if repos else None,
                    },
                    ensure_ascii=False,
                )
            except Exception as e:
                return json.dumps(
                    {
                        "ok": False,
                        "message": f"Token 验证失败：{e}",
                        "hint": "请检查 Token 是否正确、是否已过期。",
                    },
                    ensure_ascii=False,
                )
            finally:
                await client.close()
        except ValueError as e:
            return json.dumps(
                {"ok": False, "message": f"暂不支持验证 {platform} 平台：{e}"},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"ok": False, "message": f"验证出错：{e}"})

    async def _delete(self, params: dict) -> str:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortgit.models import GitProvider, GitRepo

        provider_id = params.get("provider_id", "").strip()
        if not provider_id:
            return json.dumps({"ok": False, "message": "请提供 provider_id"})

        sf = get_session_factory()
        async with sf() as session:
            provider = await session.get(GitProvider, provider_id)
            if not provider:
                return json.dumps({"ok": False, "message": "平台不存在"})

            repo_count = await session.scalar(
                select(func.count()).where(GitRepo.provider_id == provider_id)
            )
            if repo_count and repo_count > 0:
                return json.dumps(
                    {
                        "ok": False,
                        "message": f"无法删除：该平台下还有 {repo_count} 个仓库，请先移除仓库。",
                    },
                    ensure_ascii=False,
                )

            name = provider.name
            await session.delete(provider)
            await session.commit()

        return json.dumps(
            {"ok": True, "message": f"已删除平台「{name}」"},
            ensure_ascii=False,
        )
