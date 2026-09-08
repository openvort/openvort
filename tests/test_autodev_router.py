"""autodev REST：鉴权边界（403）、配置脱敏、队列/派发/统计主要读写。TestClient + sqlite。"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Integer, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from openvort.contacts.models import Member
from openvort.db import engine as db_engine
from openvort.db.engine import Base
from openvort.db.models import RemoteNode
from openvort.plugins.autodev import service as svc_mod
from openvort.plugins.autodev.router import router
from openvort.plugins.autodev.service import AutodevService
from openvort.plugins.vortflow.models import FlowExternalMapping, FlowProject, FlowStory
from openvort.web.auth import create_token

AI = "ai-member"
TABLES = ("members", "flow_projects", "flow_stories", "flow_external_mappings", "flow_comments",
          "remote_nodes", "schedule_jobs", "autodev_projects", "autodev_runs")


class FakeExec:
    def __init__(self):
        self.calls = []

    async def __call__(self, cid, command, *, timeout=300, on_text=None):
        self.calls.append(command)
        if command.startswith("jira --json issue list"):
            out = [{"key": "TPYBX-1", "fields": {"summary": "a", "status": {"name": "新增"}}}]
            return {"stdout": json.dumps(out), "stderr": "", "exit_code": 0}
        if "03_config/.env" in command:
            return {"stdout": "", "stderr": "", "exit_code": 0}
        if "nohup setsid" in command:
            return {"stdout": "launched\n", "stderr": "", "exit_code": 0}
        return {"stdout": "", "stderr": "", "exit_code": 0}

    async def write(self, cid, command, content, timeout=30):
        return {"stdout": "", "stderr": "", "exit_code": 0}


@pytest.fixture
async def client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Base.metadata.tables["flow_comments"].c.id.type = Integer()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[Base.metadata.tables[t] for t in TABLES])
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as db:
        db.add(Member(id=AI, name="交付员", is_virtual=True, remote_node_id="node1"))
        db.add(FlowProject(id="fp1", name="cpic"))
        db.add(RemoteNode(id="node1", name="master", node_type="docker", gateway_url="",
                          config=json.dumps({"container_id": "cid", "autodev_master": True, "max_slots": 2})))
        await db.commit()
    monkeypatch.setattr(db_engine, "get_session_factory", lambda: sf)
    fake = FakeExec()
    svc = AutodevService(sf, exec_fn=fake, write_fn=fake.write)
    svc.ai_member_id = AI
    svc_mod.set_service(svc)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        c.sf = sf
        c.fake = fake
        yield c
    await engine.dispose()


def _auth(roles):
    return {"Authorization": "Bearer " + create_token("m-admin", "admin", roles)}


ADMIN = _auth(["admin"])
USER = _auth(["member"])
CONFIG = {
    "repo_path": "/data/autodev/repos/cpic", "jira_project_key": "TPYBX",
    "hcm_base_url": "https://h", "hcm_username": "sysuser", "hcm_password": "secret-pass",
    "env": {"HTTP_PROXY": "http://p"},
}


def test_non_admin_cannot_write(client):
    assert client.put("/api/autodev/projects/fp1", json=CONFIG, headers=USER).status_code == 403
    assert client.put("/api/autodev/projects/fp1", json=CONFIG).status_code == 401
    assert client.post("/api/autodev/projects/fp1/dispatch", json={}, headers=USER).status_code == 403
    assert client.put("/api/autodev/global/autodev_dispatch", json={"enabled": True}, headers=USER).status_code == 403


def test_config_roundtrip_masks_password_and_rejects_secret_env(client):
    r = client.put("/api/autodev/projects/fp1", json=CONFIG, headers=ADMIN)
    assert r.status_code == 200, r.text
    cfg = r.json()["config"]
    assert cfg["hcm_password"] == "****pass" and cfg["hcm_username"] == "sysuser"
    assert "daily_cap" not in cfg and "master_node_id" not in cfg and "status_map" not in cfg
    assert client.get("/api/autodev/projects/fp1").json()["config"]["hcm_password"] == "****pass"
    # 原样提交脱敏值：不覆盖
    client.put("/api/autodev/projects/fp1", json={"hcm_password": "****pass", "sync_window_days": 5}, headers=ADMIN)
    svc = svc_mod.get_service()
    import asyncio
    p = asyncio.get_event_loop().run_until_complete(svc.get_project("fp1"))
    assert svc.hcm_values(p)["HCM_PASSWORD"] == "secret-pass" and p.sync_window_days == 5
    # 固定参数与 master 从 /global 读
    g = client.get("/api/autodev/global").json()
    assert g["master"]["node_id"] == "node1" and g["master"]["max_slots"] == 2
    assert g["fixed"]["daily_cap"] == 3 and g["fixed"]["status_map"]["OPEN"] == "in_progress"
    bad = client.put("/api/autodev/projects/fp1", json={"env": {"GITLAB_TOKEN": "x"}}, headers=ADMIN)
    assert bad.status_code == 400 and "密钥" in bad.json()["detail"]


def test_sync_queue_dispatch_runs_stats(client):
    client.put("/api/autodev/projects/fp1", json=CONFIG, headers=ADMIN)
    assert client.post("/api/autodev/projects/fp1/sync", headers=USER).status_code == 403
    r = client.post("/api/autodev/projects/fp1/sync", headers=ADMIN)
    assert r.status_code == 200 and r.json()["counts"]["created"] == 1

    q = client.get("/api/autodev/projects/fp1/queue").json()
    assert q["items"] == [] and q["ai_member_id"] == AI

    import asyncio
    loop = asyncio.get_event_loop()

    async def assign():
        async with client.sf() as db:
            stmt = select(FlowExternalMapping).where(FlowExternalMapping.external_id == "TPYBX-1")
            m = (await db.execute(stmt)).scalar_one()
            s = await db.get(FlowStory, m.local_id)
            s.assignee_id, s.state = AI, "dev_assign"
            await db.commit()
    loop.run_until_complete(assign())

    q = client.get("/api/autodev/projects/fp1/queue").json()
    assert [i["key"] for i in q["items"]] == ["TPYBX-1"] and q["items"][0]["running"] is False

    d = client.post("/api/autodev/projects/fp1/dispatch", json={"issue_key": "TPYBX-1"}, headers=ADMIN)
    assert d.status_code == 200 and d.json()["started"] == ["TPYBX-1"]
    d2 = client.post("/api/autodev/projects/fp1/dispatch", json={"issue_key": "TPYBX-1"}, headers=ADMIN)
    assert d2.json()["reason"] == "该单已在运行"

    runs = client.get("/api/autodev/projects/fp1/runs").json()["items"]
    assert len(runs) == 1 and runs[0]["status"] == "running" and runs[0]["exit_meaning"] == "运行中"
    stats = client.get("/api/autodev/projects/fp1/stats").json()
    assert stats["running"] == 1 and stats["queue"] == 0 and stats["gate"]["allowed"] == 1  # 节点 slot=2
    assert client.get("/api/autodev/exit-codes").json()["codes"][0] == {
        "code": 0, "meaning": svc_mod.ct.EXIT_CODES[0], "outcome": "delivered"}


def test_pause_resume_and_missing_project(client):
    assert client.get("/api/autodev/projects/nope").json()["config"] is None
    assert client.get("/api/autodev/projects/nope/queue").status_code == 404
    client.put("/api/autodev/projects/fp1", json=CONFIG, headers=ADMIN)
    assert client.post("/api/autodev/projects/fp1/pause", headers=ADMIN).json()["config"]["paused"] is True
    d = client.post("/api/autodev/projects/fp1/dispatch", json={}, headers=ADMIN).json()
    assert d["reason"] == "派发已暂停"
    assert client.post("/api/autodev/projects/fp1/resume", headers=ADMIN).json()["config"]["paused"] is False
