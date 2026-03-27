"""
AI Employee Bot Runner — per-employee WebSocket connection for WeCom smart bot.

Each EmployeeBotRunner manages an independent WebSocket to wss://openws.work.weixin.qq.com
using the employee's own bot_id + bot_secret credentials, routes incoming messages
through the stream handler with the correct target_member_id context.
"""

import asyncio
import base64
import json
import time
from uuid import uuid4

import httpx

from openvort.channels.wecom.think_parser import parse_thinking_content
from openvort.plugin.base import Message
from openvort.utils.logging import get_logger

BOT_WS_URL = "wss://openws.work.weixin.qq.com"
BOT_WS_HEARTBEAT_INTERVAL = 30
BOT_STREAM_MAX_BYTES = 20000
BOT_STREAM_THROTTLE_INTERVAL = 0.3
BOT_DEBOUNCE_SECONDS = 2.0

log = get_logger("channels.wecom.employee_bot")


class EmployeeBotRunner:
    """Manages one WebSocket connection for an AI employee's dedicated WeCom bot."""

    def __init__(
        self,
        bot_id: str,
        bot_secret: str,
        member_id: str,
        member_name: str,
        stream_handler,
        *,
        inbox=None,
    ):
        self.bot_id = bot_id
        self.bot_secret = bot_secret
        self.member_id = member_id
        self.member_name = member_name
        self._stream_handler = stream_handler
        self._inbox = inbox

        self._running = False
        self._ws = None
        self._ws_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._req_ids: dict[str, str] = {}
        self._pending_acks: dict[str, asyncio.Future] = {}
        self._debounce_timers: dict[str, asyncio.Task] = {}
        self._pending_msgs: dict[str, list[Message]] = {}
        self._stream_ids: dict[str, str] = {}
        self._processing: set[str] = set()

    async def start(self) -> None:
        self._running = True
        self._ws_task = asyncio.create_task(self._ws_loop())
        log.info(f"Employee bot started: {self.member_name} (member_id={self.member_id}, bot_id={self.bot_id})")

    async def stop(self) -> None:
        self._running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        log.info(f"Employee bot stopped: {self.member_name}")

    # ---- WebSocket lifecycle ----

    async def _ws_loop(self) -> None:
        import websockets

        retry_delay = 1.0
        max_retry_delay = 60.0

        while self._running:
            try:
                async with websockets.connect(
                    BOT_WS_URL, ping_interval=None, ping_timeout=None,
                ) as ws:
                    self._ws = ws

                    auth_frame = {
                        "cmd": "aibot_subscribe",
                        "headers": {"req_id": str(uuid4())},
                        "body": {"secret": self.bot_secret, "bot_id": self.bot_id},
                    }
                    await ws.send(json.dumps(auth_frame))

                    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                    if resp.get("errcode", -1) != 0:
                        raise RuntimeError(
                            f"Employee bot auth failed: errcode={resp.get('errcode')}, "
                            f"errmsg={resp.get('errmsg')}"
                        )
                    log.info(f"Employee bot WS auth ok: {self.member_name}")
                    retry_delay = 1.0

                    self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))

                    async for raw_msg in ws:
                        if not self._running:
                            break
                        try:
                            await self._handle_ws_message(raw_msg)
                        except Exception as e:
                            log.error(f"Employee bot [{self.member_name}] message error: {e}", exc_info=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    log.warning(
                        f"Employee bot [{self.member_name}] disconnected ({e}), "
                        f"retry in {retry_delay:.0f}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_retry_delay)
            finally:
                self._ws = None
                if self._heartbeat_task and not self._heartbeat_task.done():
                    self._heartbeat_task.cancel()
                    self._heartbeat_task = None
                for fut in self._pending_acks.values():
                    if not fut.done():
                        fut.cancel()
                self._pending_acks.clear()

    async def _heartbeat_loop(self, ws) -> None:
        try:
            while True:
                await asyncio.sleep(BOT_WS_HEARTBEAT_INTERVAL)
                frame = {"cmd": "ping", "headers": {"req_id": str(uuid4())}}
                await ws.send(json.dumps(frame))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning(f"Employee bot [{self.member_name}] heartbeat error: {e}")

    async def _send_frame(self, frame: dict) -> None:
        ws = self._ws
        if not ws:
            log.error(f"Employee bot [{self.member_name}] WS not connected, cannot send")
            return
        await ws.send(json.dumps(frame))

    # ---- Message handling ----

    async def _handle_ws_message(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        data = json.loads(raw)
        cmd = data.get("cmd", "")

        if not cmd and "errcode" in data:
            req_id = data.get("headers", {}).get("req_id", "")
            fut = self._pending_acks.get(req_id)
            if fut and not fut.done():
                fut.set_result(data)
            return

        if cmd == "aibot_msg_callback":
            await self._handle_msg_callback(data)
            return

        if cmd == "aibot_event_callback":
            await self._handle_event_callback(data)
            return

    async def _handle_msg_callback(self, data: dict) -> None:
        body = data.get("body", {})
        req_id = data.get("headers", {}).get("req_id", "")
        msgtype = body.get("msgtype", "")
        from_user = body.get("from", {}).get("userid", "")
        chat_type = body.get("chattype", "single")
        chat_id = body.get("chatid", "")

        msgid = body.get("msgid", "")
        if msgid and self._inbox:
            if not await self._inbox.try_claim("wecom", msgid):
                return

        content = ""
        images: list[dict] = []

        if msgtype == "text":
            content = body.get("text", {}).get("content", "")
        elif msgtype == "voice":
            content = body.get("voice", {}).get("content", "")
            if not content:
                return
        elif msgtype == "image":
            img = body.get("image", {})
            content = "[用户发送了图片]"
            if img.get("url"):
                images = [{"pic_url": img["url"], "aes_key": img.get("aeskey", "")}]
        elif msgtype == "mixed":
            items = body.get("mixed", {}).get("msg_item", [])
            text_parts = []
            for item in items:
                if item.get("msgtype") == "text" and item.get("text", {}).get("content"):
                    text_parts.append(item["text"]["content"])
                elif item.get("msgtype") == "image" and item.get("image", {}).get("url"):
                    images.append({
                        "pic_url": item["image"]["url"],
                        "aes_key": item["image"].get("aeskey", ""),
                    })
            content = "\n".join(text_parts)
            if not content and images:
                content = "[用户发送了图片]"
        elif msgtype == "file":
            file_info = body.get("file", {})
            content = f"[用户发送了文件] {file_info.get('name', '')}"
        elif msgtype == "stream":
            return
        else:
            return

        if not from_user or not content:
            return

        quote_text = ""
        if body.get("quote"):
            q = body["quote"]
            if q.get("text", {}).get("content"):
                quote_text = q["text"]["content"]
            elif q.get("voice", {}).get("content"):
                quote_text = q["voice"]["content"]
        if quote_text:
            content = f"[引用: {quote_text[:100]}]\n{content}"

        msg = Message(
            content=content,
            sender_id=from_user,
            channel="wecom",
            msg_type=msgtype if msgtype != "mixed" else "text",
            images=images,
            raw={
                "_bot_req_id": req_id,
                "_bot_chat_id": chat_id,
                "_bot_chat_type": chat_type,
                "_employee_member_id": self.member_id,
                "msgid": msgid,
                "aibotid": body.get("aibotid", ""),
            },
        )

        reply_key = chat_id if chat_id else from_user
        self._req_ids[reply_key] = req_id

        if images:
            msg.images = await self._download_images(images)

        log.info(f"Employee bot [{self.member_name}] msg: {from_user} ({chat_type}) -> {content[:80]}")

        await self._debounce_enqueue(msg, req_id, chat_id)

    async def _handle_event_callback(self, data: dict) -> None:
        body = data.get("body", {})
        req_id = data.get("headers", {}).get("req_id", "")
        event = body.get("event", {})
        event_type = event.get("eventtype", "")

        if event_type == "enter_chat" and req_id:
            welcome = f"你好！我是{self.member_name}，有什么可以帮你的吗？"
            frame = {
                "cmd": "aibot_respond_welcome_msg",
                "headers": {"req_id": req_id},
                "body": {"msgtype": "text", "text": {"content": welcome}},
            }
            await self._send_frame(frame)

    # ---- Debounce + streaming ----

    async def _debounce_enqueue(self, msg: Message, req_id: str, chat_id: str) -> None:
        user_key = chat_id if chat_id else msg.sender_id

        existing = self._debounce_timers.get(user_key)
        if existing and not existing.done():
            existing.cancel()

        self._pending_msgs.setdefault(user_key, []).append(msg)

        if len(self._pending_msgs[user_key]) == 1 and user_key not in self._processing:
            try:
                stream_id = str(uuid4())
                self._stream_ids[user_key] = stream_id
                frame = {
                    "cmd": "aibot_respond_msg",
                    "headers": {"req_id": req_id},
                    "body": {
                        "msgtype": "stream",
                        "stream": {"id": stream_id, "finish": False, "content": "", "thinking_content": "思考中..."},
                    },
                }
                await self._send_frame(frame)
            except Exception as e:
                log.warning(f"Employee bot [{self.member_name}] thinking frame error: {e}")

        self._debounce_timers[user_key] = asyncio.create_task(
            self._debounce_fire(user_key, req_id, chat_id)
        )

    async def _debounce_fire(self, user_key: str, req_id: str, chat_id: str) -> None:
        await asyncio.sleep(BOT_DEBOUNCE_SECONDS)

        if user_key in self._processing:
            return

        pending = self._pending_msgs.pop(user_key, [])
        if not pending:
            return

        stream_id = self._stream_ids.pop(user_key, str(uuid4()))

        self._processing.add(user_key)
        try:
            if len(pending) == 1:
                merged_msg = pending[0]
            else:
                texts = [m.content for m in pending if m.content]
                all_images = []
                for m in pending:
                    all_images.extend(m.images or [])
                merged_msg = Message(
                    content="\n".join(texts),
                    sender_id=pending[-1].sender_id,
                    channel="wecom",
                    msg_type=pending[-1].msg_type,
                    images=all_images,
                    raw=pending[-1].raw,
                )

            await self._handle_streaming(merged_msg, req_id, chat_id, stream_id)
        except Exception as e:
            log.error(f"Employee bot [{self.member_name}] stream error: {e}", exc_info=True)
        finally:
            self._processing.discard(user_key)
            if self._pending_msgs.get(user_key):
                new_req_id = self._req_ids.get(user_key, req_id)
                self._debounce_timers[user_key] = asyncio.create_task(
                    self._debounce_fire(user_key, new_req_id, chat_id)
                )

    async def _handle_streaming(self, msg: Message, req_id: str, chat_id: str,
                                stream_id: str = "") -> None:
        if not stream_id:
            stream_id = str(uuid4())
        visible_text = ""
        thinking_text = ""
        last_send_time = 0.0
        last_send_len = 0
        has_native_thinking = False

        async def send_stream_frame(finish: bool = False) -> None:
            nonlocal last_send_time, last_send_len
            final_visible = visible_text
            final_thinking = thinking_text

            if not has_native_thinking and visible_text:
                parsed_visible, parsed_thinking, _ = parse_thinking_content(visible_text)
                if parsed_thinking:
                    final_visible = parsed_visible
                    final_thinking = parsed_thinking

            content_bytes = final_visible.encode("utf-8")
            if len(content_bytes) > BOT_STREAM_MAX_BYTES:
                final_visible = content_bytes[:BOT_STREAM_MAX_BYTES].decode("utf-8", errors="ignore")
                if finish:
                    final_visible += "\n\n...(内容过长，已截断)"

            frame = {
                "cmd": "aibot_respond_msg",
                "headers": {"req_id": req_id},
                "body": {
                    "msgtype": "stream",
                    "stream": {"id": stream_id, "finish": finish, "content": final_visible},
                },
            }
            if final_thinking:
                frame["body"]["stream"]["thinking_content"] = final_thinking

            try:
                await self._send_frame(frame)
                last_send_time = time.monotonic()
                last_send_len = len(visible_text)
            except Exception as e:
                log.error(f"Employee bot [{self.member_name}] stream frame error: {e}")

        try:
            async for event in self._stream_handler(msg):
                etype = event.get("type", "")

                if etype == "thinking_delta":
                    has_native_thinking = True
                    thinking_text += event.get("text", "")
                elif etype == "text_delta":
                    visible_text += event.get("text", "")
                elif etype == "text":
                    visible_text = event.get("text", "")
                elif etype in ("tool_use", "tool_result", "tool_output", "tool_progress"):
                    continue

                now = time.monotonic()
                text_changed = len(visible_text) - last_send_len >= 200
                time_elapsed = now - last_send_time >= BOT_STREAM_THROTTLE_INTERVAL
                if text_changed or time_elapsed:
                    await send_stream_frame()
        except Exception as e:
            log.error(f"Employee bot [{self.member_name}] stream handler error: {e}", exc_info=True)
            if not visible_text:
                visible_text = f"抱歉，处理出现异常：{e}"

        await send_stream_frame(finish=True)
        log.info(f"Employee bot [{self.member_name}] stream done: len={len(visible_text)}")

    # ---- Image download ----

    async def _download_images(self, images: list[dict]) -> list[dict]:
        result = []
        for img in images:
            pic_url = img.get("pic_url", "")
            if not pic_url:
                continue
            try:
                aes_key = img.get("aes_key", "")
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(pic_url)
                    resp.raise_for_status()
                    raw_bytes = resp.content

                if aes_key and not self._is_plain_image(raw_bytes):
                    raw_bytes = self._decrypt_media(raw_bytes, aes_key)

                media_type = self._detect_image_type(raw_bytes)
                img_b64 = base64.b64encode(raw_bytes).decode("ascii")
                result.append({**img, "data": img_b64, "media_type": media_type})
            except Exception as e:
                log.error(f"Employee bot [{self.member_name}] image download error: {e}")
        return result

    @staticmethod
    def _is_plain_image(data: bytes) -> bool:
        return (
            data[:3] == b"\xff\xd8\xff"
            or data[:8] == b"\x89PNG\r\n\x1a\n"
            or data[:4] == b"GIF8"
            or data[:4] == b"RIFF"
        )

    @staticmethod
    def _decrypt_media(data: bytes, aes_key: str) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7

        key = base64.b64decode(aes_key)
        iv = key[:16]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(data) + decryptor.finalize()
        unpadder = PKCS7(128).unpadder()
        return unpadder.update(decrypted) + unpadder.finalize()

    @staticmethod
    def _detect_image_type(data: bytes) -> str:
        if data[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if data[:4] == b"GIF8":
            return "image/gif"
        if data[:4] == b"RIFF":
            return "image/webp"
        return "image/jpeg"


class EmployeeBotManager:
    """Manages all AI employee bot connections. Loads from DB at startup."""

    def __init__(self):
        self._runners: dict[str, EmployeeBotRunner] = {}  # bot_db_id -> runner

    async def start_all(self, session_factory, stream_handler_factory, inbox=None) -> int:
        """Load active wecom ChannelBots from DB and start runners.

        Args:
            session_factory: SQLAlchemy async session factory
            stream_handler_factory: callable(member_id) -> stream_handler
            inbox: optional InboxService for dedup

        Returns:
            Number of bots started
        """
        from sqlalchemy import select
        from openvort.db.models import ChannelBot
        from openvort.contacts.models import Member

        async with session_factory() as session:
            result = await session.execute(
                select(ChannelBot).where(
                    ChannelBot.channel_type == "wecom",
                    ChannelBot.status == "active",
                )
            )
            bots = result.scalars().all()

            if not bots:
                return 0

            member_ids = [b.member_id for b in bots]
            member_result = await session.execute(
                select(Member).where(Member.id.in_(member_ids))
            )
            members = {m.id: m for m in member_result.scalars().all()}

        started = 0
        for bot in bots:
            creds = json.loads(bot.credentials) if bot.credentials else {}
            bot_id = creds.get("bot_id", "")
            bot_secret = creds.get("bot_secret", "")
            if not bot_id or not bot_secret:
                log.warning(f"ChannelBot {bot.id} missing credentials, skip")
                continue

            member = members.get(bot.member_id)
            if not member:
                log.warning(f"ChannelBot {bot.id} member {bot.member_id} not found, skip")
                continue

            handler = stream_handler_factory(bot.member_id)
            runner = EmployeeBotRunner(
                bot_id=bot_id,
                bot_secret=bot_secret,
                member_id=bot.member_id,
                member_name=member.name,
                stream_handler=handler,
                inbox=inbox,
            )
            await runner.start()
            self._runners[bot.id] = runner
            started += 1

        if started:
            log.info(f"Employee bot manager: {started} bot(s) started")
        return started

    async def stop_all(self) -> None:
        for runner in self._runners.values():
            await runner.stop()
        self._runners.clear()
