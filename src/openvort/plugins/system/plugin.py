"""
System management plugin — system configuration, channel setup, and diagnostics.
"""

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.system")


class SystemPlugin(BasePlugin):
    """OpenVort 系统管理插件"""

    name = "system"
    display_name = "系统管理"
    description = "OpenVort 系统配置与诊断，支持 AI 引导配置通道、检测连通性"
    version = "0.1.0"
    core = True

    def get_tools(self) -> list[BaseTool]:
        from openvort.plugins.system.tools.channel_config import SystemChannelConfigTool
        from openvort.plugins.system.tools.diagnose import SystemDiagnoseTool

        return [
            SystemChannelConfigTool(),
            SystemDiagnoseTool(),
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

    def validate_credentials(self) -> bool:
        return True
