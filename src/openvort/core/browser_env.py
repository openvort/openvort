"""
Browser sandbox environment manager.

Manages Docker containers running a headless Chromium + noVNC setup,
allowing AI employees to operate browsers with real-time visual preview.
Each browser container exposes a noVNC web interface for admin observation
and manual takeover, plus a CDP endpoint for Playwright automation.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from openvort.core.remote_node import RemoteNodeService

log = get_logger("core.browser_env")

BROWSER_IMAGE = "openvort/browser-sandbox:latest"
NOVNC_BASE_PORT = 6080
CDP_PORT = 9222


class BrowserEnvironment:
    """Manage browser sandbox containers for work nodes."""

    def __init__(self, service: "RemoteNodeService | None" = None):
        self._service = service
        self._port_counter = NOVNC_BASE_PORT

    async def start_browser(
        self,
        node_id: str,
        *,
        image: str = BROWSER_IMAGE,
        novnc_port: int = 0,
    ) -> dict:
        """Start a browser sandbox container linked to a work node.

        Returns {"ok": bool, "novnc_url": str, "cdp_url": str, "container_id": str}.
        """
        if novnc_port == 0:
            self._port_counter += 1
            novnc_port = self._port_counter

        container_name = f"openvort-browser-{node_id[:8]}"

        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{novnc_port}:6080",
            "--network", "host",
            image,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                return {"ok": False, "message": f"启动浏览器容器失败: {err}"}

            cid = stdout.decode().strip()
            log.info(f"Browser sandbox started: {cid[:12]} (noVNC port {novnc_port})")

            return {
                "ok": True,
                "container_id": cid,
                "container_name": container_name,
                "novnc_url": f"http://localhost:{novnc_port}/vnc.html",
                "cdp_url": f"http://localhost:{CDP_PORT}",
                "novnc_port": novnc_port,
            }
        except asyncio.TimeoutError:
            return {"ok": False, "message": "启动浏览器容器超时"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    async def stop_browser(self, container_id_or_name: str) -> dict:
        """Stop and remove a browser sandbox container."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", container_id_or_name,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    async def get_novnc_url(self, node_id: str) -> str | None:
        """Get the noVNC URL for a node's browser container, if running."""
        container_name = f"openvort-browser-{node_id[:8]}"
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", "-f",
                '{{range $p, $conf := .NetworkSettings.Ports}}{{if eq $p "6080/tcp"}}{{(index $conf 0).HostPort}}{{end}}{{end}}',
                container_name,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            port = stdout.decode().strip()
            if port:
                return f"/vnc.html?autoconnect=true&resize=scale"
        except Exception:
            pass
        return None
