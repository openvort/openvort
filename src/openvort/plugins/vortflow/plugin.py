"""
VortFlow 插件主类

敏捷开发流程引擎 — 需求全生命周期管理。
"""

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.plugins.vortflow.adapters.local import LocalAdapter
from openvort.plugins.vortflow.config import VortFlowSettings
from openvort.plugins.vortflow.engine import FlowEngine
from openvort.plugins.vortflow.notifier import Notifier
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow")


class VortFlowPlugin(BasePlugin):
    """VortFlow 敏捷流程引擎插件"""

    name = "vortflow"
    display_name = "VortFlow 敏捷流程"
    description = "AI 驱动的敏捷开发流程引擎，支持需求录入、评审、分配、开发、测试全生命周期管理"
    version = "0.1.0"

    def __init__(self):
        self._settings = VortFlowSettings()
        self._engine = FlowEngine()
        self._notifier = Notifier()
        self._adapter = self._create_adapter()

    def _create_adapter(self):
        adapter_name = self._settings.adapter
        if adapter_name == "zentao":
            try:
                from openvort.plugins.vortflow.adapters.zentao import ZentaoAdapter
                return ZentaoAdapter()
            except Exception as e:
                log.warning(f"ZentaoAdapter 初始化失败，回退到 LocalAdapter: {e}")
                return LocalAdapter()
        return LocalAdapter()

    def get_tools(self) -> list[BaseTool]:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortflow.tools.assign import AssignTool
        from openvort.plugins.vortflow.tools.intake import IntakeStoryTool
        from openvort.plugins.vortflow.tools.progress import UpdateProgressTool
        from openvort.plugins.vortflow.tools.project import CreateProjectTool
        from openvort.plugins.vortflow.tools.query import QueryTool

        sf_getter = get_session_factory
        return [
            CreateProjectTool(sf_getter),
            IntakeStoryTool(sf_getter, self._adapter, self._notifier, self._engine),
            AssignTool(sf_getter, self._notifier),
            UpdateProgressTool(sf_getter, self._engine, self._notifier),
            QueryTool(),
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
            {"code": "vortflow.story", "display_name": "VortFlow 需求管理"},
            {"code": "vortflow.task", "display_name": "VortFlow 任务管理"},
            {"code": "vortflow.bug", "display_name": "VortFlow 缺陷管理"},
            {"code": "vortflow.assign", "display_name": "VortFlow 角色分配"},
            {"code": "vortflow.admin", "display_name": "VortFlow 管理"},
        ]

    def validate_credentials(self) -> bool:
        return True  # VortFlow 始终可用（LocalAdapter 无需凭证）

    # ---- 配置管理 ----

    def get_config_schema(self) -> list[dict]:
        return [
            {"key": "adapter", "label": "适配器", "type": "select", "required": False,
             "options": [{"value": "local", "label": "本地模式"}, {"value": "zentao", "label": "禅道"}],
             "placeholder": "local"},
            {"key": "sync_interval", "label": "同步间隔(秒)", "type": "string", "required": False, "placeholder": "300"},
            {"key": "sla_check_cron", "label": "SLA 检查 Cron", "type": "string", "required": False, "placeholder": "0 9 * * *"},
            {"key": "overdue_warn_days", "label": "逾期预警天数", "type": "string", "required": False, "placeholder": "2"},
        ]

    def get_current_config(self) -> dict:
        s = self._settings
        return {
            "adapter": s.adapter,
            "sync_interval": str(s.sync_interval),
            "sla_check_cron": s.sla_check_cron,
            "overdue_warn_days": str(s.overdue_warn_days),
        }

    def apply_config(self, config: dict) -> None:
        s = self._settings
        if "adapter" in config:
            s.adapter = config["adapter"]
            self._adapter = self._create_adapter()
        if "sync_interval" in config:
            s.sync_interval = int(config["sync_interval"])
        if "sla_check_cron" in config:
            s.sla_check_cron = config["sla_check_cron"]
        if "overdue_warn_days" in config:
            s.overdue_warn_days = int(config["overdue_warn_days"])

    # ---- UI 扩展 ----

    def get_ui_extensions(self) -> dict | None:
        return {
            "menus": [{
                "label": "VortFlow",
                "icon": "kanban",
                "path": "/vortflow",
                "position": "sidebar",
                "children": [
                    {"label": "项目看板", "path": "/vortflow/board", "icon": "layout-dashboard"},
                    {"label": "需求列表", "path": "/vortflow/stories", "icon": "list-checks"},
                    {"label": "任务管理", "path": "/vortflow/tasks", "icon": "check-square"},
                    {"label": "缺陷跟踪", "path": "/vortflow/bugs", "icon": "bug"},
                    {"label": "里程碑", "path": "/vortflow/milestones", "icon": "milestone"},
                ],
            }],
            "dashboard_widgets": [
                {"type": "stats", "title": "项目概览", "api": "/api/vortflow/dashboard/stats"},
            ],
        }

    def get_api_router(self):
        from openvort.plugins.vortflow.router import router
        return router
