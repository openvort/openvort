"""Regression coverage for terminal publication while persistence is slow."""

import asyncio

from openvort.core.task_runner import AgentTaskRunner


class SlowPersistenceRunner(AgentTaskRunner):
    def __init__(self):
        super().__init__(cancel_grace_seconds=0.01, cancel_force_seconds=0.5)
        self.persisting = asyncio.Event()
        self.release = asyncio.Event()

    async def _mark_completed(self, rt, status, summary=""):
        self.persisting.set()
        await self.release.wait()


class CooperativeAgent:
    async def process_stream_web(self, content, *, cancel_event, **kwargs):
        await cancel_event.wait()
        if False:
            yield {}


async def start(runner):
    return await runner.start_task(
        session_id="test-session", owner_id="test-owner",
        agent=CooperativeAgent(), content="test",
    )


async def test_subscriber_receives_done_during_slow_persistence():
    runner = SlowPersistenceRunner()
    tid = await start(runner)
    rt = runner._running[tid]
    rt.cancel_event.set()
    await runner.persisting.wait()

    async def collect():
        return [event async for event in runner.subscribe(tid)]

    consumer = asyncio.create_task(collect())
    await asyncio.sleep(0)
    runner.release.set()
    await rt.asyncio_task
    events = await consumer
    assert sum(event["type"] == "done" for event in events) == 1


async def test_cancel_does_not_interrupt_terminal_persistence():
    runner = SlowPersistenceRunner()
    tid = await start(runner)
    rt = runner._running[tid]
    cancellation = asyncio.create_task(runner.cancel_task(tid))
    await runner.persisting.wait()
    await asyncio.sleep(0.03)
    runner.release.set()
    try:
        assert await cancellation is True
    finally:
        await asyncio.gather(rt.asyncio_task, return_exceptions=True)
    assert sum(event["type"] == "done" for event in rt.event_buffer) == 1
    assert runner.get_active_tasks("test-owner") == []
