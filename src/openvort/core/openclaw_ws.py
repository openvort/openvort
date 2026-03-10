"""
OpenClaw Gateway WebSocket client.

Implements the Gateway protocol v3: connect handshake, agent execution
with agent.wait, and streaming event collection.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from uuid import uuid4

import websockets
from websockets.asyncio.client import ClientConnection

from openvort.utils.logging import get_logger

log = get_logger("core.openclaw_ws")

_PROTOCOL_VERSION = 3
_CLIENT_ID = "gateway-client"
_CLIENT_MODE = "backend"
_CLIENT_VERSION = "1.0.0"


@dataclass
class AgentResult:
    ok: bool
    text: str = ""
    status: str = ""
    started_at: int | None = None
    ended_at: int | None = None
    error: str = ""


@dataclass
class _PendingReq:
    """Tracks a pending request waiting for its response."""
    future: asyncio.Future
    id: str


class OpenClawWsClient:
    """WebSocket client for OpenClaw Gateway protocol v3."""

    def __init__(self) -> None:
        self._ws: ClientConnection | None = None
        self._connected = False
        self._hello_payload: dict = {}
        self._default_agent_id: str = "main"
        self._main_session_key: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self, gateway_url: str, token: str, *, timeout: float = 15) -> dict:
        """Establish WS connection and perform the connect handshake.

        Returns the hello-ok payload on success.
        Raises ``OpenClawWsError`` on failure.
        """
        ws_url = _http_to_ws(gateway_url)
        log.debug(f"Connecting to {ws_url}")

        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(ws_url, max_size=2 ** 20),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise OpenClawWsError(f"连接超时 ({gateway_url})")
        except Exception as exc:
            raise OpenClawWsError(f"无法连接到 {gateway_url}: {exc}")

        try:
            hello = await self._handshake(token, timeout=timeout)
        except Exception:
            await self._force_close()
            raise

        self._connected = True
        self._hello_payload = hello

        snapshot = hello.get("snapshot", {})
        defaults = snapshot.get("sessionDefaults", {})
        self._default_agent_id = defaults.get("defaultAgentId", "main")
        self._main_session_key = defaults.get("mainSessionKey", "")

        return hello

    async def execute_agent(
        self,
        instruction: str,
        *,
        timeout_ms: int = 120_000,
        session_key: str | None = None,
        extra_system_prompt: str | None = None,
        context: dict | None = None,
    ) -> AgentResult:
        """Send an agent instruction and wait for completion.

        Collects streaming text deltas and returns the full result.
        """
        if not self._connected or not self._ws:
            return AgentResult(ok=False, error="WebSocket 未连接")

        agent_req_id = _short_id()
        idempotency_key = str(uuid4())

        params: dict = {
            "message": instruction,
            "idempotencyKey": idempotency_key,
            "agentId": self._default_agent_id,
            "sessionKey": session_key or self._main_session_key or "openvort",
            "deliver": False,
            "timeout": max(timeout_ms // 1000, 30),
        }
        if extra_system_prompt:
            params["extraSystemPrompt"] = extra_system_prompt
        if context:
            params["label"] = json.dumps(context, ensure_ascii=False)

        await self._send_req(agent_req_id, "agent", params)

        run_id: str | None = None
        wait_req_id: str | None = None
        latest_text: str = ""
        result = AgentResult(ok=False, error="unexpected disconnect")

        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "res":
                    msg_id = msg.get("id")

                    if msg_id == agent_req_id:
                        if not msg.get("ok"):
                            err = msg.get("error", {})
                            return AgentResult(
                                ok=False,
                                error=err.get("message", str(err)),
                            )
                        run_id = msg["payload"]["runId"]
                        wait_req_id = _short_id()
                        await self._send_req(wait_req_id, "agent.wait", {
                            "runId": run_id,
                            "timeoutMs": timeout_ms,
                        })

                    elif msg_id == wait_req_id:
                        payload = msg.get("payload", {})
                        status = payload.get("status", "unknown")
                        result = AgentResult(
                            ok=(status == "ok"),
                            text=latest_text,
                            status=status,
                            started_at=payload.get("startedAt"),
                            ended_at=payload.get("endedAt"),
                            error=payload.get("error", ""),
                        )
                        break

                elif msg_type == "event":
                    event_name = msg.get("event")
                    payload = msg.get("payload", {})

                    if event_name == "agent" and payload.get("runId") == run_id:
                        stream = payload.get("stream")
                        data = payload.get("data", {})

                        if stream == "assistant":
                            text = data.get("text", "")
                            if text:
                                latest_text = text

                    # tick keepalive — just ignore

        except websockets.exceptions.ConnectionClosed:
            if not result.text and latest_text:
                result = AgentResult(
                    ok=False,
                    text=latest_text,
                    status="disconnected",
                    error="WebSocket 连接中断",
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            result = AgentResult(ok=False, error=str(exc))

        return result

    async def close(self) -> None:
        """Gracefully close the connection."""
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    @property
    def features(self) -> dict:
        return self._hello_payload.get("features", {})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _handshake(self, token: str, *, timeout: float = 15) -> dict:
        """Perform the connect handshake, return hello-ok payload."""
        assert self._ws is not None

        req_id = _short_id()
        connect_frame = {
            "type": "req",
            "id": req_id,
            "method": "connect",
            "params": {
                "minProtocol": _PROTOCOL_VERSION,
                "maxProtocol": _PROTOCOL_VERSION,
                "client": {
                    "id": _CLIENT_ID,
                    "version": _CLIENT_VERSION,
                    "platform": "python",
                    "mode": _CLIENT_MODE,
                },
                "role": "operator",
                "scopes": ["operator.read", "operator.write"],
                "caps": [],
                "commands": [],
                "permissions": {},
                "auth": {"token": token},
            },
        }

        await self._ws.send(json.dumps(connect_frame))

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise OpenClawWsError("握手超时")

            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                raise OpenClawWsError("握手超时")

            msg = json.loads(raw)

            if msg.get("type") == "event" and msg.get("event") == "connect.challenge":
                continue

            if msg.get("type") == "res" and msg.get("id") == req_id:
                if not msg.get("ok"):
                    err = msg.get("error", {})
                    raise OpenClawWsError(
                        f"认证失败: {err.get('message', str(err))}"
                    )
                return msg.get("payload", {})

            # Skip unexpected frames during handshake
            log.debug(f"Handshake: skipping frame type={msg.get('type')}")

    async def _send_req(self, req_id: str, method: str, params: dict) -> None:
        assert self._ws is not None
        frame = {
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params,
        }
        await self._ws.send(json.dumps(frame))

    async def _force_close(self) -> None:
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None


class OpenClawWsError(Exception):
    """Raised when a WebSocket operation fails."""


def _http_to_ws(url: str) -> str:
    """Convert http(s):// URL to ws(s):// URL."""
    if url.startswith("https://"):
        return "wss://" + url[len("https://"):]
    if url.startswith("http://"):
        return "ws://" + url[len("http://"):]
    if url.startswith("ws://") or url.startswith("wss://"):
        return url
    return "ws://" + url


def _short_id() -> str:
    return uuid4().hex[:8]
