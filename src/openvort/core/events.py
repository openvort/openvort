"""
事件总线

轻量级发布/订阅机制，用于模块间解耦通信。
"""

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine

from openvort.utils.logging import get_logger

log = get_logger("core.events")

# 事件处理器类型
EventHandler = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    """异步事件总线"""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event: str, handler: EventHandler) -> None:
        """订阅事件"""
        self._handlers[event].append(handler)

    def off(self, event: str, handler: EventHandler) -> None:
        """取消订阅"""
        if event in self._handlers:
            self._handlers[event] = [h for h in self._handlers[event] if h != handler]

    async def emit(self, event: str, **kwargs) -> None:
        """触发事件，所有 handler 并发执行"""
        handlers = self._handlers.get(event, [])
        if not handlers:
            return

        log.debug(f"触发事件 '{event}'，{len(handlers)} 个处理器")
        tasks = [asyncio.create_task(h(**kwargs)) for h in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log.error(f"事件 '{event}' 处理器 {handlers[i].__name__} 异常: {result}")


# 全局事件总线
event_bus = EventBus()
