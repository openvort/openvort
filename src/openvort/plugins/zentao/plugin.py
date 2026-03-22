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

    def get_permissions(self) -> list[dict]:
        return [
            {"code": "zentao.task", "display_name": "禅道任务管理"},
            {"code": "zentao.bug", "display_name": "禅道 Bug 管理"},
            {"code": "zentao.story", "display_name": "禅道需求管理"},
            {"code": "zentao.effort", "display_name": "禅道工时记录"},
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

    # ---- 配置管理接口 ----

    def get_config_schema(self) -> list[dict]:
        return [
            {"key": "host", "label": "数据库地址", "type": "string", "required": True, "secret": False, "placeholder": "127.0.0.1"},
            {"key": "port", "label": "端口", "type": "string", "required": False, "secret": False, "placeholder": "3306"},
            {"key": "user", "label": "用户名", "type": "string", "required": True, "secret": False, "placeholder": "root"},
            {"key": "password", "label": "密码", "type": "string", "required": True, "secret": True, "placeholder": ""},
            {"key": "database", "label": "数据库名", "type": "string", "required": False, "secret": False, "placeholder": "zentao"},
        ]

    def get_current_config(self) -> dict:
        def _mask(value: str) -> str:
            if not value:
                return ""
            if len(value) <= 4:
                return "****"
            return "****" + value[-4:]

        s = self._settings
        return {
            "host": s.host,
            "port": str(s.port),
            "user": s.user,
            "password": _mask(s.password),
            "database": s.database,
        }

    def apply_config(self, config: dict) -> None:
        s = self._settings
        if "host" in config:
            s.host = config["host"]
        if "port" in config:
            s.port = int(config["port"])
        if "user" in config:
            s.user = config["user"]
        if "password" in config:
            s.password = config["password"]
        if "database" in config:
            s.database = config["database"]
        # 重置 DB 连接，下次使用时重新初始化
        self._db = ZentaoDB(self._settings)

    # ---- 插件引导接口 ----

    def get_platform(self) -> str:
        return "zentao"

    async def get_setup_status(self, ctx) -> str:
        """检查禅道插件对当前用户的就绪状态"""
        from sqlalchemy import func, select

        from openvort.contacts.models import PlatformIdentity
        from openvort.db.engine import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            # 1. 检查是否有禅道通讯录同步过
            count_result = await session.execute(
                select(func.count()).where(PlatformIdentity.platform == "zentao")
            )
            synced_count = count_result.scalar_one()
            if synced_count == 0:
                return "not_synced"

            # 2. 检查当前用户是否已关联禅道身份
            if ctx.member and ctx.platform_accounts.get("zentao"):
                return "ready"

            return "not_bound"

    def get_onboarding_prompt(self, status: str, is_admin: bool) -> str:
        """返回禅道引导 prompt"""
        prompt_path = Path(__file__).parent / "prompts" / "onboarding.md"
        if not prompt_path.exists():
            return ""
        full_prompt = prompt_path.read_text(encoding="utf-8")

        # 根据状态和角色提取对应段落
        if status == "not_synced":
            tag = "[NOT_SYNCED_ADMIN]" if is_admin else "[NOT_SYNCED_USER]"
        elif status == "not_bound":
            tag = "[NOT_BOUND]"
        else:
            return ""

        # 简单按标签提取
        lines = []
        in_section = False
        for line in full_prompt.splitlines():
            if line.strip() == tag:
                in_section = True
                continue
            if in_section and line.strip().startswith("[") and line.strip().endswith("]"):
                break
            if in_section:
                lines.append(line)

        return "\n".join(lines).strip()
