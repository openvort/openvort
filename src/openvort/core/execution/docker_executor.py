"""
Docker container executor for work nodes.

Implements RemoteNodeExecutor protocol for Docker containers,
plus lifecycle management (create/start/stop/restart/remove).
All Docker operations use CLI subprocess calls (no SDK dependency).
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

log = get_logger("core.docker_executor")

BUILTIN_IMAGES: dict[str, dict] = {
    "ghcr.io/openvort/worker-sandbox:latest": {"context": "docker/worker-sandbox"},
    "ghcr.io/openvort/coding-sandbox:latest": {"context": "docker/coding-sandbox"},
    "ghcr.io/openvort/browser-sandbox:latest": {"context": "docker/browser-sandbox", "use_entrypoint": True},
}


def image_needs_entrypoint(image: str) -> bool:
    """Check if an image should use its own CMD/ENTRYPOINT instead of sleep infinity."""
    spec = BUILTIN_IMAGES.get(image)
    return bool(spec and spec.get("use_entrypoint"))


def _find_project_root() -> str:
    """Locate project root by looking for the docker/ directory."""
    current = pathlib.Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "docker").is_dir():
            return str(current)
        current = current.parent
    return ""


class DockerExecutor:
    """RemoteNodeExecutor implementation for local Docker containers."""

    # ---- RemoteNodeExecutor protocol ----

    async def test_connection(self, gateway_url: str, token: str) -> dict:
        """For Docker nodes, gateway_url holds container_id.
        token is unused. Check if the container is running.
        """
        container_id = gateway_url
        if not container_id:
            return {"ok": False, "message": "容器 ID 未设置"}

        if not self._is_docker_available():
            return {"ok": False, "message": "Docker 不可用"}

        status = await self._inspect_status(container_id)
        if status == "running":
            return {"ok": True, "message": "容器运行中"}
        if status:
            return {"ok": False, "message": f"容器状态: {status}"}
        return {"ok": False, "message": "容器不存在或已被删除"}

    async def send_instruction(
        self,
        gateway_url: str,
        token: str,
        instruction: str,
        *,
        context: dict | None = None,
        timeout: int = 300,
        on_text: "Callable[[str], None] | None" = None,
    ) -> dict:
        """Execute instruction inside the Docker container via `docker exec`."""
        container_id = gateway_url
        if not container_id:
            return {"ok": False, "error": "node_not_configured", "message": "容器 ID 未设置"}

        if not self._is_docker_available():
            return {"ok": False, "error": "docker_unavailable", "message": "Docker 不可用"}

        status = await self._inspect_status(container_id)
        if status != "running":
            return {"ok": False, "error": "container_not_running", "message": f"容器未运行 (状态: {status or 'unknown'})"}

        try:
            result = await self._exec_streaming(
                container_id, instruction, timeout=timeout, on_text=on_text,
            )
            combined = result["stdout"]
            if result["stderr"]:
                combined = combined + "\n" + result["stderr"] if combined else result["stderr"]

            if result["exit_code"] == 0:
                return {"ok": True, "data": {"text": combined.strip(), "status": "ok"}}
            else:
                return {
                    "ok": False,
                    "error": "execution_error",
                    "message": f"命令退出码: {result['exit_code']}",
                    "data": {"text": combined.strip()},
                }
        except asyncio.TimeoutError:
            return {"ok": False, "error": "timeout", "message": f"执行超时 ({timeout}s)"}
        except Exception as exc:
            log.error(f"Docker exec failed: {exc}")
            return {"ok": False, "error": "unknown", "message": str(exc)}

    # ---- Container lifecycle ----

    async def create_container(self, config: dict) -> dict:
        """Create and start a persistent Docker container.

        Returns {"ok": bool, "container_id": str, "container_name": str, "message": str}.
        """
        if not self._is_docker_available():
            return {"ok": False, "message": "Docker 不可用"}

        image = config.get("image", "python:3.11-slim")
        name = config.get("container_name", "")
        memory = config.get("memory_limit", "2g")
        cpus = config.get("cpu_limit", 2.0)
        network = config.get("network_mode", "host")
        env_vars: dict = config.get("env_vars", {})
        volumes: list = config.get("volumes", [])

        cmd = ["docker", "run", "-d", "--restart", "unless-stopped"]
        if name:
            cmd.extend(["--name", name])
        cmd.extend(["--memory", str(memory), f"--cpus={cpus}"])
        if network:
            cmd.extend(["--network", network])

        workspace_vol = config.get("workspace_volume", "")
        if workspace_vol:
            cmd.extend(["-v", f"{workspace_vol}:/workspace"])

        for v in volumes:
            cmd.extend(["-v", v])
        for k, v in env_vars.items():
            cmd.extend(["-e", f"{k}={v}"])

        use_entrypoint = config.get("use_entrypoint", False)
        if use_entrypoint:
            cmd.append(image)
        else:
            cmd.extend([image, "sleep", "infinity"])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                log.error(f"Container create failed: {err}")
                return {"ok": False, "message": f"创建容器失败: {err}"}

            cid = stdout.decode().strip()
            log.info(f"Created Docker container: {cid[:12]} ({name})")
            return {"ok": True, "container_id": cid, "container_name": name, "message": "容器已创建并启动"}
        except asyncio.TimeoutError:
            return {"ok": False, "message": "创建容器超时 (120s)"}
        except Exception as exc:
            return {"ok": False, "message": f"创建容器异常: {exc}"}

    async def start_container(self, container_id: str) -> dict:
        return await self._simple_cmd(["docker", "start", container_id], "启动")

    async def stop_container(self, container_id: str) -> dict:
        return await self._simple_cmd(["docker", "stop", "-t", "10", container_id], "停止")

    async def restart_container(self, container_id: str) -> dict:
        return await self._simple_cmd(["docker", "restart", "-t", "10", container_id], "重启")

    async def remove_container(self, container_id: str, *, force: bool = True) -> dict:
        cmd = ["docker", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container_id)
        return await self._simple_cmd(cmd, "删除")

    async def get_container_status(self, container_id: str) -> dict:
        """Return detailed container status via `docker inspect`."""
        if not container_id:
            return {"status": "unknown"}
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", "--format",
                '{"status":"{{.State.Status}}","running":{{.State.Running}},'
                '"started_at":"{{.State.StartedAt}}","image":"{{.Config.Image}}"}',
                container_id,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                return json.loads(stdout.decode().strip())
        except Exception:
            pass
        return {"status": "unknown"}

    async def get_container_stats(self, container_id: str) -> dict:
        """Return CPU/memory stats for a running container."""
        if not container_id:
            return {}
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "stats", "--no-stream", "--format",
                '{"cpu":"{{.CPUPerc}}","mem":"{{.MemUsage}}","mem_perc":"{{.MemPerc}}","net":"{{.NetIO}}","block":"{{.BlockIO}}"}',
                container_id,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode == 0 and stdout.strip():
                return json.loads(stdout.decode().strip())
        except Exception:
            pass
        return {}

    async def get_container_logs(self, container_id: str, *, tail: int = 100) -> str:
        """Return recent container logs."""
        if not container_id:
            return ""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "logs", "--tail", str(tail), container_id,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            return stdout.decode(errors="replace")
        except Exception:
            return ""

    # ---- Docker image helpers ----

    async def list_local_images(self) -> list[dict]:
        """List locally available Docker images."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "images", "--format",
                '{"repository":"{{.Repository}}","tag":"{{.Tag}}","id":"{{.ID}}","size":"{{.Size}}","created":"{{.CreatedSince}}"}',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            images = []
            for line in stdout.decode().strip().splitlines():
                if line.strip():
                    try:
                        images.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return images
        except Exception:
            return []

    async def pull_image(self, image: str) -> dict:
        """Pull a Docker image. Returns {"ok": bool, "message": str}."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "pull", image,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
            if proc.returncode == 0:
                return {"ok": True, "message": f"镜像拉取成功: {image}"}
            return {"ok": False, "message": stderr.decode(errors="replace").strip()}
        except asyncio.TimeoutError:
            return {"ok": False, "message": "镜像拉取超时 (600s)"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    async def check_image_exists(self, image: str) -> bool:
        """Check if a Docker image exists locally."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "image", "inspect", image,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False

    async def install_image_streaming(self, image: str) -> AsyncIterator[str]:
        """Build (for builtin images) or pull, yielding progress lines."""
        spec = BUILTIN_IMAGES.get(image)
        if spec:
            project_root = _find_project_root()
            if project_root:
                context_dir = os.path.join(project_root, spec["context"])
                if os.path.isfile(os.path.join(context_dir, "Dockerfile")):
                    async for line in self._build_image_streaming(image, context_dir):
                        yield line
                    return
        async for line in self._pull_image_streaming(image):
            yield line

    async def _build_image_streaming(self, tag: str, context_dir: str) -> AsyncIterator[str]:
        """Run `docker build` and yield output lines."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "build", "--progress=plain", "-t", tag, context_dir,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        async for raw in proc.stdout:
            yield raw.decode(errors="replace").rstrip()
        await proc.wait()
        if proc.returncode != 0:
            yield f"[ERROR] docker build exited with code {proc.returncode}"

    async def _pull_image_streaming(self, image: str) -> AsyncIterator[str]:
        """Run `docker pull` and yield output lines."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "pull", image,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        async for raw in proc.stdout:
            yield raw.decode(errors="replace").rstrip()
        await proc.wait()
        if proc.returncode != 0:
            yield f"[ERROR] docker pull exited with code {proc.returncode}"

    async def batch_stats(self, container_ids: list[str]) -> dict[str, dict]:
        """Get stats for multiple containers in one call."""
        if not container_ids:
            return {}
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "stats", "--no-stream", "--format",
                '{{.ID}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}',
                *container_ids,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            result: dict[str, dict] = {}
            for line in stdout.decode().strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 6:
                    cid = parts[0]
                    for full_id in container_ids:
                        if full_id.startswith(cid):
                            cid = full_id
                            break
                    result[cid] = {
                        "cpu": parts[1], "mem": parts[2], "mem_perc": parts[3],
                        "net": parts[4], "block": parts[5],
                    }
            return result
        except Exception:
            return {}

    async def get_container_ip(self, container_id: str) -> str:
        """Return the container's IP address (bridge network) or '' (host network)."""
        if not container_id:
            return ""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", "-f",
                "{{.NetworkSettings.IPAddress}}", container_id,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                return stdout.decode().strip()
        except Exception:
            pass
        return ""

    # ---- Internal helpers ----

    @staticmethod
    def _is_docker_available() -> bool:
        return shutil.which("docker") is not None

    @staticmethod
    async def _inspect_status(container_id: str) -> str:
        """Return container state string (running/exited/...) or empty if not found."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", "-f", "{{.State.Status}}", container_id,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                return stdout.decode().strip()
        except Exception:
            pass
        return ""

    @staticmethod
    async def _simple_cmd(cmd: list[str], action: str) -> dict:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0:
                return {"ok": True, "message": f"容器{action}成功"}
            return {"ok": False, "message": f"容器{action}失败: {stderr.decode(errors='replace').strip()}"}
        except asyncio.TimeoutError:
            return {"ok": False, "message": f"容器{action}超时"}
        except Exception as exc:
            return {"ok": False, "message": f"容器{action}异常: {exc}"}

    @staticmethod
    async def _exec_streaming(
        container_id: str,
        command: str,
        *,
        timeout: int = 300,
        on_text: "Callable[[str], None] | None" = None,
    ) -> dict:
        """Execute a command in the container with optional streaming output."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id, "sh", "-c", command,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )

        if not on_text:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "exit_code": proc.returncode or 0,
            }

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        accumulated = ""

        async def _read(stream, parts):
            nonlocal accumulated
            async for raw in stream:
                line = raw.decode(errors="replace")
                parts.append(line)
                accumulated += line
                try:
                    on_text(accumulated)
                except Exception:
                    pass

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _read(proc.stdout, stdout_parts),
                    _read(proc.stderr, stderr_parts),
                ),
                timeout=timeout,
            )
            await proc.wait()
            return {
                "stdout": "".join(stdout_parts),
                "stderr": "".join(stderr_parts),
                "exit_code": proc.returncode or 0,
            }
        except asyncio.CancelledError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            raise
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            raise
