"""
Docker 沙箱执行

为非 main session 提供隔离的命令执行环境。
支持三种模式：
- off: 不使用沙箱（默认）
- non-main: 仅非 main session 使用沙箱
- all: 所有 session 都使用沙箱
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from openvort.utils.logging import get_logger

log = get_logger("core.sandbox")

# 默认沙箱 Docker 镜像
DEFAULT_IMAGE = "python:3.11-slim"
# 容器最大存活时间（秒）
MAX_CONTAINER_TTL = 3600


@dataclass
class SandboxConfig:
    """沙箱配置"""
    mode: str = "off"  # off | non-main | all
    image: str = DEFAULT_IMAGE
    memory_limit: str = "256m"
    cpu_limit: float = 0.5
    timeout: int = 30  # 单次执行超时（秒）
    network_enabled: bool = False  # 是否允许网络访问


@dataclass
class Container:
    """沙箱容器"""
    container_id: str = ""
    session_key: str = ""
    created_at: float = 0


class SandboxManager:
    """Docker 沙箱管理器"""

    def __init__(self, config: SandboxConfig | None = None):
        self._config = config or SandboxConfig()
        self._containers: dict[str, Container] = {}  # session_key -> container

    @property
    def enabled(self) -> bool:
        return self._config.mode != "off"

    def should_sandbox(self, channel: str, user_id: str) -> bool:
        """判断是否应该使用沙箱

        main session 定义为 cli:debug 或 web:admin
        """
        if self._config.mode == "off":
            return False
        if self._config.mode == "all":
            return True
        # non-main: 排除 main session
        is_main = (channel == "cli" and user_id == "debug") or \
                  (channel == "web" and user_id == "admin")
        return not is_main

    async def execute(self, session_key: str, command: str) -> dict:
        """在沙箱中执行命令

        Args:
            session_key: 会话标识（channel:user_id）
            command: 要执行的命令

        Returns:
            {"stdout": str, "stderr": str, "exit_code": int}
        """
        if not self._is_docker_available():
            return {"stdout": "", "stderr": "Docker 不可用，无法创建沙箱", "exit_code": 1}

        container_id = await self._get_or_create_container(session_key)
        if not container_id:
            return {"stdout": "", "stderr": "创建沙箱容器失败", "exit_code": 1}

        try:
            result = await self._exec_in_container(container_id, command)
            return result
        except asyncio.TimeoutError:
            return {"stdout": "", "stderr": f"执行超时（{self._config.timeout}s）", "exit_code": 124}
        except Exception as e:
            log.error(f"沙箱执行异常: {e}")
            return {"stdout": "", "stderr": str(e), "exit_code": 1}

    async def cleanup(self, session_key: str) -> None:
        """清理指定会话的沙箱容器"""
        container = self._containers.pop(session_key, None)
        if container and container.container_id:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "rm", "-f", container.container_id,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
                log.info(f"已清理沙箱容器: {container.container_id[:12]}")
            except Exception as e:
                log.warning(f"清理容器失败: {e}")

    async def cleanup_all(self) -> None:
        """清理所有沙箱容器"""
        keys = list(self._containers.keys())
        for key in keys:
            await self.cleanup(key)

    # ---- 内部方法 ----

    def _is_docker_available(self) -> bool:
        """检查 Docker 是否可用"""
        import shutil
        return shutil.which("docker") is not None

    async def _get_or_create_container(self, session_key: str) -> str:
        """获取或创建沙箱容器"""
        container = self._containers.get(session_key)
        if container and container.container_id:
            # 检查容器是否还在运行
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "inspect", "-f", "{{.State.Running}}", container.container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                if b"true" in stdout:
                    return container.container_id
            except Exception:
                pass

        # 创建新容器
        container_name = f"openvort-sandbox-{uuid.uuid4().hex[:8]}"
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--memory", self._config.memory_limit,
            f"--cpus={self._config.cpu_limit}",
        ]
        if not self._config.network_enabled:
            cmd.append("--network=none")
        cmd.extend([self._config.image, "sleep", str(MAX_CONTAINER_TTL)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                log.error(f"创建沙箱容器失败: {stderr.decode()}")
                return ""

            container_id = stdout.decode().strip()
            import time
            self._containers[session_key] = Container(
                container_id=container_id,
                session_key=session_key,
                created_at=time.time(),
            )
            log.info(f"创建沙箱容器: {container_id[:12]} for {session_key}")
            return container_id
        except Exception as e:
            log.error(f"创建沙箱容器异常: {e}")
            return ""

    async def _exec_in_container(self, container_id: str, command: str) -> dict:
        """在容器中执行命令"""
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id, "sh", "-c", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._config.timeout
            )
            return {
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "exit_code": proc.returncode or 0,
            }
        except asyncio.TimeoutError:
            proc.kill()
            raise
