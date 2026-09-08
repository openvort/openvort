"""AutoDev plugin — 无人值守交付流水线的 master 侧。

worker（`docker run --rm` 一次性容器，跑 `/req <单号>`）与它的宿主脚本 worker.sh 不在本仓；
本插件只做四件事：Jira→story 投影、按机械闸门派发、回收运行结果、让 AI 员工能查。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.autodev")


class AutoDevPlugin(BasePlugin):
    name = "autodev"
    display_name = "AutoDev 自动交付"
    description = "按 Jira 投影队列派发 worker 容器做无人值守交付，记录每单结果与用量，供 AI 员工查询"
    version = "0.2.0"

    def __init__(self) -> None:
        super().__init__()
        self._ai_member_id = ""
        self._svc = None

    def activate(self, api) -> None:
        super().activate(api)
        from openvort.core.services.schedule_service import register_action_handler
        from openvort.db.engine import get_session_factory
        from openvort.plugins.autodev.service import (
            ACTION_DISPATCH,
            ACTION_SYNC,
            AutodevService,
            schedule_dispatch_handler,
            schedule_sync_handler,
            set_service,
        )

        svc = AutodevService(get_session_factory())
        svc.ai_member_id = self._ai_member_id
        set_service(svc)
        self._svc = svc
        register_action_handler(ACTION_DISPATCH, schedule_dispatch_handler)
        register_action_handler(ACTION_SYNC, schedule_sync_handler)
        try:
            loop = asyncio.get_running_loop()
            svc.start_background()
            loop.create_task(svc.refresh_member_choices())  # 首屏就有下拉，不等第一轮轮询
        except RuntimeError:
            log.warning("autodev: 无运行中的事件循环，回收循环未启动（测试或 CLI 环境）")

    def get_tools(self) -> list[BaseTool]:
        from openvort.plugins.autodev.tools.status import AutodevRunsTool, AutodevStatusTool

        return [AutodevStatusTool(), AutodevRunsTool()]

    def get_prompts(self) -> list[str]:
        prompts_dir = Path(__file__).parent / "prompts"
        return [f.read_text(encoding="utf-8") for f in sorted(prompts_dir.glob("*.md"))]

    def get_permissions(self) -> list[dict]:
        return [
            {"code": "autodev.read", "display_name": "AutoDev 查看派发状态与运行记录"},
            {"code": "autodev.admin", "display_name": "AutoDev 配置与派发"},
        ]

    def get_roles(self) -> list[dict]:
        return [{"name": "autodev_viewer", "display_name": "AutoDev 观察者", "permissions": ["autodev.read"]}]

    def validate_credentials(self) -> bool:
        return True

    # ---- 插件配置：全局唯一 AI 员工 ----

    def get_config_schema(self) -> list[dict]:
        choices = list(getattr(self._svc, "member_choices", []) or [])
        options = [
            {"value": c["id"], "label": c["name"] + ("" if c["node_id"] else "（未绑定工作机）")}
            for c in choices
        ]
        field: dict = {
            "key": "ai_member_id",
            "label": "自动交付 AI 员工",
            "required": True,
            "secret": False,
            "description": "全公司唯一的自动交付 AI 员工。需求指派给它并处于「已分配」即进入派发队列；"
                           "派发用的工作机取自它绑定的节点；它也是两条全局定时任务的负责人。",
        }
        if options:
            field.update(type="select", options=options, placeholder="选择一位数字员工")
        else:
            # 还没建数字员工，或快照未就绪：退回手填，别把人卡死在空下拉里
            field.update(type="string", placeholder="members.id（先去组织管理建一位数字员工）")
        return [field]

    def get_current_config(self) -> dict:
        return {"ai_member_id": self._ai_member_id}

    def apply_config(self, config: dict) -> None:
        if "ai_member_id" in config:
            self._ai_member_id = (config.get("ai_member_id") or "").strip()
            if self._svc is not None:
                self._svc.ai_member_id = self._ai_member_id

    def get_api_router(self):
        from openvort.plugins.autodev.router import router

        return router
