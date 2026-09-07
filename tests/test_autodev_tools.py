"""AI 员工只读工具：返回不含 master 内部路径；数字来自 service。"""

import json
from types import SimpleNamespace

from openvort.plugins.autodev import service as svc_mod
from openvort.plugins.autodev.models import AutodevRun
from openvort.plugins.autodev.tools import status as tools
from openvort.plugins.autodev.tools.status import INTERNAL_KEYS, AutodevRunsTool, AutodevStatusTool


class FakeService:
    ai_member_id = "ai"

    async def stats(self, project_id, *, days=7):
        return {"configured": True, "queue": 2, "running": 1, "delivered_tickets": 3, "priced": False, "days": days}

    async def list_runs(self, project_id, *, issue_key="", limit=50):
        return [AutodevRun(id="r1", project_id="p", issue_key="TPYBX-1", status="finished", exit_code=0,
                           outcome="delivered", dispatch_dir="/data/autodev/state/dispatch/x",
                           run_dir="/data/autodev/state/runs/x", worktree="/w", image_id="sha", mr_url="http://mr")]


async def test_tools_return_stats_and_strip_internal_paths(monkeypatch):
    async def projects(project_id):
        return [(SimpleNamespace(project_id="fp1", jira_project_key="TPYBX"), "cpic")]

    monkeypatch.setattr(tools, "_resolve_projects", projects)
    monkeypatch.setattr(svc_mod, "_service", FakeService())

    s = json.loads(await AutodevStatusTool().execute({"days": 3}))
    assert s["projects"][0]["queue"] == 2 and s["projects"][0]["project"] == "cpic" and s["projects"][0]["days"] == 3

    r = json.loads(await AutodevRunsTool().execute({"issue_key": "TPYBX-1"}))
    item = r["items"][0]
    assert item["issue_key"] == "TPYBX-1" and item["mr_url"] == "http://mr" and item["exit_meaning"].startswith("/req")
    assert not (set(item) & set(INTERNAL_KEYS))


async def test_tools_without_projects(monkeypatch):
    async def none(project_id):
        return []

    monkeypatch.setattr(tools, "_resolve_projects", none)
    monkeypatch.setattr(svc_mod, "_service", FakeService())
    assert json.loads(await AutodevStatusTool().execute({}))["projects"] == []
