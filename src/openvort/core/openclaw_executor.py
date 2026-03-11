"""
OpenClaw remote node executor implementation.

Handles connection testing and instruction execution via the
OpenClaw Gateway WebSocket protocol.
"""

from __future__ import annotations

from openvort.core.openclaw_ws import OpenClawWsClient, OpenClawWsError
from openvort.utils.logging import get_logger

log = get_logger("core.openclaw_executor")


class OpenClawExecutor:
    """RemoteNodeExecutor implementation for OpenClaw nodes."""

    async def test_connection(self, gateway_url: str, token: str) -> dict:
        if not gateway_url:
            return {"ok": False, "message": "节点未配置 Gateway 地址"}
        if not token:
            return {"ok": False, "message": "节点未配置 Gateway Token"}

        client = OpenClawWsClient()
        try:
            hello = await client.connect(gateway_url, token)
            methods = hello.get("features", {}).get("methods", [])
            has_agent = "agent" in methods

            if has_agent:
                return {"ok": True, "message": f"连接成功，WebSocket Gateway 可用 ({gateway_url})"}
            return {"ok": True, "message": f"Gateway 可连接，但 agent 方法不可用 ({gateway_url})"}

        except OpenClawWsError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:
            return {"ok": False, "message": f"连接失败: {exc}"}
        finally:
            await client.close()

    async def send_instruction(
        self,
        gateway_url: str,
        token: str,
        instruction: str,
        *,
        context: dict | None = None,
        timeout: int = 300,
    ) -> dict:
        if not gateway_url or not token:
            return {"ok": False, "error": "node_not_configured", "message": "节点未配置"}

        client = OpenClawWsClient()
        try:
            await client.connect(gateway_url, token)
        except OpenClawWsError as exc:
            log.warning(f"WS connect failed for {gateway_url}: {exc}")
            return {"ok": False, "error": "connect_error", "message": str(exc)}
        except Exception as exc:
            log.warning(f"WS connect failed for {gateway_url}: {type(exc).__name__}: {exc}")
            return {"ok": False, "error": "connect_error", "message": f"无法连接到 {gateway_url}: {exc}"}

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
