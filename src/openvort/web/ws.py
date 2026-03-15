"""
WebSocket 实时通信

提供 typing indicator、在线状态（presence）和实时通知推送。
与现有 SSE chat 并存，前端可选择使用 WebSocket 或 SSE。
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from openvort.utils.logging import get_logger
from openvort.web.auth import verify_token

log = get_logger("web.ws")

ws_router = APIRouter()


@dataclass
class ConnectedClient:
    """已连接的 WebSocket 客户端"""
    ws: WebSocket
    member_id: str
    name: str = ""
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)


class ConnectionManager:
    """WebSocket 连接管理器（支持同一用户多标签页连接）"""

    def __init__(self):
        self._clients: dict[str, list[ConnectedClient]] = {}  # member_id -> [clients]
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, member_id: str, name: str = "") -> ConnectedClient:
        await ws.accept()
        client = ConnectedClient(ws=ws, member_id=member_id, name=name)
        async with self._lock:
            if member_id not in self._clients:
                self._clients[member_id] = []
            self._clients[member_id].append(client)
        log.info(f"WebSocket 连接: {member_id} ({name}), 当前连接数={len(self._clients.get(member_id, []))}")
        await self.broadcast_presence()
        return client

    async def disconnect_client(self, client: ConnectedClient) -> None:
        """断开单个客户端连接"""
        member_id = client.member_id
        async with self._lock:
            clients = self._clients.get(member_id, [])
            try:
                clients.remove(client)
            except ValueError:
                pass
            if not clients:
                self._clients.pop(member_id, None)
        remaining = len(self._clients.get(member_id, []))
        log.info(f"WebSocket 断开: {member_id}, 剩余连接数={remaining}")
        await self.broadcast_presence()

    async def disconnect(self, member_id: str) -> None:
        """断开用户的所有连接（兼容旧调用）"""
        async with self._lock:
            clients = self._clients.pop(member_id, [])
        for c in clients:
            try:
                await c.ws.close()
            except Exception:
                pass
        log.info(f"WebSocket 断开全部: {member_id}")
        await self.broadcast_presence()

    async def send_to(self, member_id: str, data: dict) -> None:
        """发送消息给指定用户的所有连接"""
        clients = self._clients.get(member_id, [])
        dead: list[ConnectedClient] = []
        for client in clients:
            try:
                await client.ws.send_json(data)
            except Exception:
                dead.append(client)
        for c in dead:
            await self.disconnect_client(c)

    async def broadcast(self, data: dict, exclude: str = "") -> None:
        """广播消息给所有连接的客户端"""
        dead: list[ConnectedClient] = []
        for mid, clients in self._clients.items():
            if mid == exclude:
                continue
            for client in clients:
                try:
                    await client.ws.send_json(data)
                except Exception:
                    dead.append(client)
        for c in dead:
            await self.disconnect_client(c)

    async def broadcast_presence(self) -> None:
        """广播在线状态"""
        online = [
            {"member_id": mid, "name": clients[0].name}
            for mid, clients in self._clients.items()
            if clients
        ]
        await self.broadcast({"type": "presence", "online": online})

    async def broadcast_typing(self, member_id: str, is_typing: bool) -> None:
        """广播 typing 状态"""
        await self.broadcast(
            {"type": "typing", "member_id": member_id, "is_typing": is_typing},
            exclude=member_id,
        )

    def get_online_members(self) -> list[dict]:
        """获取在线成员列表"""
        return [
            {"member_id": mid, "name": clients[0].name, "connected_at": clients[0].connected_at}
            for mid, clients in self._clients.items()
            if clients
        ]

    @property
    def online_count(self) -> int:
        return len(self._clients)


# 全局连接管理器
manager = ConnectionManager()


@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query("")):
    """WebSocket 入口

    连接时通过 query param token 认证。
    消息格式: {"type": "typing|ping|chat", ...}
    """
    # 认证
    payload = verify_token(token)
    if not payload:
        await ws.close(code=4003, reason="unauthorized")
        return

    member_id = payload.get("sub", "") or payload.get("member_id", "")
    name = payload.get("name", "")
    if not member_id:
        await ws.close(code=4003, reason="invalid token")
        return

    client = await manager.connect(ws, member_id, name)

    # Push offline summary on connect
    try:
        from openvort.web.deps import get_db_session_factory
        sf = get_db_session_factory()
        if sf:
            from sqlalchemy import select, func as sa_func
            from openvort.db.models import ChatMessage, ChatSession
            async with sf() as db:
                unread_stmt = (
                    select(
                        ChatMessage.session_id,
                        ChatMessage.content,
                        ChatMessage.source,
                    )
                    .where(
                        ChatMessage.owner_id == member_id,
                        ChatMessage.is_read == False,  # noqa: E712
                        ChatMessage.sender_type == "assistant",
                    )
                    .order_by(ChatMessage.created_at.desc())
                    .limit(10)
                )
                result = await db.execute(unread_stmt)
                unread_msgs = result.all()

                if unread_msgs:
                    highlights = []
                    for msg in unread_msgs[:5]:
                        preview = (msg.content or "")[:80]
                        if msg.source == "schedule":
                            highlights.append(preview)
                        else:
                            highlights.append(preview)

                    await ws.send_json({
                        "type": "offline_summary",
                        "unreads": len(unread_msgs),
                        "highlights": highlights,
                    })
    except Exception as e:
        log.debug(f"Failed to push offline summary: {e}")

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                client.last_ping = time.time()
                await ws.send_json({"type": "pong", "ts": time.time()})

            elif msg_type == "typing":
                is_typing = data.get("is_typing", False)
                await manager.broadcast_typing(member_id, is_typing)

            elif msg_type == "notification":
                target = data.get("target", "")
                content = data.get("content", "")
                if target and content:
                    await manager.send_to(target, {
                        "type": "notification",
                        "from": member_id,
                        "content": content,
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning(f"WebSocket 异常 ({member_id}): {e}")
    finally:
        await manager.disconnect_client(client)
