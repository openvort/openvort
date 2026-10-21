from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
import unittest

from openvort.core.task_runner import AgentTaskRunner


class ProcessGroupAgent:
    """Owns a child process group but deliberately ignores cancel_event."""

    def __init__(self) -> None:
        self.child: asyncio.subprocess.Process | None = None
        self.cleaned = asyncio.Event()
        self.side_effects = 0

    async def process_stream_web(self, content: str, **kwargs):
        del content, kwargs
        self.child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
            start_new_session=True,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        pgid = os.getpgid(self.child.pid)
        try:
            yield {"type": "tool_use", "name": "test.long_running_process_group"}
            await asyncio.sleep(30)
            self.side_effects += 1
            yield {"type": "tool_progress", "status": "unexpected"}
        finally:
            if self.child.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(pgid, signal.SIGTERM)
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.child.wait(), timeout=0.5)
            if self.child.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(pgid, signal.SIGKILL)
                await self.child.wait()
            self.cleaned.set()


class CompletingAgent:
    def __init__(self, release: asyncio.Event | None = None) -> None:
        self.release = release

    async def process_stream_web(self, content: str, **kwargs):
        del content, kwargs
        if self.release is not None:
            await self.release.wait()
        yield {"type": "text", "text": "done"}


class AgentTaskRunnerCancellationTests(unittest.IsolatedAsyncioTestCase):
    def make_runner(self) -> AgentTaskRunner:
        return AgentTaskRunner(
            session_factory=None,
            cancel_grace_seconds=0.05,
            cancel_force_seconds=1.0,
            stream_close_seconds=0.5,
        )

    async def start(self, runner: AgentTaskRunner, agent, suffix: str = "one") -> str:
        return await runner.start_task(
            session_id=f"session-{suffix}",
            owner_id="owner",
            executor_id="executor",
            source="test",
            agent=agent,
            content="synthetic",
        )

    async def test_force_cancel_closes_stream_and_process_group(self) -> None:
        runner = self.make_runner()
        agent = ProcessGroupAgent()
        task_id = await self.start(runner, agent)
        await asyncio.sleep(0.05)

        self.assertTrue(await runner.cancel_task(task_id))
        task = runner._running[task_id]
        self.assertTrue(task.done)
        self.assertEqual(task.terminal_status, "cancelled")
        self.assertTrue(agent.cleaned.is_set())
        self.assertIsNotNone(agent.child)
        self.assertIsNotNone(agent.child.returncode)
        self.assertEqual(agent.side_effects, 0)
        self.assertEqual(runner.get_active_tasks("owner"), [])
        self.assertEqual(sum(e["type"] == "interrupted" for e in task.event_buffer), 1)
        self.assertEqual(sum(e["type"] == "done" for e in task.event_buffer), 1)

    async def test_repeated_cancel_is_idempotent(self) -> None:
        runner = self.make_runner()
        agent = ProcessGroupAgent()
        task_id = await self.start(runner, agent, "repeat")
        await asyncio.sleep(0.05)

        first, second = await asyncio.gather(
            runner.cancel_task(task_id),
            runner.cancel_task(task_id),
        )
        task = runner._running[task_id]
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(sum(e["type"] == "interrupted" for e in task.event_buffer), 1)
        self.assertEqual(sum(e["type"] == "done" for e in task.event_buffer), 1)

    async def test_cancel_complete_race_has_one_terminal_state(self) -> None:
        runner = self.make_runner()
        release = asyncio.Event()
        task_id = await self.start(runner, CompletingAgent(release), "race")
        release.set()
        cancel_result = await runner.cancel_task(task_id)
        await runner._running[task_id].asyncio_task

        task = runner._running[task_id]
        self.assertIn(task.terminal_status, {"completed", "cancelled"})
        self.assertEqual(sum(e["type"] == "done" for e in task.event_buffer), 1)
        self.assertLessEqual(sum(e["type"] == "interrupted" for e in task.event_buffer), 1)
        self.assertEqual(cancel_result, task.terminal_status == "cancelled")
        self.assertEqual(runner.get_active_tasks("owner"), [])

    async def test_completed_task_rejects_cancel(self) -> None:
        runner = self.make_runner()
        task_id = await self.start(runner, CompletingAgent(), "complete")
        await runner._running[task_id].asyncio_task

        self.assertFalse(await runner.cancel_task(task_id))
        task = runner._running[task_id]
        self.assertEqual(task.terminal_status, "completed")
        self.assertFalse(any(e["type"] == "interrupted" for e in task.event_buffer))
        self.assertEqual(sum(e["type"] == "done" for e in task.event_buffer), 1)


if __name__ == "__main__":
    unittest.main()
