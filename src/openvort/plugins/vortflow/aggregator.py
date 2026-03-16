"""VortFlow IM notification aggregator — batches notifications per user to prevent IM spam."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass

from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.aggregator")


@dataclass
class NotificationPayload:
    title: str
    summary: str
    source_id: str = ""
    entity_type: str = ""
    entity_id: str = ""


class NotificationAggregator:
    """Per-user notification queue with timed batch flush.

    Enqueued notifications are held in memory and flushed every FLUSH_INTERVAL
    seconds.  All pending items for a given user are merged into a single IM
    message to avoid flooding the channel.
    """

    FLUSH_INTERVAL = 30  # seconds

    def __init__(self):
        self._buffer: dict[str, list[NotificationPayload]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._channel_sender = None  # callable(member_id, message) -> coroutine

    def set_channel_sender(self, sender):
        """Inject the IM send function. Expected signature: async def sender(member_id: str, text: str)"""
        self._channel_sender = sender

    async def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._flush_loop())
            log.info("VortFlow notification aggregator started (flush every %ds)", self.FLUSH_INTERVAL)

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._flush()  # drain remaining

    async def enqueue(self, member_id: str, payload: NotificationPayload):
        async with self._lock:
            self._buffer[member_id].append(payload)

    async def _flush_loop(self):
        try:
            while True:
                await asyncio.sleep(self.FLUSH_INTERVAL)
                await self._flush()
        except asyncio.CancelledError:
            pass

    async def _flush(self):
        async with self._lock:
            batch = dict(self._buffer)
            self._buffer.clear()

        for member_id, payloads in batch.items():
            if not payloads:
                continue
            text = self._format_batch(payloads)
            try:
                if self._channel_sender:
                    await self._channel_sender(member_id, text)
            except Exception:
                log.warning("Failed to send IM notification to %s", member_id, exc_info=True)

    @staticmethod
    def _format_batch(payloads: list[NotificationPayload]) -> str:
        if len(payloads) == 1:
            p = payloads[0]
            return f"{p.title}\n{p.summary}"
        lines = [f"你有 {len(payloads)} 条 VortFlow 通知："]
        for p in payloads[:10]:
            lines.append(f"  - {p.title}")
        if len(payloads) > 10:
            lines.append(f"  ... 还有 {len(payloads) - 10} 条")
        return "\n".join(lines)


# Module-level singleton
im_aggregator = NotificationAggregator()
