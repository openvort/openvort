"""
OpenClaw remote node executor implementation.

Handles connection testing and instruction execution via the
OpenClaw Gateway WebSocket protocol.  For Docker-hosted nodes the
executor can optionally run a helper script *inside* the container
(via ``docker exec``) so the WS connection originates from localhost,
sidestepping Docker Desktop port-forwarding auth quirks.
"""

from __future__ import annotations

import asyncio
import json
import shlex
from typing import TYPE_CHECKING

from openvort.core.openclaw_ws import OpenClawWsClient, OpenClawWsError
from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

log = get_logger("core.openclaw_executor")

# Inline helper executed inside the Docker container via ``docker exec``.
# Connects to the local gateway, sends an agent instruction, collects
# streaming text, and prints JSON result to stdout.
_DOCKER_AGENT_SCRIPT = r'''
import asyncio, json, sys, hashlib, base64, time
from uuid import uuid4

try:
    import websockets
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
except ImportError:
    print(json.dumps({"ok": False, "error": "missing_deps",
                       "message": "Container missing websockets/cryptography"}))
    sys.exit(0)

SCOPES = ["operator.read","operator.write","operator.admin",
          "operator.approvals","operator.pairing"]

def _load_token():
    with open("/root/.openclaw/openclaw.json") as f:
        cfg = json.load(f)
    return cfg.get("gateway",{}).get("auth",{}).get("token","")

async def run(instruction, timeout_s, extra_sp=""):
    token = _load_token()
    if not token:
        return {"ok": False, "error": "no_token", "message": "gateway.auth.token not configured"}

    pk = Ed25519PrivateKey.generate()
    pub = pk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    pub_b64 = base64.urlsafe_b64encode(pub).decode().rstrip("=")
    dev_id = hashlib.sha256(pub).hexdigest()

    ws = await websockets.connect("ws://127.0.0.1:18789", max_size=2**20)
    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    ch = json.loads(raw)
    if ch.get("event") != "connect.challenge":
        return {"ok": False, "error": "protocol", "message": "Expected challenge"}
    nonce = ch["payload"]["nonce"]
    ts = ch["payload"]["ts"]

    parts = ["v2", dev_id, "cli", "cli", "operator", ",".join(SCOPES), str(ts), token, nonce]
    sig = base64.urlsafe_b64encode(pk.sign("|".join(parts).encode())).decode().rstrip("=")

    req_id = uuid4().hex[:8]
    await ws.send(json.dumps({"type":"req","id":req_id,"method":"connect","params":{
        "minProtocol":3,"maxProtocol":3,
        "client":{"id":"cli","version":"1.0.0","platform":"linux","mode":"cli"},
        "role":"operator","scopes":SCOPES,
        "caps":["agent-events","tool-events"],"commands":[],"permissions":{},
        "auth":{"token":token},"locale":"en-US","userAgent":"openvort-docker/1.0.0",
        "device":{"id":dev_id,"publicKey":pub_b64,"signature":sig,"signedAt":ts,"nonce":nonce}}}))

    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    resp = json.loads(raw)
    if not resp.get("ok"):
        err = resp.get("error",{})
        return {"ok": False, "error": "auth", "message": err.get("message", str(err))}

    agent_id = resp.get("payload",{}).get("snapshot",{}).get("sessionDefaults",{}).get("defaultAgentId","main")
    session_key = resp.get("payload",{}).get("snapshot",{}).get("sessionDefaults",{}).get("mainSessionKey","") or "openvort"

    agent_params = {
        "message":instruction,"idempotencyKey":uuid4().hex,
        "agentId":agent_id,"sessionKey":session_key,
        "deliver":False,"timeout":max(timeout_s, 30)}
    if extra_sp:
        agent_params["extraSystemPrompt"] = extra_sp

    a_id = uuid4().hex[:8]
    await ws.send(json.dumps({"type":"req","id":a_id,"method":"agent","params":agent_params}))

    run_id = None
    wait_id = None
    text = ""
    tool_outputs = []

    async for raw in ws:
        msg = json.loads(raw)
        if msg.get("type") == "res":
            mid = msg.get("id")
            if mid == a_id:
                if not msg.get("ok"):
                    err = msg.get("error",{})
                    return {"ok": False, "error": "agent", "message": err.get("message", str(err))}
                run_id = msg["payload"]["runId"]
                wait_id = uuid4().hex[:8]
                await ws.send(json.dumps({"type":"req","id":wait_id,"method":"agent.wait",
                    "params":{"runId":run_id,"timeoutMs":timeout_s*1000}}))
            elif mid == wait_id:
                p = msg.get("payload",{})
                st = p.get("status","unknown")
                parts = []
                if text:
                    parts.append(text)
                if tool_outputs:
                    parts.append(chr(10).join(tool_outputs))
                final_text = (chr(10) + chr(10)).join(parts)
                return {"ok": st == "ok", "data":{"text": final_text, "status": st},
                        "error": p.get("error","") if st != "ok" else "",
                        "message": p.get("error","") if st != "ok" else ""}
        elif msg.get("type") == "event":
            p = msg.get("payload",{})
            if msg.get("event") == "agent" and p.get("runId") == run_id:
                stream = p.get("stream")
                data = p.get("data",{})
                if stream == "assistant":
                    t = data.get("text","")
                    if t:
                        text = t
                        print(f"__STREAM__|{t}", file=sys.stderr, flush=True)
                elif stream == "tool":
                    phase = data.get("phase","")
                    if phase == "result":
                        tr = data.get("result")
                        if isinstance(tr, dict):
                            stdout = tr.get("stdout","")
                            if stdout:
                                tool_outputs.append(stdout)
                                print(f"__STREAM__|{stdout}", file=sys.stderr, flush=True)
                        elif isinstance(tr, str) and tr:
                            tool_outputs.append(tr)
                            print(f"__STREAM__|{tr}", file=sys.stderr, flush=True)
                    elif phase == "output":
                        out = data.get("output","")
                        if out:
                            print(f"__STREAM__|{out}", file=sys.stderr, flush=True)

    return {"ok": False, "error": "disconnected", "message": "WS closed unexpectedly", "data": {"text": text}}

instruction = sys.argv[1]
timeout_s = int(sys.argv[2]) if len(sys.argv) > 2 else 120
extra_sp = sys.argv[3] if len(sys.argv) > 3 else ""
result = asyncio.run(run(instruction, timeout_s, extra_sp))
print(json.dumps(result, ensure_ascii=False))
'''


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
        container_id: str = "",
        context: dict | None = None,
        timeout: int = 300,
        on_text: "Callable[[str], None] | None" = None,
        extra_system_prompt: str = "",
    ) -> dict:
        if container_id:
            return await self._send_via_docker(
                container_id, instruction, timeout=timeout, on_text=on_text,
                extra_system_prompt=extra_system_prompt,
            )

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
                on_text=on_text,
                extra_system_prompt=extra_system_prompt or None,
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

    async def _send_via_docker(
        self,
        container_id: str,
        instruction: str,
        *,
        timeout: int = 300,
        on_text: "Callable[[str], None] | None" = None,
        extra_system_prompt: str = "",
    ) -> dict:
        """Execute instruction inside the Docker container via ``docker exec``.

        This avoids the macOS Docker Desktop port-forwarding auth issue
        by connecting to the gateway from localhost inside the container.
        """
        cmd = [
            "docker", "exec", container_id,
            "python3", "-c", _DOCKER_AGENT_SCRIPT,
            instruction, str(timeout), extra_system_prompt,
        ]

        log.info(f"Sending instruction via docker exec: container={container_id[:12]}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_lines: list[str] = []

            async def read_stderr():
                assert proc.stderr
                while True:
                    line = await proc.stderr.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").strip()
                    if text.startswith("__STREAM__|") and on_text is not None:
                        try:
                            on_text(text[len("__STREAM__|"):])
                        except Exception:
                            pass

            async def read_stdout():
                assert proc.stdout
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    stdout_lines.append(line.decode("utf-8", errors="replace"))

            await asyncio.wait_for(
                asyncio.gather(read_stderr(), read_stdout(), proc.wait()),
                timeout=timeout + 30,
            )

            output = "".join(stdout_lines).strip()
            rc = proc.returncode
            log.info(f"docker exec finished: exit_code={rc}, stdout_len={len(output)}")
            if output:
                log.debug(f"docker exec stdout: {output[:500]}")
            if not output:
                return {"ok": False, "error": "no_output", "message": f"容器内脚本无输出 (exit_code={rc})"}

            try:
                result = json.loads(output)
            except json.JSONDecodeError:
                return {"ok": False, "error": "parse_error", "message": f"解析失败: {output[:200]}"}

            log.info(f"docker exec result: ok={result.get('ok')}, text_len={len(result.get('data',{}).get('text',''))}")
            return result

        except asyncio.TimeoutError:
            log.warning(f"docker exec timed out for {container_id[:12]}")
            return {"ok": False, "error": "timeout", "message": f"执行超时 ({timeout}s)"}
        except Exception as exc:
            log.error(f"docker exec failed: {exc}")
            return {"ok": False, "error": "exec_error", "message": str(exc)}
