"""AutoDev 查询工具——给 AI 员工回答「队列几张、做完多少、每单花了多少」。只读。"""

from __future__ import annotations

import json

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.autodev.tools")

# 运行记录里 master 内部落点，员工回答不需要也不该外泄
INTERNAL_KEYS = ("dispatch_dir", "run_dir", "worktree", "image_id")


async def _resolve_projects(project_id: str) -> list:
    from openvort.db.engine import get_session_factory
    from openvort.plugins.autodev.models import AutodevProject
    from openvort.plugins.vortflow.models import FlowProject

    sf = get_session_factory()
    async with sf() as db:
        stmt = select(AutodevProject, FlowProject.name).join(FlowProject, FlowProject.id == AutodevProject.project_id)
        if project_id:
            stmt = stmt.where(AutodevProject.project_id == project_id)
        return [(p, name) for p, name in (await db.execute(stmt)).all()]


class AutodevStatusTool(BaseTool):
    name = "autodev_status"
    description = (
        "查询自动交付流水线的状态：派发队列长度、运行中数量、近 N 天各结果计数、"
        "token 用量与费用合计、当前闸门状态。不传 project_id 则汇总全部已配置项目。"
        "所有数字直接来自运行记录与队列，不要自行估算。"
    )
    required_permission = "autodev.read"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "VortFlow 项目 ID（可选）", "default": ""},
                "days": {"type": "integer", "description": "统计窗口天数，默认 7", "default": 7},
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        from openvort.plugins.autodev.service import get_service

        svc = get_service()
        days = int(params.get("days") or 7)
        out = []
        for p, name in await _resolve_projects(params.get("project_id", "")):
            s = await svc.stats(p.project_id, days=days)
            s["project"] = name
            s["project_id"] = p.project_id
            s["jira_project_key"] = p.jira_project_key
            out.append(s)
        if not out:
            return json.dumps({"projects": [], "note": "没有已配置自动交付的项目"}, ensure_ascii=False)
        return json.dumps({"projects": out}, ensure_ascii=False)


class AutodevRunsTool(BaseTool):
    name = "autodev_runs"
    description = (
        "列出自动交付的运行记录：每次运行的工单号、结果（delivered/verified/no_change/failed）、"
        "退出码含义、MR 链接、token 用量与费用、耗时。可按工单号过滤。"
    )
    required_permission = "autodev.read"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "VortFlow 项目 ID（可选）", "default": ""},
                "issue_key": {"type": "string", "description": "只看某张单，如 ABC-123（可选）", "default": ""},
                "limit": {"type": "integer", "description": "最多返回条数，默认 20", "default": 20},
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        from openvort.plugins.autodev.router import run_dict
        from openvort.plugins.autodev.service import get_service

        svc = get_service()
        limit = max(1, min(int(params.get("limit") or 20), 200))
        items = []
        for p, name in await _resolve_projects(params.get("project_id", "")):
            for r in await svc.list_runs(p.project_id, issue_key=params.get("issue_key", ""), limit=limit):
                d = run_dict(r)
                d["project"] = name
                for k in INTERNAL_KEYS:
                    d.pop(k, None)
                items.append(d)
        items.sort(key=lambda d: d["started_at"] or "", reverse=True)
        return json.dumps({"items": items[:limit]}, ensure_ascii=False)
