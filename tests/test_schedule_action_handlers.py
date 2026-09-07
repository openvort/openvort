"""ScheduleJob 的非 agent action_type 走 ACTION_HANDLERS，不再要求 prompt、不经 Agent。"""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from openvort.core.services import schedule_service as ss
from openvort.db.engine import Base
from openvort.db.models import ScheduleJob


@pytest.fixture
async def sf():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [Base.metadata.tables[t] for t in ("schedule_jobs", "work_assignments")]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


class _Scheduler:
    def remove(self, job_id):
        pass


async def _make_service(sf, monkeypatch):
    svc = ss.ScheduleService(sf, _Scheduler(), agent_runtime=None, notify_fn=None)

    async def fake_ctx(job):
        return SimpleNamespace(member=None, user_id="u1")

    async def no_member(_):
        return None

    monkeypatch.setattr(svc, "_build_executor_context", fake_ctx)
    monkeypatch.setattr(svc._contacts_service, "get_member", no_member)
    return svc


async def _seed_job(sf, action_type, config):
    job = ScheduleJob(job_id="sched_test", name="t", owner_id="m1", creator_id="m1", schedule_type="interval",
                      schedule="60", action_type=action_type, action_config=json.dumps(config))
    async with sf() as db:
        db.add(job)
        await db.commit()
        await db.refresh(job)
    return job


async def test_registered_handler_runs_without_prompt_and_persists_result(sf, monkeypatch):
    seen = {}

    async def handler(job, config):
        seen["job"] = job.job_id
        seen["config"] = config
        return "已派发：X-1"

    monkeypatch.setitem(ss.ACTION_HANDLERS, "autodev_dispatch", handler)
    svc = await _make_service(sf, monkeypatch)
    job = await _seed_job(sf, "autodev_dispatch", {"project_id": "fp1"})

    assert await svc._execute_job(job) == "已派发：X-1"
    assert seen == {"job": "sched_test", "config": {"project_id": "fp1"}}
    async with sf() as db:
        row = (await db.execute(select(ScheduleJob).where(ScheduleJob.job_id == "sched_test"))).scalar_one()
    assert row.last_status == "success" and row.last_result == "已派发：X-1" and row.last_run_at is not None


async def test_handler_exception_marks_failed(sf, monkeypatch):
    async def boom(job, config):
        raise RuntimeError("master 不可达")

    monkeypatch.setitem(ss.ACTION_HANDLERS, "autodev_dispatch", boom)
    svc = await _make_service(sf, monkeypatch)
    job = await _seed_job(sf, "autodev_dispatch", {"project_id": "fp1"})
    assert await svc._execute_job(job) == "master 不可达"
    async with sf() as db:
        row = (await db.execute(select(ScheduleJob).where(ScheduleJob.job_id == "sched_test"))).scalar_one()
    assert row.last_status == "failed"


async def test_agent_chat_still_requires_prompt(sf, monkeypatch):
    svc = await _make_service(sf, monkeypatch)
    job = await _seed_job(sf, "agent_chat", {})
    with pytest.raises(ValueError, match="prompt"):
        await svc._execute_job(job)


async def test_unknown_action_type_without_handler_is_failed_not_dispatched(sf, monkeypatch):
    svc = await _make_service(sf, monkeypatch)
    job = await _seed_job(sf, "something_else", {"prompt": "x"})
    text = await svc._execute_job(job)
    assert "不支持的 action_type" in text
