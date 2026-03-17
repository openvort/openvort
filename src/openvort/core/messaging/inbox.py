"""
IM Inbox Service

Distributed message dedup via PostgreSQL atomic INSERT ON CONFLICT.
Also provides shared consume cursors for poll-based channels.
"""

from sqlalchemy import text

from openvort.utils.logging import get_logger

log = get_logger("core.inbox")


class InboxService:
    """Cross-instance IM message dedup backed by PostgreSQL.

    Each inbound message is "claimed" via INSERT ... ON CONFLICT DO NOTHING.
    Only the instance whose INSERT succeeds (rowcount > 0) should process the message.
    """

    def __init__(self, session_factory):
        self._sf = session_factory

    # ---- message dedup ----

    async def try_claim(self, channel: str, msg_id: str) -> bool:
        """Atomically try to claim a message.

        Returns True if this instance should process the message.
        Returns True when msg_id is empty (cannot deduplicate).
        """
        if not msg_id:
            return True
        try:
            async with self._sf() as db:
                result = await db.execute(
                    text(
                        "INSERT INTO im_inbox (channel, msg_id, status, created_at) "
                        "VALUES (:channel, :msg_id, 'claimed', NOW()) "
                        "ON CONFLICT (channel, msg_id) DO NOTHING"
                    ),
                    {"channel": channel, "msg_id": msg_id},
                )
                await db.commit()
                claimed = result.rowcount > 0
                if not claimed:
                    log.debug(f"[{channel}] msg already claimed: {msg_id}")
                return claimed
        except Exception as e:
            log.warning(f"[{channel}] try_claim failed, allowing through: {e}")
            return True

    async def mark_done(self, channel: str, msg_id: str) -> None:
        if not msg_id:
            return
        try:
            async with self._sf() as db:
                await db.execute(
                    text(
                        "UPDATE im_inbox SET status = 'done' "
                        "WHERE channel = :channel AND msg_id = :msg_id"
                    ),
                    {"channel": channel, "msg_id": msg_id},
                )
                await db.commit()
        except Exception as e:
            log.warning(f"[{channel}] mark_done failed: {e}")

    async def mark_failed(self, channel: str, msg_id: str, error: str = "") -> None:
        if not msg_id:
            return
        try:
            async with self._sf() as db:
                await db.execute(
                    text(
                        "UPDATE im_inbox SET status = 'failed', error = :error "
                        "WHERE channel = :channel AND msg_id = :msg_id"
                    ),
                    {"channel": channel, "msg_id": msg_id, "error": error[:1000]},
                )
                await db.commit()
        except Exception as e:
            log.warning(f"[{channel}] mark_failed failed: {e}")

    # ---- shared consume cursors ----

    async def get_cursor(self, key: str) -> int:
        """Read a shared cursor value (e.g. poll-db last_id)."""
        try:
            async with self._sf() as db:
                result = await db.execute(
                    text("SELECT value FROM im_cursors WHERE key = :key"),
                    {"key": key},
                )
                row = result.scalar_one_or_none()
                return row or 0
        except Exception as e:
            log.warning(f"get_cursor({key}) failed: {e}")
            return 0

    async def set_cursor(self, key: str, value: int) -> None:
        """Write a shared cursor value (upsert)."""
        try:
            async with self._sf() as db:
                await db.execute(
                    text(
                        "INSERT INTO im_cursors (key, value, updated_at) "
                        "VALUES (:key, :value, NOW()) "
                        "ON CONFLICT (key) DO UPDATE SET value = :value, updated_at = NOW()"
                    ),
                    {"key": key, "value": value},
                )
                await db.commit()
        except Exception as e:
            log.warning(f"set_cursor({key}, {value}) failed: {e}")

    # ---- cleanup ----

    async def cleanup(self, max_age_hours: int = 24) -> int:
        """Delete inbox entries older than max_age_hours. Returns rows deleted."""
        try:
            async with self._sf() as db:
                result = await db.execute(
                    text(
                        "DELETE FROM im_inbox "
                        "WHERE created_at < NOW() - MAKE_INTERVAL(hours => :hours)"
                    ),
                    {"hours": max_age_hours},
                )
                await db.commit()
                deleted = result.rowcount
                if deleted:
                    log.info(f"im_inbox cleanup: deleted {deleted} rows older than {max_age_hours}h")
                return deleted
        except Exception as e:
            log.warning(f"im_inbox cleanup failed: {e}")
            return 0
