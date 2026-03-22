"""
消息调度器

debounce + per-user 处理锁 + 消息队列 + 中间回复丢弃。
解决 IM 场景下用户连续发消息导致重复回复的问题。
"""

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable

from openvort.core.engine.context import RequestContext
from openvort.utils.logging import get_logger

log = get_logger("core.dispatcher")

# 处理函数签名: (ctx, content) -> reply
ProcessFn = Callable[[RequestContext, str], Awaitable[str]]


class MessageDispatcher:
    """per-user 消息调度器

    收到消息后 debounce 等待，收集同一用户的后续消息，
    合并后统一处理。处理期间新消息入队列，处理完后排空队列。
    """

    def __init__(
        self,
        max_pending: int = 10,
        lock_timeout: float = 60.0,
        debounce: float = 2.0,
    ):
        """
        Args:
            max_pending: 每个用户的 pending 队列上限
            lock_timeout: 单次处理超时（秒），防止死锁
            debounce: 收到消息后等待多久再处理（秒），收集后续消息
        """
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._pending: dict[str, list[str]] = defaultdict(list)
        self._pending_images: dict[str, list[dict]] = defaultdict(list)  # 累积图片
        self._processing: set[str] = set()  # 正在 LLM 处理中的 user_key
        self._debounce_tasks: dict[str, asyncio.Task] = {}
        self._debounce_ctx: dict[str, RequestContext] = {}
        self._debounce_fns: dict[str, tuple[ProcessFn, Callable]] = {}
        self._max_pending = max_pending
        self._lock_timeout = lock_timeout
        self._debounce = debounce

    async def dispatch(
        self,
        ctx: RequestContext,
        content: str,
        process_fn: ProcessFn,
        send_fn: Callable[[str], Awaitable[None]] | None = None,
    ) -> str | None:
        """调度消息处理

        Returns:
            始终返回 None，回复通过 send_fn 异步发送
        """
        user_key = f"{ctx.channel}:{ctx.user_id}"

        # 空消息且无图片直接丢弃
        if (not content or not content.strip()) and not ctx.images:
            log.warning(f"[{user_key}] 收到空消息，丢弃")
            return None

        # 如果正在 LLM 处理中，消息入 pending 队列
        if user_key in self._processing:
            self._enqueue(user_key, content)
            self._accumulate_images(user_key, ctx.images)
            return None

        # 消息入队列
        self._enqueue(user_key, content)

        # 保存 ctx 和回调（累积图片）
        if user_key in self._debounce_ctx:
            # debounce 期间有新消息，累积图片
            self._accumulate_images(user_key, ctx.images)
        else:
            self._debounce_ctx[user_key] = ctx
            self._pending_images[user_key] = list(ctx.images)
        if send_fn:
            self._debounce_fns[user_key] = (process_fn, send_fn)

        # 重置 debounce 定时器（每次新消息都重置）
        if user_key in self._debounce_tasks:
            self._debounce_tasks[user_key].cancel()

        self._debounce_tasks[user_key] = asyncio.create_task(
            self._debounce_then_process(user_key, process_fn, send_fn)
        )

        return None

    async def _debounce_then_process(
        self,
        user_key: str,
        process_fn: ProcessFn,
        send_fn: Callable[[str], Awaitable[None]] | None,
    ) -> None:
        """等待 debounce 时间后，合并队列消息并处理"""
        try:
            await asyncio.sleep(self._debounce)
        except asyncio.CancelledError:
            # debounce 被重置（有新消息），不处理
            return

        # debounce 结束，清理定时器
        self._debounce_tasks.pop(user_key, None)

        ctx = self._debounce_ctx.pop(user_key, None)
        self._debounce_fns.pop(user_key, None)
        if not ctx:
            return

        # 把累积的图片写入 ctx
        ctx.images = self._pending_images.pop(user_key, [])

        lock = self._locks[user_key]
        async with lock:
            self._processing.add(user_key)
            try:
                reply = await self._process_with_drain(
                    ctx, process_fn, user_key
                )
            finally:
                self._processing.discard(user_key)

        if reply and send_fn:
            await send_fn(reply)

    async def _process_with_drain(
        self,
        ctx: RequestContext,
        process_fn: ProcessFn,
        user_key: str,
    ) -> str:
        """取出队列消息处理，循环排空，返回最终回复"""
        while True:
            # 取出当前队列
            pending = self._pending.pop(user_key, [])
            if not pending:
                return ""

            content = "\n".join(pending)
            log.info(f"[{user_key}] 处理 {len(pending)} 条消息: {content[:50]}")

            try:
                reply = await asyncio.wait_for(
                    process_fn(ctx, content),
                    timeout=self._lock_timeout,
                )
            except asyncio.TimeoutError:
                log.error(f"[{user_key}] 处理超时 ({self._lock_timeout}s)")
                return "处理超时，请稍后再试。"

            # 检查处理期间是否有新消息入队
            if not self._pending.get(user_key):
                return reply

            # 有新消息，丢弃当前回复继续处理
            log.info(
                f"[{user_key}] 丢弃中间回复，继续处理 "
                f"{len(self._pending[user_key])} 条新消息"
            )

    def _enqueue(self, user_key: str, content: str) -> None:
        """消息入队列"""
        if not content or not content.strip():
            return  # 空文本不入队（可能是纯图片消息）
        pending = self._pending[user_key]
        if len(pending) >= self._max_pending:
            pending.pop(0)
            log.warning(f"[{user_key}] pending 队列已满，丢弃最早消息")
        pending.append(content)
        log.info(f"[{user_key}] 消息入队 (pending={len(pending)}): {content[:30]}")

    def _accumulate_images(self, user_key: str, images: list[dict]) -> None:
        """累积图片到 pending_images"""
        if images:
            self._pending_images[user_key].extend(images)
            log.info(f"[{user_key}] 图片累积 (+{len(images)}, 总计={len(self._pending_images[user_key])})")
