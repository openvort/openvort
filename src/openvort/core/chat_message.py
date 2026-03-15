"""
Chat message persistence helpers.

Provides write_chat_message() for consistent message recording across
chat, scheduled tasks, and webhook sources. Manages unread_count on
chat_sessions alongside writing to chat_messages.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from openvort.db.models import ChatMessage, ChatSession
from openvort.utils.logging import get_logger

log = get_logger("core.chat_message")


async def write_chat_message(
    db: AsyncSession,
    *,
    session_id: str,
    owner_id: str,
    sender_type: str,
    sender_id: str = "",
    content: str = "",
    metadata_json: str = "{}",
    source: str = "chat",
    is_read: bool = False,
    increment_unread: bool = False,
) -> ChatMessage:
    """Write a single message record and optionally bump unread_count.

    Args:
        increment_unread: If True, increment chat_sessions.unread_count by 1.
            Typically True for assistant messages the user hasn't seen yet.
    """
    msg = ChatMessage(
        session_id=session_id,
        owner_id=owner_id,
        sender_type=sender_type,
        sender_id=sender_id,
        content=content,
        metadata_json=metadata_json,
        source=source,
        is_read=is_read,
    )
    db.add(msg)

    if increment_unread:
        stmt = (
            update(ChatSession)
            .where(
                ChatSession.session_id == session_id,
                ChatSession.user_id == owner_id,
                ChatSession.channel == "web",
            )
            .values(unread_count=ChatSession.unread_count + 1)
        )
        await db.execute(stmt)

    await db.flush()
    return msg


async def mark_session_read(
    db: AsyncSession,
    *,
    owner_id: str,
    session_id: str,
) -> int:
    """Mark all unread messages in a session as read and reset unread_count.

    Returns the number of messages marked as read.
    """
    from sqlalchemy import update as sa_update

    result = await db.execute(
        sa_update(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.owner_id == owner_id,
            ChatMessage.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    marked = result.rowcount

    await db.execute(
        sa_update(ChatSession)
        .where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == owner_id,
            ChatSession.channel == "web",
        )
        .values(unread_count=0)
    )

    await db.commit()
    return marked


async def push_unread_update(owner_id: str, session_id: str) -> None:
    """Push unread_update via WebSocket after DB commit.

    Call this AFTER committing the transaction that incremented unread_count.
    """
    try:
        from openvort.web.ws import manager as ws_manager
        from openvort.web.deps import get_db_session_factory

        sf = get_db_session_factory()
        if not sf:
            return
        async with sf() as db:
            counts = await get_unread_counts(db, owner_id=owner_id)
        new_count = counts.get(session_id, 0)
        await ws_manager.send_to(owner_id, {
            "type": "unread_update",
            "session_id": session_id,
            "count": new_count,
        })
    except Exception:
        pass


async def get_unread_counts(
    db: AsyncSession,
    *,
    owner_id: str,
) -> dict[str, int]:
    """Return {session_id: unread_count} for all sessions with unread > 0."""
    stmt = (
        select(ChatSession.session_id, ChatSession.unread_count)
        .where(
            ChatSession.user_id == owner_id,
            ChatSession.channel == "web",
            ChatSession.unread_count > 0,
        )
    )
    result = await db.execute(stmt)
    return {row.session_id: row.unread_count for row in result}
