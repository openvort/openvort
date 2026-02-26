"""
禅道插件主类

组装所有 Tools 和 Prompts，通过 entry_points 被 OpenVort 自动发现加载。
"""

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.plugins.zentao.config import ZentaoSettings
from openvort.plugins.zentao.db import ZentaoDB
from openvort.plugins.zentao.tools.create_task import CreateTaskTool
from openvort.plugins.zentao.tools.update_task import UpdateTaskTool
from openvort.plugins.zentao.tools.my_tasks import MyTasksTool
from openvort.plugins.zentao.tools.task_detail import TaskDetailTool
from openvort.plugins.zentao.tools.log_effort import LogEffortTool
from openvort.plugins.zentao.tools.create_bug import CreateBugTool
from openvort.plugins.zentao.tools.update_bug import UpdateBugTool
from openvort.plugins.zentao.tools.my_bugs import MyBugsTool
from openvort.plugins.zentao.tools.create_story import CreateStoryTool
from openvort.plugins.zentao.tools.update_story import UpdateStoryTool
from openvort.plugins.zentao.tools.my_stories import MyStoriesTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.zentao")


class ZentaoPlugin(BasePlugin):
    """禅道项目管理插件"""

    name = "zentao"
    display_name = "禅道项目管理"
    description = "对接禅道，支持任务/Bug 的创建、查询、更新、工时记录"
    version = "0.1.0"

    def __init__(self):
        self._settings = ZentaoSettings()
        self._db = ZentaoDB(self._settings)

    def get_tools(self) -> list[BaseTool]:
        """返回禅道插件的所有 Tool"""
        return [
            CreateTaskTool(self._db),
            UpdateTaskTool(self._db),
            MyTasksTool(self._db),
            TaskDetailTool(self._db),
            LogEffortTool(self._db),
            CreateBugTool(self._db),
            UpdateBugTool(self._db),
            MyBugsTool(self._db),
            CreateStoryTool(self._db),
            UpdateStoryTool(self._db),
            MyStoriesTool(self._db),
        ]

    def get_prompts(self) -> list[str]:
        """读取 prompts/ 目录下的 markdown 文件作为领域知识"""
        prompts_dir = Path(__file__).parent / "prompts"
        prompts = []
        for f in sorted(prompts_dir.glob("*.md")):
            try:
                prompts.append(f.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning(f"读取 prompt 文件 {f.name} 失败: {e}")
        return prompts

    def validate_credentials(self) -> bool:
        """校验禅道数据库配置是否完整"""
        if not self._settings.host or not self._settings.user:
            log.warning("禅道插件未配置（缺少 OPENVORT_ZENTAO_HOST 或 OPENVORT_ZENTAO_USER），跳过加载")
            return False
        return True

    def get_sync_provider(self):
        """返回禅道通讯录同步提供者"""
        from openvort.plugins.zentao.sync import ZentaoContactSyncProvider
        return ZentaoContactSyncProvider(self._db)
