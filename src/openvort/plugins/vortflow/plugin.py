"""
VortFlow 插件主类

敏捷开发流程引擎 — 需求全生命周期管理。
"""

import asyncio
from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.plugins.vortflow.aggregator import im_aggregator
from openvort.plugins.vortflow.engine import FlowEngine
from openvort.plugins.vortflow.notifier import notifier as _notifier_singleton
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow")


class VortFlowPlugin(BasePlugin):
    """VortFlow 敏捷流程引擎插件"""

    name = "vortflow"
    display_name = "VortFlow 敏捷流程"
    description = "AI 驱动的敏捷开发流程引擎，支持需求录入、评审、分配、开发、测试全生命周期管理"
    version = "0.1.0"

    def __init__(self):
        self._engine = FlowEngine()
        self._notifier = _notifier_singleton
        try:
            from openvort.web.ws import manager as ws_manager
            self._notifier.set_ws_manager(ws_manager)
        except ImportError:
            pass
        asyncio.create_task(im_aggregator.start())

    def get_tools(self) -> list[BaseTool]:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.vortflow.tools.assign import AssignTool
        from openvort.plugins.vortflow.tools.group_bind import GroupBindTool
        from openvort.plugins.vortflow.tools.intake import IntakeStoryTool
        from openvort.plugins.vortflow.tools.progress import UpdateProgressTool
        from openvort.plugins.vortflow.tools.project import CreateProjectTool
        from openvort.plugins.vortflow.tools.query import QueryTool

        sf_getter = get_session_factory
        return [
            CreateProjectTool(sf_getter),
            IntakeStoryTool(sf_getter, self._notifier, self._engine),
            AssignTool(sf_getter, self._notifier),
            UpdateProgressTool(sf_getter, self._engine, self._notifier),
            QueryTool(),
            GroupBindTool(),
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
        return True

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
