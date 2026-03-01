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
        from openvort.plugins.vortgit.tools.coding import CodeTaskTool, CommitPushTool, CreatePRTool
        from openvort.plugins.vortgit.tools.commits import QueryCommitsTool, WorkSummaryTool
        from openvort.plugins.vortgit.tools.providers import ManageProviderTool
        from openvort.plugins.vortgit.tools.repos import ListReposTool, RepoInfoTool

        return [
            ListReposTool(),
            RepoInfoTool(),
            QueryCommitsTool(),
            WorkSummaryTool(),
            ManageProviderTool(),
            CodeTaskTool(),
            CommitPushTool(),
            CreatePRTool(),
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
            {"code": "vortgit.code", "display_name": "VortGit AI 编码（触发 CLI 编码任务）"},
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
            {
                "key": "cli_default_tool",
                "label": "默认 CLI 编码工具",
                "type": "select",
                "options": ["claude-code", "aider"],
                "required": False,
                "placeholder": "claude-code",
            },
            {
                "key": "claude_code_api_key",
                "label": "Claude Code API Key",
                "type": "string",
                "required": False,
                "secret": True,
                "placeholder": "sk-ant-...",
            },
            {
                "key": "aider_api_key",
                "label": "Aider API Key",
                "type": "string",
                "required": False,
                "secret": True,
                "placeholder": "API Key for Aider",
            },
        ]

    def get_current_config(self) -> dict:
        return {
            "encryption_key": "***" if self._settings.encryption_key else "",
            "cli_default_tool": self._settings.cli_default_tool,
            "claude_code_api_key": "***" if self._settings.claude_code_api_key else "",
            "aider_api_key": "***" if self._settings.aider_api_key else "",
        }

    def apply_config(self, config: dict) -> None:
        if "encryption_key" in config and config["encryption_key"] != "***":
            self._settings.encryption_key = config["encryption_key"]
        if "cli_default_tool" in config:
            self._settings.cli_default_tool = config["cli_default_tool"]
        if "claude_code_api_key" in config and config["claude_code_api_key"] != "***":
            self._settings.claude_code_api_key = config["claude_code_api_key"]
        if "aider_api_key" in config and config["aider_api_key"] != "***":
            self._settings.aider_api_key = config["aider_api_key"]

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
                        {"label": "编码任务", "path": "/vortgit/code-tasks", "icon": "terminal-square"},
                        {"label": "平台管理", "path": "/vortgit/providers", "icon": "server"},
                    ],
                }
            ],
        }

    def get_api_router(self):
        from openvort.plugins.vortgit.router import router

        return router
