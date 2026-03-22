"""
Jenkins plugin for OpenVort.
"""

from __future__ import annotations

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.plugins.jenkins.tools import (
    BuildLogTool,
    BuildStatusTool,
    JenkinsManageInstanceTool,
    JobInfoTool,
    ListJobsTool,
    ManageJobTool,
    ManageViewTool,
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

    def get_tools(self) -> list[BaseTool]:
        return [
            JenkinsManageInstanceTool(),
            ListJobsTool(),
            JobInfoTool(),
            TriggerBuildTool(),
            BuildStatusTool(),
            BuildLogTool(),
            SystemInfoTool(),
            ManageJobTool(),
            ManageViewTool(),
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
            {"code": "jenkins.write", "display_name": "管理 Jenkins 实例与触发构建"},
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
        # Multi-instance credentials are managed via jenkins_manage_instance.
        log.info("Jenkins 插件实例配置由 AI 工具 jenkins_manage_instance 管理")
        return True
