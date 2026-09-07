"""autodev 服务层：sqlite 内存库 + 桩 exec，验证同步 / 队列 / 闸门 / 派发 / 凭据写入 / 回收 / 统计。"""

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import Integer, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from openvort.contacts.models import Member
from openvort.db.engine import Base
from openvort.db.models import RemoteNode
from openvort.plugins.autodev import contract as ct
from openvort.plugins.autodev import service as svc_mod
from openvort.plugins.autodev.models import AutodevProject, AutodevRun
from openvort.plugins.autodev.service import AutodevError, AutodevService
from openvort.plugins.vortflow.models import FlowComment, FlowExternalMapping, FlowProject, FlowStory

AI = "ai-member"
TABLES = ("members", "flow_projects", "flow_stories", "flow_external_mappings", "flow_comments",
          "remote_nodes", "schedule_jobs", "autodev_projects", "autodev_runs")


def jira_out(*rows):
    return json.dumps([
        {"key": k, "fields": {"summary": s, "description": "d", "status": {"name": st}, "priority": {"name": pr}}}
        for k, s, st, pr in rows
    ])


class FakeExec:
    """按命令前缀回放输出；记录全部命令与 stdin 写入供断言。"""

    def __init__(self):
        self.calls: list[str] = []
        self.writes: list[tuple[str, str]] = []
        self.jira = jira_out(("TPYBX-1", "a", "新增", "High"), ("TPYBX-2", "b", "新增", "Medium"))
        self.env_text = "HCM_BASE_URL=https://h\nHCM_USERNAME=u\nHCM_PASSWORD=p\nHCM_TOKEN=tok\n"
        self.rc_text = "RC=\n"
        self.summary = {"ticket": "TPYBX-1", "branch": "auto/TPYBX-1", "worktree": "/w", "mr_url": "http://gl/mr/9",
                        "image_id": "sha256:abc", "model": "m", "exit_code": 0, "verdict": "全绿"}
        self.usage = [{"run": "TPYBX-1-20260907-120000", "inputTokens": 1000, "outputTokens": 100,
                       "totalTokens": 1100, "cachedInputTokens": 500, "calls": 3, "durMs": 4200}]
        self.fail_launch = False

    async def __call__(self, cid, command, *, timeout=300, on_text=None):
        self.calls.append(command)
        assert cid == "cid-master"
        if command.startswith("jira --json issue list"):
            return {"stdout": self.jira, "stderr": "", "exit_code": 0}
        if "nohup setsid" in command:
            if self.fail_launch:
                return {"stdout": "", "stderr": "boom", "exit_code": 2}
            return {"stdout": "launched\n", "stderr": "", "exit_code": 0}
        if command.startswith("if [ -f "):
            return {"stdout": self.rc_text, "stderr": "", "exit_code": 0}
        if command.startswith("cat ") and command.endswith("summary.json"):
            return {"stdout": json.dumps(self.summary), "stderr": "", "exit_code": 0}
        if command.startswith("cat ") and "03_config/.env" in command:
            return {"stdout": self.env_text, "stderr": "", "exit_code": 0}
        if "usage-report.py" in command:
            return {"stdout": json.dumps(self.usage), "stderr": "", "exit_code": 0}
        raise AssertionError(f"未预期的命令: {command}")

    async def write(self, cid, command, content, timeout=30):
        assert cid == "cid-master"
        self.writes.append((command, content))
        self.env_text = content
        return {"stdout": "", "stderr": "", "exit_code": 0}


@pytest.fixture
async def sf():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # sqlite 只给 INTEGER PRIMARY KEY 自增；flow_comments.id 是 BigInteger（Postgres serial），测试里降型
    Base.metadata.tables["flow_comments"].c.id.type = Integer()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[Base.metadata.tables[t] for t in TABLES])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(Member(id=AI, name="交付员", is_virtual=True))
        db.add(Member(id="human", name="顾问甲"))
        db.add(FlowProject(id="fp1", name="cpic"))
        db.add(FlowProject(id="fp2", name="spic"))
        db.add(RemoteNode(id="node1", name="master", node_type="docker", gateway_url="",
                          config=json.dumps({"container_id": "cid-master", "autodev_master": True, "max_slots": 1}),
                          status="running"))
        db.add(RemoteNode(id="node-oc", name="other", node_type="openclaw", gateway_url="http://x"))
        await db.commit()
    yield factory
    await engine.dispose()


@pytest.fixture
async def service(sf):
    fake = FakeExec()
    s = AutodevService(sf, exec_fn=fake, write_fn=fake.write)
    s.ai_member_id = AI
    await s.upsert_project("fp1", {
        "master_node_id": "node1", "repo_path": "/data/autodev/repos/cpic", "jira_project_key": "TPYBX",
        "daily_cap": 2, "deliver": False, "env_json": {"HTTP_PROXY": "http://p"},
        "price_in_per_m": 2.0, "price_out_per_m": 8.0,
        "hcm_base_url": "https://h", "hcm_username": "u", "hcm_password": "p",
    })
    s.fake = fake
    return s


async def _assign(sf, key: str, member: str = AI, state: str = ct.STATE_DEV_ASSIGN) -> str:
    async with sf() as db:
        m = (await db.execute(select(FlowExternalMapping).where(FlowExternalMapping.external_id == key))).scalar_one()
        story = await db.get(FlowStory, m.local_id)
        story.assignee_id = member
        story.state = state
        await db.commit()
        return story.id


async def _story(sf, key: str) -> FlowStory:
    async with sf() as db:
        m = (await db.execute(select(FlowExternalMapping).where(FlowExternalMapping.external_id == key))).scalar_one()
        return await db.get(FlowStory, m.local_id)


# ---------- 配置 ----------


async def test_upsert_rejects_secret_env_and_bad_status_map(service):
    with pytest.raises(ValueError):
        await service.upsert_project("fp1", {"env_json": {"GITLAB_TOKEN": "x"}})
    with pytest.raises(ValueError):
        await service.upsert_project("fp1", {"status_map_json": {"x": 1}})


async def test_password_encrypted_and_mask_prefix_keeps_value(service):
    p = await service.get_project("fp1")
    assert p.hcm_password_enc and p.hcm_password_enc != "p"
    assert service.hcm_values(p)["HCM_PASSWORD"] == "p"
    await service.upsert_project("fp1", {"hcm_password": "****xxxx"})
    assert service.hcm_values(await service.get_project("fp1"))["HCM_PASSWORD"] == "p"
    await service.upsert_project("fp1", {"hcm_password": "new"})
    assert service.hcm_values(await service.get_project("fp1"))["HCM_PASSWORD"] == "new"


async def test_exec_on_refuses_non_docker_and_nonzero(service):
    with pytest.raises(AutodevError, match="docker"):
        await service.exec_on("node-oc", "true")
    with pytest.raises(AutodevError, match="未绑定"):
        await service.exec_on("", "true")
    service.fake.fail_launch = True
    with pytest.raises(AutodevError, match="rc=2"):
        await service.exec_on("node1", "nohup setsid bash -c x")


# ---------- 同步 ----------


async def test_sync_creates_stories_and_mappings_once(service, sf):
    p = await service.get_project("fp1")
    c1 = await service.sync_project(p)
    assert c1 == {"seen": 2, "created": 2, "updated": 0, "state_changed": 0, "unmapped": 0}
    assert "updated >= -365d" in service.fake.calls[0]  # 首次全量窗口
    c2 = await service.sync_project(await service.get_project("fp1"))
    assert c2["created"] == 0 and c2["updated"] == 2
    assert "updated >= -30d" in service.fake.calls[1]  # 之后增量窗口
    async with sf() as db:
        assert len((await db.execute(select(FlowStory))).scalars().all()) == 2
        stmt = select(FlowExternalMapping).where(FlowExternalMapping.external_id == "TPYBX-1")
        m = (await db.execute(stmt)).scalar_one()
        assert m.adapter == "jira" and m.local_type == "story" and m.sync_cursor == "新增"
    s = await _story(sf, "TPYBX-1")
    assert s.project_id == "fp1" and s.state == ct.STATE_SUBMITTED and s.priority == 2 and s.title == "a"


async def test_sync_keeps_human_dev_assign_when_jira_unchanged(service, sf):
    await service.sync_project(await service.get_project("fp1"))
    await _assign(sf, "TPYBX-1")
    await service.sync_project(await service.get_project("fp1"))
    assert (await _story(sf, "TPYBX-1")).state == ct.STATE_DEV_ASSIGN


async def test_sync_overrides_on_jira_change_and_warns_on_unmapped(service, sf):
    await service.sync_project(await service.get_project("fp1"))
    await _assign(sf, "TPYBX-1")
    service.fake.jira = jira_out(("TPYBX-1", "a", "OPEN", "High"), ("TPYBX-2", "b", "怪状态", "Low"))
    c = await service.sync_project(await service.get_project("fp1"))
    assert c["state_changed"] == 1 and c["unmapped"] == 1
    assert (await _story(sf, "TPYBX-1")).state == ct.STATE_IN_PROGRESS
    assert (await _story(sf, "TPYBX-2")).state == ct.STATE_SUBMITTED  # 表外状态：保留


async def test_sync_zero_hit_keeps_stories(service, sf):
    await service.sync_project(await service.get_project("fp1"))
    service.fake.jira = "[]"
    c = await service.sync_project(await service.get_project("fp1"))
    assert c["seen"] == 0
    async with sf() as db:
        assert len((await db.execute(select(FlowStory))).scalars().all()) == 2


# ---------- 队列与派发 ----------


async def test_queue_requires_dev_assign_ai_assignee_and_mapping(service, sf):
    await service.sync_project(await service.get_project("fp1"))
    p = await service.get_project("fp1")
    assert await service.queue(p) == []
    await _assign(sf, "TPYBX-1")
    await _assign(sf, "TPYBX-2", member="human")
    assert [q["key"] for q in await service.queue(p)] == ["TPYBX-1"]
    async with sf() as db:  # 指派给 AI 但无映射的 story：不进队列，单独计数
        db.add(FlowStory(id="orphan", project_id="fp1", title="手工", assignee_id=AI, state=ct.STATE_DEV_ASSIGN))
        await db.commit()
    assert [q["key"] for q in await service.queue(p)] == ["TPYBX-1"]
    assert await service.unmapped_dev_assign(p) == 1


async def test_dispatch_starts_queue_head_and_respects_node_slot(service, sf):
    await service.sync_project(await service.get_project("fp1"))
    sid = await _assign(sf, "TPYBX-1")
    await _assign(sf, "TPYBX-2")
    r = await service.dispatch("fp1", trigger="manual")
    assert r["started"] == ["TPYBX-1"] and r["reason"] == ""
    launch = [c for c in service.fake.calls if "nohup setsid" in c]
    assert len(launch) == 1
    assert "AUTODEV_DELIVER=0" in launch[0] and "HTTP_PROXY=http://p" in launch[0]
    assert "/data/autodev/build/v4/worker.sh TPYBX-1 --repo /data/autodev/repos/cpic" in launch[0]
    async with sf() as db:
        run = (await db.execute(AutodevRun.__table__.select())).mappings().one()
    assert run["status"] == "running" and run["issue_key"] == "TPYBX-1" and run["story_id"] == sid
    assert (await _story(sf, "TPYBX-1")).state == ct.STATE_IN_PROGRESS
    assert (await service.get_project("fp1")).last_dispatched_at is not None

    r2 = await service.dispatch("fp1")  # 节点 slot=1
    assert r2["started"] == [] and r2["reason"].startswith("slot 已满")
    assert len([c for c in service.fake.calls if "nohup setsid" in c]) == 1


async def test_env_materialized_before_launch_only_when_changed(service, sf):
    await service.sync_project(await service.get_project("fp1"))
    await _assign(sf, "TPYBX-1")
    service.fake.env_text = "HCM_BASE_URL=https://old\nHCM_USERNAME=u\nHCM_PASSWORD=p\nHCM_TOKEN=tok\n"
    await service.dispatch("fp1")
    assert len(service.fake.writes) == 1
    cmd, content = service.fake.writes[0]
    assert cmd.startswith("umask 077") and "chmod 600" in cmd
    assert content == "HCM_BASE_URL=https://h\nHCM_USERNAME=u\nHCM_PASSWORD=p\nHCM_TOKEN=tok\n"
    # 写命令在起 worker 之前
    idx_write = next(i for i, c in enumerate(service.fake.calls) if "03_config/.env" in c)
    idx_launch = next(i for i, c in enumerate(service.fake.calls) if "nohup setsid" in c)
    assert idx_write < idx_launch
    # 第二次内容相同：不写
    await service.upsert_project("fp1", {"daily_cap": 9})
    async with sf() as db:
        run = (await db.execute(select(AutodevRun))).scalars().one()
        run.status = "finished"
        await db.commit()
    await _assign(sf, "TPYBX-1")
    await service.dispatch("fp1")
    assert len(service.fake.writes) == 1


async def test_dispatch_refuses_when_credentials_missing(service, sf):
    await service.sync_project(await service.get_project("fp1"))
    await _assign(sf, "TPYBX-1")
    async with sf() as db:
        p = (await db.execute(select(AutodevProject))).scalars().one()
        p.hcm_password_enc = ""
        await db.commit()
    r = await service.dispatch("fp1")
    assert r["started"] == [] and r["reason"] == "凭据缺项：HCM_PASSWORD"
    assert not [c for c in service.fake.calls if "nohup setsid" in c]


async def test_dispatch_specific_key_rules(service, sf):
    await service.sync_project(await service.get_project("fp1"))
    await _assign(sf, "TPYBX-1")
    r = await service.dispatch("fp1", issue_key="TPYBX-2")
    assert r["started"] == [] and "不在队列" in r["reason"]
    await service.dispatch("fp1", issue_key="TPYBX-1")
    r3 = await service.dispatch("fp1", issue_key="TPYBX-1")
    assert r3["reason"] == "该单已在运行"


async def test_launch_failure_finalizes_run_and_returns_story(service, sf):
    await service.sync_project(await service.get_project("fp1"))
    await _assign(sf, "TPYBX-1")
    service.fake.fail_launch = True
    with pytest.raises(AutodevError):
        await service.dispatch("fp1")
    async with sf() as db:
        run = (await db.execute(AutodevRun.__table__.select())).mappings().one()
    assert run["status"] == "finished" and run["outcome"] == "failed" and "启动失败" in run["error"]
    assert (await _story(sf, "TPYBX-1")).state == ct.STATE_DEV_ASSIGN  # failed → 回队列


async def test_dispatch_all_rotates_by_last_dispatched(service, sf):
    await service.upsert_project("fp2", {
        "master_node_id": "node1", "repo_path": "/data/autodev/repos/spic", "jira_project_key": "SPIC",
        "hcm_base_url": "https://h", "hcm_username": "u", "hcm_password": "p",
    })
    await service.sync_project(await service.get_project("fp1"))
    await _assign(sf, "TPYBX-1")
    await _assign(sf, "TPYBX-2")
    # fp1 上次派发在最近，fp2 从未派发 → fp2 先；fp2 队列空，slot 留给 fp1
    async with sf() as db:
        p1 = (await db.execute(select(AutodevProject).where(AutodevProject.project_id == "fp1"))).scalar_one()
        p1.last_dispatched_at = datetime.now()
        await db.commit()
    text = await service.dispatch_all()
    assert text.splitlines()[0].startswith("SPIC: 未派发：队列为空")
    assert "TPYBX: 已派发：TPYBX-1" in text


# ---------- 回收 ----------


async def _dispatched(service, sf, key="TPYBX-1"):
    await service.sync_project(await service.get_project("fp1"))
    sid = await _assign(sf, key)
    await service.dispatch("fp1")
    return sid


async def test_poll_reconciles_summary_usage_and_story(service, sf):
    sid = await _dispatched(service, sf)
    assert await service.poll_once() == 0
    service.fake.rc_text = ("RC=0\n[worker] 结果 rc=0：全绿\n"
                            "[worker] 摘要 /data/autodev/state/runs/TPYBX-1-20260907-120000/summary.json\n"
                            "[worker] 运行目录 /data/autodev/state/runs/TPYBX-1-20260907-120000\n")
    assert await service.poll_once() == 1
    async with sf() as db:
        run = (await db.execute(AutodevRun.__table__.select())).mappings().one()
        comments = (await db.execute(select(FlowComment).where(FlowComment.entity_id == sid))).scalars().all()
    assert run["status"] == "finished" and run["exit_code"] == 0 and run["outcome"] == "delivered"
    assert run["mr_url"] == "http://gl/mr/9" and run["input_tokens"] == 1000 and run["calls"] == 3
    assert run["cost"] == pytest.approx(1000 / 1e6 * 2.0 + 100 / 1e6 * 8.0) and run["error"] == ""
    assert (await _story(sf, "TPYBX-1")).state == ct.STATE_TESTING
    assert len(comments) == 1 and "delivered" in comments[0].content and "http://gl/mr/9" in comments[0].content
    n = len(service.fake.calls)
    assert await service.poll_once() == 0 and len(service.fake.calls) == n

    stats = await service.stats("fp1", days=1)
    assert stats["runs"] == 1 and stats["by_outcome"] == {"delivered": 1} and stats["delivered_tickets"] == 1
    assert stats["total_tokens"] == 1100 and stats["priced"] is True and stats["gate"]["allowed"] == 1
    assert stats["queue"] == 0 and stats["queue_unmapped"] == 0


async def test_poll_missing_summary_and_usage_still_finalizes(service, sf):
    await _dispatched(service, sf)
    service.fake.rc_text = "RC=26\n"
    assert await service.poll_once() == 1
    async with sf() as db:
        run = (await db.execute(AutodevRun.__table__.select())).mappings().one()
    assert run["exit_code"] == 26 and run["outcome"] == "failed" and run["verdict"] == "超时被杀"
    assert "摘要缺失" in run["error"] and "用量缺失" in run["error"] and run["total_tokens"] == 0
    assert (await _story(sf, "TPYBX-1")).state == ct.STATE_DEV_ASSIGN


async def test_poll_verified_leaves_story_untouched(service, sf):
    await _dispatched(service, sf)
    service.fake.rc_text = "RC=15\n[worker] 运行目录 /data/autodev/state/runs/TPYBX-1-20260907-120000\n"
    await service.poll_once()
    assert (await _story(sf, "TPYBX-1")).state == ct.STATE_IN_PROGRESS


async def test_poll_marks_lost_after_deadline(service, sf):
    await _dispatched(service, sf)
    async with sf() as db:
        run = (await db.execute(select(AutodevRun))).scalars().one()
        run.started_at = datetime.now() - svc_mod.LOST_AFTER - timedelta(minutes=1)
        await db.commit()
    assert await service.poll_once() == 1
    async with sf() as db:
        row = (await db.execute(AutodevRun.__table__.select())).mappings().one()
    assert row["status"] == "lost" and row["outcome"] == "failed"


async def test_breaker_blocks_after_consecutive_failures(service, sf):
    await service.upsert_project("fp1", {"failure_threshold": 2, "daily_cap": 10})
    await service.sync_project(await service.get_project("fp1"))
    await _assign(sf, "TPYBX-1")
    async with sf() as db:
        p = (await db.execute(AutodevProject.__table__.select())).mappings().one()
        for i in range(2):
            db.add(AutodevRun(project_id=p["id"], issue_key=f"TPYBX-{90 + i}", status="finished",
                              exit_code=26, outcome=ct.OUTCOME_FAILED))
        await db.commit()
    r = await service.dispatch("fp1")
    assert r["started"] == [] and r["reason"].startswith("熔断")


# ---------- 定时处理器 ----------


async def test_schedule_handlers_call_global_paths(service, sf):
    svc_mod.set_service(service)
    assert "TPYBX: 命中 2 · 新建 2" in await svc_mod.schedule_sync_handler(None, {})
    await _assign(sf, "TPYBX-1")
    assert "TPYBX: 已派发：TPYBX-1" in await svc_mod.schedule_dispatch_handler(None, {"max_starts": 1})
