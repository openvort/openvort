"""
AgentTaskRunner — Async task execution engine.

Decouples Agent execution from SSE lifecycle so that:
- Users can leave the Chat page while the AI keeps working.
- SSE is just a "viewer window" that can disconnect and reconnect.
- Tasks are tracked in the agent_tasks table for visibility.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator

from openvort.utils.logging import get_logger

log = get_logger("core.task_runner")

MAX_EVENT_BUFFER = 200
CLEANUP_DELAY = 300  # seconds to keep event buffer after completion


@dataclass
class RunningTask:
    task_id: str
    session_id: str
    owner_id: str
    executor_id: str
    source: str  # chat / schedule
    asyncio_task: asyncio.Task[Any] | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    event_buffer: deque = field(default_factory=lambda: deque(maxlen=MAX_EVENT_BUFFER))
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    done: bool = False
    completed_at: float = 0.0
    inject_queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class AgentTaskRunner:
    """Manages background Agent task execution."""

    def __init__(self, session_factory=None):
        self._running: dict[str, RunningTask] = {}
        self._session_index: dict[str, str] = {}  # session_id -> task_id (for running tasks only)
        self._sf = session_factory

    def get_running_task_for_session(self, session_id: str) -> RunningTask | None:
        tid = self._session_index.get(session_id)
        if tid:
            t = self._running.get(tid)
            if t and not t.done:
                return t
        return None

    async def start_task(
        self,
        *,
        session_id: str,
        owner_id: str,
        executor_id: str = "",
        source: str = "chat",
        source_id: str = "",
        agent,
        content: str,
        images: list[dict] | None = None,
        target_type: str = "ai",
        target_id: str = "",
    ) -> str:
        existing = self.get_running_task_for_session(session_id)
        if existing:
            await self.inject_message(existing.task_id, content)
            return existing.task_id

        task_id = uuid.uuid4().hex
        rt = RunningTask(
            task_id=task_id,
            session_id=session_id,
            owner_id=owner_id,
            executor_id=executor_id,
            source=source,
        )
        self._running[task_id] = rt
        self._session_index[session_id] = task_id

        if self._sf:
            try:
                from openvort.db.models import AgentTask
                async with self._sf() as db:
                    db.add(AgentTask(
                        id=task_id,
                        session_id=session_id,
                        owner_id=owner_id,
                        executor_id=executor_id,
                        source=source,
                        source_id=source_id,
                        status="running",
                        started_at=datetime.utcnow(),
                    ))
                    await db.commit()
            except Exception as e:
                log.warning(f"Failed to create agent_task record: {e}")

        async def _run():
            try:
                await self._execute(rt, agent, content, images, owner_id, session_id, target_type, target_id)
            except Exception as e:
                log.error(f"Task {task_id} failed: {e}")
                self._emit(rt, {"type": "server_error", "data": str(e)})
                await self._mark_completed(rt, "failed", str(e))
            finally:
                rt.done = True
                self._emit(rt, {"type": "done", "data": "ok"})
                self._session_index.pop(session_id, None)
                asyncio.get_event_loop().call_later(CLEANUP_DELAY, lambda: self._running.pop(task_id, None))

        rt.asyncio_task = asyncio.create_task(_run())
        return task_id

    async def _execute(
        self, rt: RunningTask, agent, content, images, owner_id, session_id, target_type, target_id,
    ):
        cancel = rt.cancel_event

        self._emit(rt, {"type": "thinking", "data": "start"})

        cancel_notified = False
        async for event in agent.process_stream_web(
            content,
            member_id=owner_id,
            images=images or [],
            session_id=session_id,
            cancel_event=cancel,
            target_type=target_type,
            target_id=target_id,
        ):
            if cancel.is_set():
                if not cancel_notified:
                    self._emit(rt, {"type": "interrupted", "data": "aborted"})
                    cancel_notified = True
                event_type = event.get("type", "")
                if event_type == "text":
                    self._emit(rt, {"type": "text", "data": event["text"]})
                continue

            event_type = event.get("type", "")
            if event_type == "text":
                self._emit(rt, {"type": "text", "data": event["text"]})
            elif event_type in ("tool_use", "tool_output", "tool_progress", "tool_result", "usage", "action_button"):
                import json
                self._emit(rt, {"type": event_type, "data": json.dumps(event, ensure_ascii=False)})

        if cancel.is_set():
            if not cancel_notified:
                self._emit(rt, {"type": "interrupted", "data": "aborted"})
            await self._mark_completed(rt, "cancelled")
            return

        # Persist result
        try:
            from openvort.web.deps import get_session_store, get_db_session_factory
            from openvort.core.chat_message import write_chat_message

            session_store = get_session_store()
            sf = get_db_session_factory()
            if sf and session_store:
                all_msgs = await session_store.get_messages("web", owner_id, session_id)
                assistant_text = ""
                for m in reversed(all_msgs):
                    if m.get("role") == "assistant":
                        c = m.get("content", "")
                        if isinstance(c, str):
                            assistant_text = c
                        elif isinstance(c, list):
                            assistant_text = " ".join(
                                b.get("text", "") for b in c
                                if isinstance(b, dict) and b.get("type") == "text"
                            )
                        break

                async with sf() as db:
                    await write_chat_message(
                        db, session_id=session_id, owner_id=owner_id,
                        sender_type="user", sender_id=owner_id,
                        content=content, source=rt.source, is_read=True,
                    )
                    if assistant_text:
                        await write_chat_message(
                            db, session_id=session_id, owner_id=owner_id,
                            sender_type="assistant", sender_id=rt.executor_id,
                            content=assistant_text.strip(), source=rt.source, is_read=True,
                        )
                    await db.commit()
        except Exception as e:
            log.warning(f"Failed to persist task result: {e}")

        await self._mark_completed(rt, "completed")

        # Push WebSocket notifications
        try:
            from openvort.web.ws import manager as ws_mgr
            await ws_mgr.send_to(owner_id, {
                "type": "task_completed",
                "task_id": rt.task_id,
                "session_id": session_id,
                "executor_id": rt.executor_id,
            })
        except Exception:
            pass

    def _emit(self, rt: RunningTask, event: dict):
        rt.event_buffer.append(event)
        dead = []
        for q in rt.subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            rt.subscribers.remove(q)

    async def subscribe(self, task_id: str) -> AsyncIterator[dict]:
        rt = self._running.get(task_id)
        if not rt:
            return

        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        rt.subscribers.append(q)

        for evt in rt.event_buffer:
            yield evt

        try:
            while not rt.done or not q.empty():
                try:
                    event = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield event
                    if event.get("type") == "done":
                        break
                except asyncio.TimeoutError:
                    continue
        finally:
            if q in rt.subscribers:
                rt.subscribers.remove(q)

    async def cancel_task(self, task_id: str) -> bool:
        rt = self._running.get(task_id)
        if not rt or rt.done:
            return False
        rt.cancel_event.set()
        return True

    async def inject_message(self, task_id: str, content: str) -> bool:
        rt = self._running.get(task_id)
        if not rt or rt.done:
            return False
        await rt.inject_queue.put(content)
        return True

    def get_active_tasks(self, owner_id: str) -> list[dict]:
        return [
            {
                "task_id": rt.task_id,
                "session_id": rt.session_id,
                "executor_id": rt.executor_id,
                "source": rt.source,
                "done": rt.done,
            }
            for rt in self._running.values()
            if rt.owner_id == owner_id and not rt.done
        ]

    async def _mark_completed(self, rt: RunningTask, status: str, summary: str = ""):
        rt.completed_at = time.time()
        if self._sf:
            try:
                from sqlalchemy import select
                from openvort.db.models import AgentTask
                async with self._sf() as db:
                    stmt = select(AgentTask).where(AgentTask.id == rt.task_id)
                    result = await db.execute(stmt)
                    row = result.scalar_one_or_none()
                    if row:
                        row.status = status
                        row.result_summary = summary[:2000]
                        row.completed_at = datetime.utcnow()
                        await db.commit()
            except Exception as e:
                log.warning(f"Failed to update agent_task status: {e}")

    async def recover_on_startup(self):
        """Mark any orphaned running tasks as failed on service restart."""
        if not self._sf:
            return
        try:
            from sqlalchemy import select, update
            from openvort.db.models import AgentTask
            async with self._sf() as db:
                stmt = (
                    update(AgentTask)
                    .where(AgentTask.status.in_(["pending", "running"]))
                    .values(status="failed", result_summary="Service restarted")
                )
                result = await db.execute(stmt)
                await db.commit()
                if result.rowcount:
                    log.info(f"Recovered {result.rowcount} orphaned agent tasks on startup")
        except Exception as e:
            log.warning(f"Failed to recover orphaned tasks: {e}")


_task_runner: AgentTaskRunner | None = None


def get_task_runner() -> AgentTaskRunner | None:
    return _task_runner


def init_task_runner(session_factory=None) -> AgentTaskRunner:
    global _task_runner
    _task_runner = AgentTaskRunner(session_factory)
    return _task_runner
