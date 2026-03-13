"""
Remote work node management.

Provides CRUD, connection testing, and instruction sending
for remote execution nodes via pluggable executor backends.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from openvort.core.remote_executor import get_executor
from openvort.db.models import RemoteNode
from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

log = get_logger("core.remote_node")


def _encrypt(plaintext: str) -> str:
    """Encrypt token using VortGit's Fernet key (shared infrastructure)."""
    if not plaintext:
        return ""
    try:
        from openvort.plugins.vortgit.crypto import encrypt_token
        return encrypt_token(plaintext)
    except Exception:
        return plaintext


def _decrypt(ciphertext: str) -> str:
    """Decrypt token using VortGit's Fernet key."""
    if not ciphertext:
        return ""
    try:
        from openvort.plugins.vortgit.crypto import decrypt_token
        return decrypt_token(ciphertext)
    except Exception as e:
        log.warning(f"Token decryption failed (returning raw value): {type(e).__name__}: {e}")
        return ciphertext


class RemoteNodeService:
    """Manage remote execution nodes."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    # ---- CRUD ----

    async def list_nodes(self) -> list[dict]:
        async with self._sf() as db:
            result = await db.execute(
                select(RemoteNode).order_by(RemoteNode.created_at.desc())
            )
            nodes = result.scalars().all()
            return [self._to_dict(n) for n in nodes]

    async def get_node(self, node_id: str) -> dict | None:
        async with self._sf() as db:
            node = await db.get(RemoteNode, node_id)
            return self._to_dict(node) if node else None

    async def create_node(
        self,
        *,
        name: str,
        gateway_url: str,
        gateway_token: str,
        description: str = "",
        node_type: str = "openclaw",
        config: dict | None = None,
    ) -> dict:
        async with self._sf() as db:
            node = RemoteNode(
                name=name,
                node_type=node_type,
                description=description,
                gateway_url=gateway_url.rstrip("/"),
                gateway_token=_encrypt(gateway_token),
                config=json.dumps(config or {}, ensure_ascii=False),
            )
            db.add(node)
            await db.commit()
            await db.refresh(node)
            log.info(f"Created remote node: {node.name} ({node.node_type}, {node.gateway_url})")
            return self._to_dict(node)

    async def update_node(self, node_id: str, **kwargs) -> dict | None:
        async with self._sf() as db:
            node = await db.get(RemoteNode, node_id)
            if not node:
                return None

            if "name" in kwargs and kwargs["name"] is not None:
                node.name = kwargs["name"]
            if "description" in kwargs and kwargs["description"] is not None:
                node.description = kwargs["description"]
            if "gateway_url" in kwargs and kwargs["gateway_url"] is not None:
                node.gateway_url = kwargs["gateway_url"].rstrip("/")
            if "gateway_token" in kwargs and kwargs["gateway_token"] is not None:
                token = kwargs["gateway_token"]
                if token and not token.startswith("****"):
                    node.gateway_token = _encrypt(token)
            if "node_type" in kwargs and kwargs["node_type"] is not None:
                node.node_type = kwargs["node_type"]
            if "config" in kwargs and kwargs["config"] is not None:
                node.config = json.dumps(kwargs["config"], ensure_ascii=False) if isinstance(kwargs["config"], dict) else kwargs["config"]

            await db.commit()
            await db.refresh(node)
            return self._to_dict(node)

    async def delete_node(self, node_id: str) -> bool:
        """Delete node and unbind all members referencing it."""
        from openvort.contacts.models import Member

        async with self._sf() as db:
            node = await db.get(RemoteNode, node_id)
            if not node:
                return False

            await db.execute(
                sa_update(Member)
                .where(Member.remote_node_id == node_id)
                .values(remote_node_id="")
            )

            await db.delete(node)
            await db.commit()
            log.info(f"Deleted remote node: {node.name}")
            return True

    async def get_bound_members(self, node_id: str) -> list[dict]:
        """List AI employees bound to a node."""
        from openvort.contacts.models import Member

        async with self._sf() as db:
            result = await db.execute(
                select(Member).where(
                    Member.remote_node_id == node_id,
                    Member.is_virtual == True,  # noqa: E712
                )
            )
            members = result.scalars().all()
            return [
                {"id": m.id, "name": m.name, "post": m.post or ""}
                for m in members
            ]

    # ---- Connection / Instruction (dispatched via executor) ----

    async def test_connection(self, node_id: str) -> dict:
        async with self._sf() as db:
            node = await db.get(RemoteNode, node_id)
            if not node:
                return {"ok": False, "message": "节点不存在"}

        executor = get_executor(node.node_type)
        if not executor:
            return {"ok": False, "message": f"不支持的节点类型: {node.node_type}"}

        token = _decrypt(node.gateway_token)
        masked = ("****" + token[-4:]) if len(token) > 4 else "****"
        log.info(f"Testing connection to node {node.name}: url={node.gateway_url}, token={masked}, len={len(token)}")
        result = await executor.test_connection(node.gateway_url, token)

        if result.get("ok"):
            await self._update_status(node_id, "online")
        else:
            await self._update_status(node_id, "offline")

        return result

    async def send_instruction(
        self, node_id: str, instruction: str, *, context: dict | None = None, timeout: int = 300,
        on_text: "Callable[[str], None] | None" = None,
    ) -> dict:
        """Send a work instruction to a remote node via its executor."""
        async with self._sf() as db:
            node = await db.get(RemoteNode, node_id)
            if not node:
                return {"ok": False, "error": "node_not_found", "message": "节点不存在"}

        executor = get_executor(node.node_type)
        if not executor:
            return {"ok": False, "error": "unsupported_type", "message": f"不支持的节点类型: {node.node_type}"}

        token = _decrypt(node.gateway_token)
        if not node.gateway_url or not token:
            return {"ok": False, "error": "node_not_configured", "message": "节点未配置"}

        masked = ("****" + token[-4:]) if len(token) > 4 else "****"
        log.info(f"Sending instruction to node {node.name}: url={node.gateway_url}, token={masked}, len={len(token)}")
        result = await executor.send_instruction(
            node.gateway_url, token, instruction, context=context, timeout=timeout,
            on_text=on_text,
        )

        if result.get("ok"):
            await self._update_status(node_id, "online")
        elif result.get("error") == "connect_error":
            await self._update_status(node_id, "offline")

        return result

    # ---- Internal ----

    async def _update_status(self, node_id: str, status: str) -> None:
        try:
            async with self._sf() as db:
                node = await db.get(RemoteNode, node_id)
                if node:
                    node.status = status
                    if status == "online":
                        node.last_heartbeat_at = datetime.now()
                    await db.commit()
        except Exception:
            pass

    @staticmethod
    def _to_dict(node: RemoteNode) -> dict:
        token = node.gateway_token
        if token:
            try:
                plain = _decrypt(token)
                masked = "****" + plain[-4:] if len(plain) > 4 else "****"
            except Exception:
                masked = "****"
        else:
            masked = ""

        config = {}
        if node.config:
            try:
                config = json.loads(node.config)
            except Exception:
                config = {}

        return {
            "id": node.id,
            "name": node.name,
            "node_type": node.node_type,
            "description": node.description,
            "gateway_url": node.gateway_url,
            "gateway_token": masked,
            "config": config,
            "status": node.status,
            "machine_info": json.loads(node.machine_info) if node.machine_info else {},
            "last_heartbeat_at": node.last_heartbeat_at.isoformat() if node.last_heartbeat_at else None,
            "created_at": node.created_at.isoformat() if node.created_at else "",
            "updated_at": node.updated_at.isoformat() if node.updated_at else "",
        }


# Backward compatibility alias
OpenClawNodeService = RemoteNodeService
