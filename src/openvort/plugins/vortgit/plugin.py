"""VortGit plugin — Git repository management for OpenVort."""

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.plugins.vortgit.config import VortGitSettings
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit")


class VortGitPlugin(BasePlugin):
    """Git 仓库管理插件 — 仓库接入、提交分析、AI 编码调度"""

    name = "vortgit"
    display_name = "VortGit 代码仓库"
    description = "Git 仓库管理、提交记录查询、工作汇报生成、AI CLI 编码调度"
    version = "0.1.0"

    def __init__(self):
        self._settings = VortGitSettings()

    def get_tools(self) -> list[BaseTool]:
        from openvort.plugins.vortgit.tools.commits import QueryCommitsTool, WorkSummaryTool
        from openvort.plugins.vortgit.tools.providers import ManageProviderTool
        from openvort.plugins.vortgit.tools.repos import ListReposTool, RepoInfoTool

        return [
            ListReposTool(),
            RepoInfoTool(),
            QueryCommitsTool(),
            WorkSummaryTool(),
            ManageProviderTool(),
        ]

    def get_prompts(self) -> list[str]:
        prompts_dir = Path(__file__).parent / "prompts"
        prompts = []
        for f in sorted(prompts_dir.glob("*.md")):
            try:
                prompts.append(f.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning(f"Failed to read prompt file {f.name}: {e}")
        return prompts

    def get_permissions(self) -> list[dict]:
        return [
            {"code": "vortgit.read", "display_name": "VortGit 查看仓库与提交"},
            {"code": "vortgit.write", "display_name": "VortGit 编码与提交"},
            {"code": "vortgit.admin", "display_name": "VortGit 管理"},
        ]

    def get_roles(self) -> list[dict]:
        return [
            {
                "name": "vortgit_user",
                "display_name": "VortGit 用户",
                "permissions": ["vortgit.read", "vortgit.write"],
            },
        ]

    def validate_credentials(self) -> bool:
        return True

    # ---- Config ----

    def get_config_schema(self) -> list[dict]:
        return [
            {
                "key": "encryption_key",
                "label": "Token 加密密钥",
                "type": "string",
                "required": False,
                "secret": True,
                "placeholder": "留空自动生成",
            },
        ]

    def get_current_config(self) -> dict:
        return {"encryption_key": "***" if self._settings.encryption_key else ""}

    def apply_config(self, config: dict) -> None:
        if "encryption_key" in config and config["encryption_key"] != "***":
            self._settings.encryption_key = config["encryption_key"]

    # ---- UI ----

    def get_ui_extensions(self) -> dict | None:
        return {
            "menus": [
                {
                    "label": "VortGit",
                    "icon": "git-branch",
                    "path": "/vortgit",
                    "position": "sidebar",
                    "children": [
                        {"label": "代码仓库", "path": "/vortgit/repos", "icon": "folder-git-2"},
                        {"label": "平台管理", "path": "/vortgit/providers", "icon": "server"},
                    ],
                }
            ],
        }

    def get_api_router(self):
        from openvort.plugins.vortgit.router import router

        return router
