"""
Jenkins plugin for OpenVort.
"""

from __future__ import annotations

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.plugins.jenkins.config import JenkinsSettings
from openvort.plugins.jenkins.tools import (
    BuildLogTool,
    BuildStatusTool,
    JobInfoTool,
    ListJobsTool,
    SystemInfoTool,
    TriggerBuildTool,
)
from openvort.utils.logging import get_logger

log = get_logger("plugins.jenkins")


class JenkinsPlugin(BasePlugin):
    """Jenkins CI/CD 插件"""

    name = "jenkins"
    display_name = "Jenkins CI/CD"
    description = "连接 Jenkins 并通过 AI 对话执行 Job 查询、触发构建、查看日志等操作"
    version = "0.1.0"

    def __init__(self):
        self._settings = JenkinsSettings()

    def get_tools(self) -> list[BaseTool]:
        return [
            ListJobsTool(self._settings),
            JobInfoTool(self._settings),
            TriggerBuildTool(self._settings),
            BuildStatusTool(self._settings),
            BuildLogTool(self._settings),
            SystemInfoTool(self._settings),
        ]

    def get_prompts(self) -> list[str]:
        prompts_dir = Path(__file__).parent / "prompts"
        prompts = []
        for f in sorted(prompts_dir.glob("*.md")):
            try:
                prompts.append(f.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning(f"读取 prompt 文件 {f.name} 失败: {e}")
        return prompts

    def get_permissions(self) -> list[dict]:
        return [
            {"code": "jenkins.read", "display_name": "查看 Jenkins Job/构建状态/日志"},
            {"code": "jenkins.write", "display_name": "触发 Jenkins 构建"},
        ]

    def get_roles(self) -> list[dict]:
        return [
            {
                "name": "jenkins_user",
                "display_name": "Jenkins 用户",
                "permissions": ["jenkins.read", "jenkins.write"],
            }
        ]

    def validate_credentials(self) -> bool:
        # Keep plugin visible in /plugins even before it is configured.
        if not self._settings.url or not self._settings.username:
            log.info("Jenkins 插件尚未配置，可在 /plugins 页面完成配置")
        return True

    # ---- Config ----

    def get_config_schema(self) -> list[dict]:
        return [
            {
                "key": "url",
                "label": "Jenkins 地址",
                "type": "string",
                "required": True,
                "secret": False,
                "placeholder": "http://192.168.5.201:9090",
            },
            {
                "key": "username",
                "label": "用户名",
                "type": "string",
                "required": True,
                "secret": False,
                "placeholder": "admin",
            },
            {
                "key": "api_token",
                "label": "API Token",
                "type": "string",
                "required": True,
                "secret": True,
                "placeholder": "Jenkins 用户 API Token",
            },
            {
                "key": "verify_ssl",
                "label": "验证 SSL 证书",
                "type": "select",
                "required": False,
                "secret": False,
                "options": [
                    {"value": "true", "label": "是"},
                    {"value": "false", "label": "否"},
                ],
                "placeholder": "true",
            },
        ]

    def get_current_config(self) -> dict:
        return {
            "url": self._settings.url,
            "username": self._settings.username,
            "api_token": "****" if self._settings.api_token else "",
            "verify_ssl": "true" if self._settings.verify_ssl else "false",
        }

    def apply_config(self, config: dict) -> None:
        if "url" in config:
            self._settings.url = str(config["url"] or "").strip()
        if "username" in config:
            self._settings.username = str(config["username"] or "").strip()
        if "api_token" in config:
            self._settings.api_token = str(config["api_token"] or "").strip()
        if "verify_ssl" in config:
            raw = config["verify_ssl"]
            if isinstance(raw, bool):
                self._settings.verify_ssl = raw
            else:
                self._settings.verify_ssl = str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}
