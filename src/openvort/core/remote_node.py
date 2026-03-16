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

    # ---- Docker container lifecycle ----

    async def create_docker_node(
        self,
        *,
        name: str,
        image: str = "python:3.11-slim",
        memory_limit: str = "2g",
        cpu_limit: float = 2.0,
        network_mode: str = "host",
        env_vars: dict | None = None,
        volumes: list[str] | None = None,
        description: str = "",
    ) -> dict:
        """Create a DB record and start a Docker container for a work node."""
        from openvort.core.docker_executor import DockerExecutor

        async with self._sf() as db:
            node = RemoteNode(
                name=name,
                node_type="docker",
                description=description,
                gateway_url="",
                gateway_token="",
                config=json.dumps({
                    "image": image,
                    "memory_limit": memory_limit,
                    "cpu_limit": cpu_limit,
                    "network_mode": network_mode,
                    "env_vars": env_vars or {},
                    "volumes": volumes or [],
                }, ensure_ascii=False),
                status="creating",
            )
            db.add(node)
            await db.commit()
            await db.refresh(node)
            node_id = node.id

        container_name = f"openvort-worker-{node_id[:8]}"
        workspace_vol = f"openvort-workspace-{node_id[:8]}"

        is_openclaw = "openclaw" in image.lower()
        merged_env = dict(env_vars or {})
        gateway_token = ""
        if is_openclaw:
            import secrets
            gateway_token = secrets.token_urlsafe(32)
            merged_env["GATEWAY_TOKEN"] = gateway_token

        executor = DockerExecutor()
        result = await executor.create_container({
            "image": image,
            "container_name": container_name,
            "memory_limit": memory_limit,
            "cpu_limit": cpu_limit,
            "network_mode": network_mode,
            "env_vars": merged_env,
            "volumes": volumes or [],
            "workspace_volume": workspace_vol,
            "use_entrypoint": is_openclaw,
        })

        if result.get("ok"):
            cid = result["container_id"]
            node_config = {
                "image": image,
                "memory_limit": memory_limit,
                "cpu_limit": cpu_limit,
                "network_mode": network_mode,
                "env_vars": env_vars or {},
                "volumes": volumes or [],
                "container_id": cid,
                "container_name": container_name,
                "workspace_volume": workspace_vol,
            }

            if is_openclaw:
                gw_url = "ws://127.0.0.1:18789"
                node_config["openclaw_bridge"] = True
                async with self._sf() as db:
                    node = await db.get(RemoteNode, node_id)
                    if node:
                        node.gateway_url = gw_url
                        node.gateway_token = _encrypt(gateway_token)
                        await db.commit()

            await self.update_node(node_id, config=node_config)
            await self._update_status(node_id, "running")
            await self._update_machine_info(node_id, {"os": "Linux", "image": image})
        else:
            await self._update_status(node_id, "error")

        node_dict = await self.get_node(node_id)
        if node_dict:
            node_dict["_create_result"] = result
        return node_dict or {"id": node_id, "_create_result": result}

    async def start_docker_container(self, node_id: str) -> dict:
        cid = await self._get_container_id(node_id)
        if not cid:
            return {"ok": False, "message": "容器 ID 不存在"}
        from openvort.core.docker_executor import DockerExecutor
        result = await DockerExecutor().start_container(cid)
        if result.get("ok"):
            await self._update_status(node_id, "running")
        return result

    async def stop_docker_container(self, node_id: str) -> dict:
        cid = await self._get_container_id(node_id)
        if not cid:
            return {"ok": False, "message": "容器 ID 不存在"}
        from openvort.core.docker_executor import DockerExecutor
        result = await DockerExecutor().stop_container(cid)
        if result.get("ok"):
            await self._update_status(node_id, "stopped")
        return result

    async def restart_docker_container(self, node_id: str) -> dict:
        cid = await self._get_container_id(node_id)
        if not cid:
            return {"ok": False, "message": "容器 ID 不存在"}
        from openvort.core.docker_executor import DockerExecutor
        result = await DockerExecutor().restart_container(cid)
        if result.get("ok"):
            await self._update_status(node_id, "running")
        return result

    async def remove_docker_container(self, node_id: str) -> dict:
        cid = await self._get_container_id(node_id)
        if not cid:
            return {"ok": False, "message": "容器 ID 不存在"}
        from openvort.core.docker_executor import DockerExecutor
        result = await DockerExecutor().remove_container(cid)
        if result.get("ok"):
            await self._update_status(node_id, "stopped")
        return result

    async def get_docker_status(self, node_id: str) -> dict:
        cid = await self._get_container_id(node_id)
        if not cid:
            return {"status": "unknown"}
        from openvort.core.docker_executor import DockerExecutor
        return await DockerExecutor().get_container_status(cid)

    async def get_docker_stats(self, node_id: str) -> dict:
        cid = await self._get_container_id(node_id)
        if not cid:
            return {}
        from openvort.core.docker_executor import DockerExecutor
        return await DockerExecutor().get_container_stats(cid)

    async def get_docker_logs(self, node_id: str, *, tail: int = 100) -> str:
        cid = await self._get_container_id(node_id)
        if not cid:
            return ""
        from openvort.core.docker_executor import DockerExecutor
        return await DockerExecutor().get_container_logs(cid, tail=tail)

    async def get_all_docker_stats(self) -> dict:
        """Get resource stats for all running Docker nodes."""
        nodes = await self.list_nodes()
        docker_nodes = [n for n in nodes if n["node_type"] == "docker" and n["status"] == "running"]
        cid_map: dict[str, str] = {}
        for n in docker_nodes:
            cid = (n.get("config") or {}).get("container_id", "")
            if cid:
                cid_map[cid] = n["id"]

        if not cid_map:
            return {}

        from openvort.core.docker_executor import DockerExecutor
        raw = await DockerExecutor().batch_stats(list(cid_map.keys()))
        result = {}
        for cid, stats in raw.items():
            nid = cid_map.get(cid)
            if nid:
                result[nid] = stats
        return result

    async def check_docker_health(self) -> None:
        """Check all Docker nodes: update status, detect exits, memory alerts."""
        nodes = await self.list_nodes()
        docker_nodes = [n for n in nodes if n["node_type"] == "docker"]
        if not docker_nodes:
            return

        from openvort.core.docker_executor import DockerExecutor
        executor = DockerExecutor()

        running_cids: list[str] = []
        cid_node_map: dict[str, dict] = {}

        for node in docker_nodes:
            cid = (node.get("config") or {}).get("container_id", "")
            if not cid:
                continue

            status_info = await executor.get_container_status(cid)
            container_status = status_info.get("status", "unknown")

            if container_status == "running":
                if node["status"] != "running":
                    await self._update_status(node["id"], "running")
                running_cids.append(cid)
                cid_node_map[cid] = node
            elif container_status == "exited" and node["status"] == "running":
                await self._update_status(node["id"], "error")
                try:
                    from openvort.web.ws import manager as _ws
                    await _ws.broadcast({
                        "type": "docker_alert",
                        "node_id": node["id"],
                        "node_name": node["name"],
                        "alert": "container_exited",
                        "message": f"容器「{node['name']}」异常退出",
                    })
                except Exception:
                    pass
            elif container_status not in ("running", "exited", "unknown") and node["status"] not in ("stopped", "error", "unknown"):
                await self._update_status(node["id"], "stopped")

        # Memory threshold alerts for running containers
        if running_cids:
            stats = await executor.batch_stats(running_cids)
            for cid, st in stats.items():
                node = cid_node_map.get(cid)
                if not node:
                    continue
                mem_perc_str = st.get("mem_perc", "0%").rstrip("%")
                try:
                    mem_perc = float(mem_perc_str)
                except (ValueError, TypeError):
                    continue
                if mem_perc >= 90:
                    try:
                        from openvort.web.ws import manager as _ws
                        await _ws.broadcast({
                            "type": "docker_alert",
                            "node_id": node["id"],
                            "node_name": node["name"],
                            "alert": "memory_high",
                            "message": f"容器「{node['name']}」内存使用率 {mem_perc:.0f}%，已超过 90% 阈值",
                            "mem_perc": mem_perc,
                        })
                    except Exception:
                        pass

    async def _get_container_id(self, node_id: str) -> str:
        node = await self.get_node(node_id)
        if not node:
            return ""
        config = node.get("config") or {}
        return config.get("container_id", "")

    async def _update_machine_info(self, node_id: str, info: dict) -> None:
        try:
            async with self._sf() as db:
                node = await db.get(RemoteNode, node_id)
                if node:
                    node.machine_info = json.dumps(info, ensure_ascii=False)
                    await db.commit()
        except Exception:
            pass

    # ---- Connection / Instruction (dispatched via executor) ----

    async def test_connection(self, node_id: str) -> dict:
        async with self._sf() as db:
            node = await db.get(RemoteNode, node_id)
            if not node:
                return {"ok": False, "message": "节点不存在"}

        executor = get_executor(node.node_type)
        if not executor:
            return {"ok": False, "message": f"不支持的节点类型: {node.node_type}"}

        if node.node_type == "docker":
            config = {}
            try:
                config = json.loads(node.config) if node.config else {}
            except Exception:
                pass
            cid = config.get("container_id", "")
            result = await executor.test_connection(cid, "")
            status = "running" if result.get("ok") else "stopped"
            await self._update_status(node_id, status)
        else:
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

        if node.node_type == "docker":
            config = {}
            try:
                config = json.loads(node.config) if node.config else {}
            except Exception:
                pass

            if config.get("openclaw_bridge") and node.gateway_url:
                token = _decrypt(node.gateway_token)
                if not token:
                    return {"ok": False, "error": "node_not_configured", "message": "OpenClaw Gateway Token 未设置"}
                openclaw_exec = get_executor("openclaw")
                if not openclaw_exec:
                    return {"ok": False, "error": "unsupported_type", "message": "OpenClaw executor 未注册"}
                log.info(f"Sending instruction to OpenClaw Docker node {node.name}: {node.gateway_url}")
                result = await openclaw_exec.send_instruction(
                    node.gateway_url, token, instruction, context=context, timeout=timeout, on_text=on_text,
                )
            else:
                cid = config.get("container_id", "")
                if not cid:
                    return {"ok": False, "error": "node_not_configured", "message": "Docker 容器 ID 未设置"}
                log.info(f"Sending instruction to Docker node {node.name}: container={cid[:12]}")
                result = await executor.send_instruction(
                    cid, "", instruction, context=context, timeout=timeout, on_text=on_text,
                )
        else:
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
            status = "running" if node.node_type == "docker" else "online"
            await self._update_status(node_id, status)
        elif result.get("error") == "connect_error":
            await self._update_status(node_id, "offline")

        return result

    # ---- Internal ----

    async def _update_status(self, node_id: str, status: str) -> None:
        old_status = None
        try:
            async with self._sf() as db:
                node = await db.get(RemoteNode, node_id)
                if node:
                    old_status = node.status
                    node.status = status
                    if status in ("online", "running"):
                        node.last_heartbeat_at = datetime.now()
                    await db.commit()
        except Exception:
            pass

        if old_status and old_status != status:
            try:
                from openvort.web.ws import manager as _ws
                await _ws.broadcast({
                    "type": "node_status_change",
                    "node_id": node_id,
                    "status": status,
                    "old_status": old_status,
                })
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

        if config.get("env_vars"):
            masked_env = {}
            for k, v in config["env_vars"].items():
                if any(secret in k.upper() for secret in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                    masked_env[k] = ("****" + v[-4:]) if len(v) > 4 else "****"
                else:
                    masked_env[k] = v
            config["env_vars"] = masked_env

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
