"""
Remote node executor protocol and registry.

Defines the interface that each node type (docker, etc.) must implement,
and provides a registry for dispatching operations by node_type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

log = get_logger("core.remote_executor")


@runtime_checkable
class RemoteNodeExecutor(Protocol):
    """Protocol that every remote node type must implement."""

    async def test_connection(self, gateway_url: str, token: str) -> dict:
        """Test connectivity. Returns {"ok": bool, "message": str}."""
        ...

    async def send_instruction(
        self,
        gateway_url: str,
        token: str,
        instruction: str,
        *,
        context: dict | None = None,
        timeout: int = 300,
        on_text: "Callable[[str], None] | None" = None,
        extra_system_prompt: str = "",
    ) -> dict:
        """Execute a work instruction on the remote node."""
        ...


_executors: dict[str, RemoteNodeExecutor] = {}


def register_executor(node_type: str, executor: RemoteNodeExecutor) -> None:
    """Register an executor implementation for a given node type."""
    _executors[node_type] = executor
    log.info(f"Registered remote node executor: {node_type}")


def get_executor(node_type: str) -> RemoteNodeExecutor | None:
    """Look up the executor for a node type."""
    return _executors.get(node_type)


def available_node_types() -> list[str]:
    """Return all registered node type names."""
    return list(_executors.keys())
