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
    """WebSocket 连接管理器"""

    def __init__(self):
        self._clients: dict[str, ConnectedClient] = {}  # member_id -> client
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, member_id: str, name: str = "") -> None:
        await ws.accept()
        async with self._lock:
            # 踢掉同一用户的旧连接
            old = self._clients.get(member_id)
            if old:
                try:
                    await old.ws.close(code=4001, reason="replaced")
                except Exception:
                    pass
            self._clients[member_id] = ConnectedClient(ws=ws, member_id=member_id, name=name)
        log.info(f"WebSocket 连接: {member_id} ({name})")
        # 广播上线
        await self.broadcast_presence()

    async def disconnect(self, member_id: str) -> None:
        async with self._lock:
            self._clients.pop(member_id, None)
        log.info(f"WebSocket 断开: {member_id}")
        await self.broadcast_presence()

    async def send_to(self, member_id: str, data: dict) -> None:
        """发送消息给指定用户"""
        client = self._clients.get(member_id)
        if client:
            try:
                await client.ws.send_json(data)
            except Exception:
                await self.disconnect(member_id)

    async def broadcast(self, data: dict, exclude: str = "") -> None:
        """广播消息给所有连接的客户端"""
        disconnected = []
        for mid, client in self._clients.items():
            if mid == exclude:
                continue
            try:
                await client.ws.send_json(data)
            except Exception:
                disconnected.append(mid)
        for mid in disconnected:
            await self.disconnect(mid)

    async def broadcast_presence(self) -> None:
        """广播在线状态"""
        online = [
            {"member_id": c.member_id, "name": c.name}
            for c in self._clients.values()
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
            {"member_id": c.member_id, "name": c.name, "connected_at": c.connected_at}
            for c in self._clients.values()
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

    member_id = payload.get("member_id", "")
    name = payload.get("name", "")
    if not member_id:
        await ws.close(code=4003, reason="invalid token")
        return

    await manager.connect(ws, member_id, name)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                client = manager._clients.get(member_id)
                if client:
                    client.last_ping = time.time()
                await ws.send_json({"type": "pong", "ts": time.time()})

            elif msg_type == "typing":
                is_typing = data.get("is_typing", False)
                await manager.broadcast_typing(member_id, is_typing)

            elif msg_type == "notification":
                # 管理员可推送通知给指定用户
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
        await manager.disconnect(member_id)
