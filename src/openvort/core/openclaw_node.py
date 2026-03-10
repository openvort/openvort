"""
OpenClaw remote work node management.

Provides CRUD, connection testing, and instruction sending
for OpenClaw instances on remote machines via WebSocket Gateway protocol.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from openvort.core.openclaw_ws import OpenClawWsClient, OpenClawWsError
from openvort.db.models import OpenClawNode
from openvort.utils.logging import get_logger

log = get_logger("core.openclaw_node")


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
    except Exception:
        return ciphertext


class OpenClawNodeService:
    """Manage OpenClaw remote execution nodes."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    # ---- CRUD ----

    async def list_nodes(self) -> list[dict]:
        async with self._sf() as db:
            result = await db.execute(
                select(OpenClawNode).order_by(OpenClawNode.created_at.desc())
            )
            nodes = result.scalars().all()
            return [self._to_dict(n) for n in nodes]

    async def get_node(self, node_id: str) -> dict | None:
        async with self._sf() as db:
            node = await db.get(OpenClawNode, node_id)
            return self._to_dict(node) if node else None

    async def create_node(
        self, *, name: str, gateway_url: str, gateway_token: str, description: str = "",
    ) -> dict:
        async with self._sf() as db:
            node = OpenClawNode(
                name=name,
                description=description,
                gateway_url=gateway_url.rstrip("/"),
                gateway_token=_encrypt(gateway_token),
            )
            db.add(node)
            await db.commit()
            await db.refresh(node)
            log.info(f"Created OpenClaw node: {node.name} ({node.gateway_url})")
            return self._to_dict(node)

    async def update_node(self, node_id: str, **kwargs) -> dict | None:
        async with self._sf() as db:
            node = await db.get(OpenClawNode, node_id)
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

            await db.commit()
            await db.refresh(node)
            return self._to_dict(node)

    async def delete_node(self, node_id: str) -> bool:
        """Delete node and unbind all members referencing it."""
        from openvort.contacts.models import Member

        async with self._sf() as db:
            node = await db.get(OpenClawNode, node_id)
            if not node:
                return False

            await db.execute(
                sa_update(Member)
                .where(Member.openclaw_node_id == node_id)
                .values(openclaw_node_id="")
            )

            await db.delete(node)
            await db.commit()
            log.info(f"Deleted OpenClaw node: {node.name}")
            return True

    async def get_bound_members(self, node_id: str) -> list[dict]:
        """List AI employees bound to a node."""
        from openvort.contacts.models import Member

        async with self._sf() as db:
            result = await db.execute(
                select(Member).where(
                    Member.openclaw_node_id == node_id,
                    Member.is_virtual == True,  # noqa: E712
                )
            )
            members = result.scalars().all()
            return [
                {"id": m.id, "name": m.name, "post": m.post or ""}
                for m in members
            ]

    # ---- Connection / Instruction (WebSocket) ----

    async def test_connection(self, node_id: str) -> dict:
        async with self._sf() as db:
            node = await db.get(OpenClawNode, node_id)
            if not node:
                return {"ok": False, "message": "节点不存在"}

        if not node.gateway_url:
            return {"ok": False, "message": "节点未配置 Gateway 地址"}

        token = _decrypt(node.gateway_token)
        if not token:
            return {"ok": False, "message": "节点未配置 Gateway Token"}

        client = OpenClawWsClient()
        try:
            hello = await client.connect(node.gateway_url, token)
            await self._update_status(node_id, "online")

            methods = hello.get("features", {}).get("methods", [])
            has_agent = "agent" in methods

            if has_agent:
                return {"ok": True, "message": f"连接成功，WebSocket Gateway 可用 ({node.gateway_url})"}
            return {"ok": True, "message": f"Gateway 可连接，但 agent 方法不可用 ({node.gateway_url})"}

        except OpenClawWsError as exc:
            await self._update_status(node_id, "offline")
            return {"ok": False, "message": str(exc)}
        except Exception as exc:
            await self._update_status(node_id, "offline")
            return {"ok": False, "message": f"连接失败: {exc}"}
        finally:
            await client.close()

    async def send_instruction(
        self, node_id: str, instruction: str, *, context: dict | None = None, timeout: int = 300,
    ) -> dict:
        """Send a work instruction to a remote OpenClaw node via WebSocket."""
        async with self._sf() as db:
            node = await db.get(OpenClawNode, node_id)
            if not node:
                return {"ok": False, "error": "node_not_found", "message": "节点不存在"}

        token = _decrypt(node.gateway_token)
        if not node.gateway_url or not token:
            return {"ok": False, "error": "node_not_configured", "message": "节点未配置"}

        client = OpenClawWsClient()
        try:
            await client.connect(node.gateway_url, token)
            await self._update_status(node_id, "online")
        except OpenClawWsError as exc:
            log.warning(f"WS connect failed for {node.gateway_url}: {exc}")
            await self._update_status(node_id, "offline")
            return {"ok": False, "error": "connect_error", "message": str(exc)}
        except Exception as exc:
            log.warning(f"WS connect failed for {node.gateway_url}: {type(exc).__name__}: {exc}")
            await self._update_status(node_id, "offline")
            return {"ok": False, "error": "connect_error", "message": f"无法连接到 {node.gateway_url}: {exc}"}

        try:
            result = await client.execute_agent(
                instruction,
                timeout_ms=timeout * 1000,
                context=context,
            )

            if result.ok:
                return {
                    "ok": True,
                    "data": {
                        "text": result.text,
                        "status": result.status,
                    },
                }
            else:
                error_type = "timeout" if result.status == "timeout" else "execution_error"
                return {
                    "ok": False,
                    "error": error_type,
                    "message": result.error or f"远程执行失败 (status={result.status})",
                    "data": {"text": result.text} if result.text else {},
                }

        except Exception as exc:
            log.error(f"Send instruction failed: {exc}")
            return {"ok": False, "error": "unknown", "message": str(exc)}
        finally:
            await client.close()

    # ---- Internal ----

    async def _update_status(self, node_id: str, status: str) -> None:
        try:
            async with self._sf() as db:
                node = await db.get(OpenClawNode, node_id)
                if node:
                    node.status = status
                    if status == "online":
                        node.last_heartbeat_at = datetime.now()
                    await db.commit()
        except Exception:
            pass

    @staticmethod
    def _to_dict(node: OpenClawNode) -> dict:
        token = node.gateway_token
        if token:
            try:
                plain = _decrypt(token)
                masked = "****" + plain[-4:] if len(plain) > 4 else "****"
            except Exception:
                masked = "****"
        else:
            masked = ""

        return {
            "id": node.id,
            "name": node.name,
            "description": node.description,
            "gateway_url": node.gateway_url,
            "gateway_token": masked,
            "status": node.status,
            "machine_info": json.loads(node.machine_info) if node.machine_info else {},
            "last_heartbeat_at": node.last_heartbeat_at.isoformat() if node.last_heartbeat_at else None,
            "created_at": node.created_at.isoformat() if node.created_at else "",
            "updated_at": node.updated_at.isoformat() if node.updated_at else "",
        }
