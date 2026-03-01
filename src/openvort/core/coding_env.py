"""
Coding execution environment — detect and execute CLI tools in local or Docker mode.

This is a core infrastructure module (not a plugin). It provides:
- Environment detection (local / Docker / unavailable)
- Unified command execution across modes
- Docker image management
- CLI tool availability checking
"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from openvort.utils.logging import get_logger

log = get_logger("core.coding_env")

DEFAULT_CODING_IMAGE = "openvort/coding-sandbox:latest"


class EnvMode(str, Enum):
    LOCAL = "local"
    DOCKER = "docker"
    UNAVAILABLE = "unavailable"


@dataclass
class ExecResult:
    """Result of a command execution in the coding environment."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass
class CLIToolStatus:
    """Status of a single CLI tool."""
    name: str
    installed: bool = False
    version: str = ""
    error: str = ""


@dataclass
class EnvStatus:
    """Full coding environment status report."""
    mode: EnvMode = EnvMode.UNAVAILABLE
    running_in_docker: bool = False
    docker_available: bool = False
    docker_socket: bool = False
    coding_image_pulled: bool = False
    coding_image_name: str = DEFAULT_CODING_IMAGE
    cli_tools: dict[str, CLIToolStatus] = field(default_factory=dict)
    api_keys: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "running_in_docker": self.running_in_docker,
            "docker_available": self.docker_available,
            "docker_socket": self.docker_socket,
            "coding_image_pulled": self.coding_image_pulled,
            "coding_image_name": self.coding_image_name,
            "cli_tools": {
                k: {"installed": v.installed, "version": v.version, "error": v.error}
                for k, v in self.cli_tools.items()
            },
            "api_keys": self.api_keys,
        }


# Well-known CLI tool binaries for local detection
_CLI_BINARIES = {
    "claude-code": "claude",
    "aider": "aider",
}


class CodingEnvironment:
    """Coding execution environment manager.

    Detects whether to run CLI tools locally or via Docker,
    and provides a unified execute() interface.
    """

    def __init__(
        self,
        image: str = DEFAULT_CODING_IMAGE,
        memory_limit: str = "2g",
        cpu_limit: float = 2.0,
        timeout: int = 300,
    ):
        self._image = image
        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit
        self._timeout = timeout

    # ---- Detection ----

    def detect_mode(self) -> EnvMode:
        """Auto-detect the best execution mode."""
        if self._is_running_in_docker():
            if self._has_docker_socket():
                return EnvMode.DOCKER
            # Inside Docker without socket — check if CLI tools are baked in
            if self._has_any_cli_locally():
                return EnvMode.LOCAL
            return EnvMode.UNAVAILABLE

        if self._has_any_cli_locally():
            return EnvMode.LOCAL
        if self._is_docker_available():
            return EnvMode.DOCKER
        return EnvMode.UNAVAILABLE

    async def get_status(self) -> EnvStatus:
        """Build a comprehensive status report."""
        status = EnvStatus(
            running_in_docker=self._is_running_in_docker(),
            docker_available=self._is_docker_available(),
            docker_socket=self._has_docker_socket(),
            coding_image_name=self._image,
        )

        status.mode = self.detect_mode()

        if status.docker_available:
            status.coding_image_pulled = await self._is_image_pulled(self._image)

        for tool_name, binary in _CLI_BINARIES.items():
            ts = CLIToolStatus(name=tool_name)
            path = shutil.which(binary)
            if path:
                ts.installed = True
                ts.version = await self._get_cli_version(binary)
            status.cli_tools[tool_name] = ts

        # API key status from VortGit settings
        try:
            from openvort.plugins.vortgit.config import VortGitSettings
            vg = VortGitSettings()
            status.api_keys["claude-code"] = bool(vg.claude_code_api_key)
            status.api_keys["aider"] = bool(vg.aider_api_key)
        except Exception:
            pass

        return status

    # ---- Execution ----

    async def execute(
        self,
        command: list[str],
        *,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        mode: EnvMode | None = None,
        on_output: "Callable[[str], Any] | None" = None,
    ) -> ExecResult:
        """Execute a command in the detected (or specified) environment.

        Args:
            on_output: Optional callback invoked with each line of stdout/stderr
                       as the subprocess produces it (for live streaming to UI).
        """
        effective_mode = mode or self.detect_mode()
        effective_timeout = timeout or self._timeout

        if effective_mode == EnvMode.UNAVAILABLE:
            return ExecResult(
                stderr="Coding environment not available. Run: openvort coding setup",
                exit_code=1,
            )

        if effective_mode == EnvMode.LOCAL:
            return await self._exec_local(command, cwd=cwd, env=env, timeout=effective_timeout, on_output=on_output)
        else:
            return await self._exec_docker(command, cwd=cwd, env=env, timeout=effective_timeout, on_output=on_output)

    async def pull_image(self) -> ExecResult:
        """Pull the coding sandbox Docker image."""
        if not self._is_docker_available():
            return ExecResult(stderr="Docker is not available", exit_code=1)

        log.info(f"Pulling coding sandbox image: {self._image}")
        proc = await asyncio.create_subprocess_exec(
            "docker", "pull", self._image,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
            return ExecResult(
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ExecResult(stderr="Image pull timed out (600s)", exit_code=124)

    # ---- Local execution ----

    async def _exec_local(
        self,
        command: list[str],
        *,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 300,
        on_output: "Callable[[str], Any] | None" = None,
    ) -> ExecResult:
        import os
        merged_env = {**os.environ, **(env or {})}

        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )

        if not on_output:
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return ExecResult(
                    stdout=stdout.decode(errors="replace"),
                    stderr=stderr.decode(errors="replace"),
                    exit_code=proc.returncode or 0,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ExecResult(stderr=f"Execution timed out ({timeout}s)", exit_code=124)

        # Streaming mode: read stdout/stderr line by line, call on_output
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        async def _read_stream(stream, parts, is_stdout=True):
            async for raw_line in stream:
                line = raw_line.decode(errors="replace")
                parts.append(line)
                if is_stdout:
                    try:
                        on_output(line)
                    except Exception:
                        pass

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _read_stream(proc.stdout, stdout_parts, is_stdout=True),
                    _read_stream(proc.stderr, stderr_parts, is_stdout=False),
                ),
                timeout=timeout,
            )
            await proc.wait()
            return ExecResult(
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            return ExecResult(
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts) + f"\nExecution timed out ({timeout}s)",
                exit_code=124,
            )

    # ---- Docker execution ----

    async def _exec_docker(
        self,
        command: list[str],
        *,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 300,
        on_output: "Callable[[str], Any] | None" = None,
    ) -> ExecResult:
        docker_cmd = [
            "docker", "run", "--rm",
            "--memory", self._memory_limit,
            f"--cpus={self._cpu_limit}",
            "--network", "host",
        ]

        if cwd:
            docker_cmd.extend(["-v", f"{cwd}:/workspace", "-w", "/workspace"])

        for k, v in (env or {}).items():
            docker_cmd.extend(["-e", f"{k}={v}"])

        docker_cmd.append(self._image)
        docker_cmd.extend(command)

        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if not on_output:
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return ExecResult(
                    stdout=stdout.decode(errors="replace"),
                    stderr=stderr.decode(errors="replace"),
                    exit_code=proc.returncode or 0,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ExecResult(stderr=f"Docker execution timed out ({timeout}s)", exit_code=124)

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        async def _read_stream(stream, parts, is_stdout=True):
            async for raw_line in stream:
                line = raw_line.decode(errors="replace")
                parts.append(line)
                if is_stdout:
                    try:
                        on_output(line)
                    except Exception:
                        pass

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _read_stream(proc.stdout, stdout_parts, is_stdout=True),
                    _read_stream(proc.stderr, stderr_parts, is_stdout=False),
                ),
                timeout=timeout,
            )
            await proc.wait()
            return ExecResult(
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            return ExecResult(
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts) + f"\nDocker execution timed out ({timeout}s)",
                exit_code=124,
            )

    # ---- Probes ----

    @staticmethod
    def _is_running_in_docker() -> bool:
        if Path("/.dockerenv").exists():
            return True
        try:
            text = Path("/proc/1/cgroup").read_text()
            return "docker" in text or "containerd" in text
        except Exception:
            return False

    @staticmethod
    def _has_docker_socket() -> bool:
        return Path("/var/run/docker.sock").exists()

    @staticmethod
    def _is_docker_available() -> bool:
        return shutil.which("docker") is not None

    @staticmethod
    def _has_any_cli_locally() -> bool:
        return any(shutil.which(b) for b in _CLI_BINARIES.values())

    @staticmethod
    async def _is_image_pulled(image: str) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "images", "-q", image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            return bool(stdout.strip())
        except Exception:
            return False

    @staticmethod
    async def _get_cli_version(binary: str) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            output = (stdout or stderr).decode(errors="replace").strip()
            return output.split("\n")[0][:100]
        except Exception:
            return ""
