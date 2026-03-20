"""VortFlow IM notification aggregator — batches notifications per user to prevent IM spam."""

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass

from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.aggregator")

IM_PRIORITY = ["wecom", "dingtalk", "feishu"]


async def send_im_to_member(member_id: str, text: str) -> None:
    """Send IM text to a member via first available channel (lazy resolution)."""
    log.info("send_im_to_member called: member=%s, text_len=%d", member_id, len(text))
    try:
        from openvort.db.engine import get_session_factory
        from openvort.core.services.notification import get_notification_center

        nc = get_notification_center()
        registry = nc._registry if nc else None
        if not registry:
            log.warning("IM send skipped for %s: no channel registry (nc=%s)", member_id, nc is not None)
            return

        sf = get_session_factory()

        im_priority = IM_PRIORITY
        try:
            from openvort.contacts.models import Member as _Member
            async with sf() as db:
                m = await db.get(_Member, member_id)
                if m and m.notification_prefs:
                    prefs = json.loads(m.notification_prefs) if isinstance(m.notification_prefs, str) else m.notification_prefs
                    vf_prefs = prefs.get("vortflow", {})
                    if not vf_prefs.get("im", True):
                        return
                    im_priority = prefs.get("im_channel_priority", IM_PRIORITY)
        except Exception:
            pass

        try:
            from sqlalchemy import select as _sel
            from openvort.contacts.models import PlatformIdentity
            async with sf() as db:
                rows = (await db.execute(
                    _sel(PlatformIdentity.platform, PlatformIdentity.platform_user_id)
                    .where(PlatformIdentity.member_id == member_id)
                )).all()
            platform_map = {r[0]: r[1] for r in rows}
        except Exception:
            platform_map = {}

        if not platform_map:
            log.warning("IM send skipped for %s: no platform identities", member_id)
            return

        from openvort.plugin.base import Message as _Msg

        for channel_name in im_priority:
            platform_uid = platform_map.get(channel_name)
            if not platform_uid:
                continue
            ch = registry.get_channel(channel_name)
            if not ch or not ch.is_configured():
                log.debug("Channel %s not available for %s", channel_name, member_id)
                continue
            try:
                await ch.send(platform_uid, _Msg(content=text, channel=channel_name))
                log.info("VortFlow IM sent to %s via %s", member_id, channel_name)
                return
            except Exception as exc:
                log.warning("VortFlow IM send failed via %s: %s", channel_name, exc)
    except Exception as exc:
        log.warning("send_im_to_member error for %s: %s", member_id, exc)


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

        if batch:
            log.info("Flushing %d user(s), sender=%s", len(batch), self._channel_sender is not None)

        for member_id, payloads in batch.items():
            if not payloads:
                continue
            text = self._format_batch(payloads)
            try:
                if self._channel_sender:
                    await self._channel_sender(member_id, text)
                else:
                    log.warning("IM flush skipped: no channel_sender set")
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
