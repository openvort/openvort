"""
PluginAPI — runtime API provided to plugins via activate().

Wraps PluginRegistry (tool/prompt), EventBus (events), and a slot store,
presenting a single facade that plugins interact with.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine

from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from openvort.core.events import EventBus
    from openvort.plugin.base import BaseTool
    from openvort.plugin.registry import PluginRegistry

log = get_logger("plugin.api")

EventHandler = Callable[..., Coroutine[Any, Any, None]]


class PluginAPI:
    """Runtime API provided to each plugin during activate()."""

    def __init__(
        self,
        registry: PluginRegistry,
        event_bus: EventBus,
        db_factory_getter: Callable | None = None,
    ):
        self._registry = registry
        self._event_bus = event_bus
        self._db_factory_getter = db_factory_getter

    # ---- Tool / Prompt registration ----

    def register_tool(self, tool: BaseTool) -> None:
        self._registry.register_tool(tool)

    def register_prompt(self, content: str, source: str = "") -> None:
        self._registry.register_prompt(content, source=source)

    # ---- Slot (exclusive capability providers) ----

    def register_slot(self, name: str, provider: Any) -> None:
        self._registry.register_slot(name, provider)

    def get_slot(self, name: str) -> Any | None:
        return self._registry.get_slot(name)

    # ---- Events ----

    def emit(self, event: str, data: dict | None = None) -> None:
        """Fire-and-forget event emission (schedules coroutine)."""
        import asyncio

        async def _do_emit():
            await self._event_bus.emit(event, **(data or {}))

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_do_emit())
        except RuntimeError:
            pass

    def on(self, event: str, handler: EventHandler) -> None:
        self._event_bus.on(event, handler)

    # ---- Runtime services ----

    @property
    def db(self) -> Callable:
        """Returns the async session factory getter."""
        if self._db_factory_getter is None:
            from openvort.db.engine import get_session_factory
            return get_session_factory
        return self._db_factory_getter
