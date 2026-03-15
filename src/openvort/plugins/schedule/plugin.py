"""
Schedule plugin — AI-driven scheduled task management.
"""

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.schedule")


class SchedulePlugin(BasePlugin):
    """计划任务管理插件"""

    name = "schedule"
    display_name = "计划任务"
    description = "通过 AI 对话创建和管理计划任务，支持 cron 定时、固定间隔、一次性执行"
    version = "0.1.0"
    core = True

    def get_tools(self) -> list[BaseTool]:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.schedule.tools.manage import ScheduleManageTool
        from openvort.plugins.schedule.tools.query import ScheduleQueryTool

        sf_getter = get_session_factory
        return [
            ScheduleManageTool(sf_getter),
            ScheduleQueryTool(),
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
