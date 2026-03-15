"""
NotificationCenter — Delayed IM notification with read-check.

Flow:
1. schedule_notify() creates a notification record (status=pending) and starts a delayed task.
2. After delay_seconds, check if the notification has been cancelled (user read the message).
3. If still pending, send a short IM reminder via the user's preferred channel.
4. If cancelled, do nothing.

Service restart recovery:
- On startup, scan pending notifications and re-evaluate them.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

from openvort.utils.logging import get_logger

log = get_logger("core.notification")

DEFAULT_DELAY_SECONDS = 60
DEFAULT_IM_PRIORITY = ["wecom", "dingtalk", "feishu"]


class NotificationCenter:
    def __init__(self, session_factory, channel_registry=None):
        self._sf = session_factory
        self._registry = channel_registry
        self._pending_tasks: dict[int, asyncio.Task] = {}

    async def schedule_notify(
        self,
        *,
        recipient_id: str,
        source: str,
        source_id: str = "",
        session_id: str = "",
        title: str,
        summary: str = "",
        delay_seconds: int | None = None,
        severity: str = "info",
    ) -> int | None:
        """Create a pending notification and schedule delayed IM delivery."""
        actual_delay = delay_seconds if delay_seconds is not None else DEFAULT_DELAY_SECONDS

        # Bypass delay for error-severity notifications
        if severity == "error":
            actual_delay = 0

        try:
            from openvort.db.models import Notification
            async with self._sf() as db:
                notif = Notification(
                    recipient_id=recipient_id,
                    source=source,
                    source_id=source_id,
                    session_id=session_id,
                    title=title,
                    summary=summary[:500],
                    status="pending",
                )
                db.add(notif)
                await db.commit()
                await db.refresh(notif)
                notif_id = notif.id

            if actual_delay > 0:
                task = asyncio.create_task(self._delayed_check(notif_id, actual_delay, recipient_id))
                self._pending_tasks[notif_id] = task
            else:
                await self._send_im(notif_id, recipient_id, title, summary)

            return notif_id
        except Exception as e:
            log.warning(f"Failed to schedule notification: {e}")
            return None

    async def cancel_pending(self, recipient_id: str, session_id: str) -> int:
        """Cancel all pending notifications for a session (user read the message)."""
        try:
            from sqlalchemy import update
            from openvort.db.models import Notification
            async with self._sf() as db:
                stmt = (
                    update(Notification)
                    .where(
                        Notification.recipient_id == recipient_id,
                        Notification.session_id == session_id,
                        Notification.status == "pending",
                    )
                    .values(status="cancelled", read_at=datetime.utcnow())
                )
                result = await db.execute(stmt)
                await db.commit()
                return result.rowcount
        except Exception as e:
            log.warning(f"Failed to cancel pending notifications: {e}")
            return 0

    async def _delayed_check(self, notif_id: int, delay: int, recipient_id: str):
        """Wait for delay, then check if notification is still pending."""
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        try:
            from sqlalchemy import select
            from openvort.db.models import Notification
            async with self._sf() as db:
                stmt = select(Notification).where(Notification.id == notif_id)
                result = await db.execute(stmt)
                notif = result.scalar_one_or_none()

                if not notif or notif.status != "pending":
                    return

                await self._send_im(notif_id, recipient_id, notif.title, notif.summary)
        except Exception as e:
            log.warning(f"Delayed notification check failed: {e}")
        finally:
            self._pending_tasks.pop(notif_id, None)

    def _is_in_dnd(self, prefs: dict) -> bool:
        """Check if current time is within DND period."""
        dnd_start = prefs.get("dnd_start", "")
        dnd_end = prefs.get("dnd_end", "")
        if not dnd_start or not dnd_end:
            return False
        try:
            now = datetime.now()
            start_h, start_m = map(int, dnd_start.split(":"))
            end_h, end_m = map(int, dnd_end.split(":"))
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            now_minutes = now.hour * 60 + now.minute

            if start_minutes <= end_minutes:
                return start_minutes <= now_minutes < end_minutes
            else:
                return now_minutes >= start_minutes or now_minutes < end_minutes
        except Exception:
            return False

    async def _aggregate_and_send(self, recipient_id: str, prefs: dict):
        """Aggregate pending notifications and send a single IM."""
        try:
            from sqlalchemy import select
            from openvort.db.models import Notification
            cutoff = datetime.utcnow() - timedelta(minutes=5)
            async with self._sf() as db:
                stmt = select(Notification).where(
                    Notification.recipient_id == recipient_id,
                    Notification.status == "pending",
                    Notification.created_at >= cutoff,
                )
                result = await db.execute(stmt)
                pending = result.scalars().all()

            if not pending:
                return

            if len(pending) == 1:
                n = pending[0]
                await self._send_im(n.id, recipient_id, n.title, n.summary)
            else:
                lines = [f"- {n.title}" for n in pending[:5]]
                if len(pending) > 5:
                    lines.append(f"  ...及其他 {len(pending) - 5} 条")
                aggregated_title = f"你有 {len(pending)} 条未读消息"
                aggregated_summary = "\n".join(lines)
                first_id = pending[0].id
                await self._send_im(first_id, recipient_id, aggregated_title, aggregated_summary)
                # Mark remaining as sent
                try:
                    from sqlalchemy import update
                    async with self._sf() as db:
                        for n in pending[1:]:
                            await db.execute(
                                update(Notification).where(Notification.id == n.id).values(status="sent")
                            )
                        await db.commit()
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"Aggregation failed: {e}")

    async def _send_im(self, notif_id: int, recipient_id: str, title: str, summary: str):
        """Send IM notification via the first available channel."""
        if not self._registry:
            log.debug("No channel registry, skipping IM send")
            return

        im_priority = DEFAULT_IM_PRIORITY
        prefs: dict = {}

        try:
            from sqlalchemy import select
            from openvort.contacts.models import Member
            async with self._sf() as db:
                m = await db.get(Member, recipient_id)
                if m and m.notification_prefs:
                    prefs = json.loads(m.notification_prefs) if isinstance(m.notification_prefs, str) else m.notification_prefs
                    im_priority = prefs.get("im_channel_priority", DEFAULT_IM_PRIORITY)
        except Exception:
            pass

        if self._is_in_dnd(prefs):
            log.debug(f"DND active for {recipient_id}, deferring IM send")
            return

        # Get user's platform identities
        try:
            from sqlalchemy import select as _sel
            from openvort.contacts.models import PlatformIdentity
            async with self._sf() as db:
                stmt = _sel(PlatformIdentity.platform, PlatformIdentity.platform_user_id).where(
                    PlatformIdentity.member_id == recipient_id,
                )
                rows = (await db.execute(stmt)).all()
            platform_map = {row[0]: row[1] for row in rows}
        except Exception:
            platform_map = {}

        from openvort.plugin.base import Message as _Msg

        im_content = f"【{title}】\n{summary[:200]}"

        sent = False
        for channel_name in im_priority:
            platform_uid = platform_map.get(channel_name)
            if not platform_uid:
                continue
            ch = self._registry.get_channel(channel_name)
            if not ch or not ch.is_configured():
                continue
            try:
                await ch.send(platform_uid, _Msg(content=im_content, channel=channel_name))
                sent = True
                log.info(f"IM notification sent: {recipient_id} via {channel_name}")
                break
            except Exception as e:
                log.warning(f"IM send failed via {channel_name}: {e}")

        # Update notification status
        try:
            from sqlalchemy import select
            from openvort.db.models import Notification
            async with self._sf() as db:
                stmt = select(Notification).where(Notification.id == notif_id)
                result = await db.execute(stmt)
                notif = result.scalar_one_or_none()
                if notif and notif.status == "pending":
                    notif.status = "sent" if sent else "pending"
                    if sent:
                        notif.im_sent_at = datetime.utcnow()
                        notif.im_channel = channel_name if sent else ""
                    await db.commit()
        except Exception as e:
            log.warning(f"Failed to update notification status: {e}")

    async def recover_on_startup(self):
        """Re-evaluate pending notifications after service restart."""
        try:
            from sqlalchemy import select
            from openvort.db.models import Notification
            now = datetime.utcnow()

            async with self._sf() as db:
                stmt = select(Notification).where(Notification.status == "pending")
                result = await db.execute(stmt)
                pending = result.scalars().all()

            for notif in pending:
                age = (now - notif.created_at).total_seconds() if notif.created_at else 0
                if age >= DEFAULT_DELAY_SECONDS:
                    await self._send_im(notif.id, notif.recipient_id, notif.title, notif.summary)
                else:
                    remaining = max(1, int(DEFAULT_DELAY_SECONDS - age))
                    task = asyncio.create_task(self._delayed_check(notif.id, remaining, notif.recipient_id))
                    self._pending_tasks[notif.id] = task

            if pending:
                log.info(f"Recovered {len(pending)} pending notifications on startup")
        except Exception as e:
            log.warning(f"Failed to recover pending notifications: {e}")


_notification_center: NotificationCenter | None = None


def get_notification_center() -> NotificationCenter | None:
    return _notification_center


def init_notification_center(session_factory, channel_registry=None) -> NotificationCenter:
    global _notification_center
    _notification_center = NotificationCenter(session_factory, channel_registry)
    return _notification_center
