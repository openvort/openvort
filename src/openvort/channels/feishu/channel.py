"""
飞书 Channel

实现 BaseChannel 接口，支持飞书机器人消息收发。
支持两种模式：
- WebSocket 长连接（推荐，无需公网地址）
- Event Subscription 回调（需要公网地址）
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openvort.channels.feishu.api import FeishuAPI
from openvort.config.settings import FeishuSettings
from openvort.plugin.base import BaseChannel, Message, MessageHandler
from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    import lark_oapi as lark

log = get_logger("channels.feishu")

FEISHU_STREAM_UPDATE_THROTTLE = 0.35


def merge_streaming_text(previous_text: str | None, next_text: str | None) -> str:
    previous = previous_text or ""
    next_value = next_text or ""
    if not next_value:
        return previous
    if not previous or next_value == previous:
        return next_value
    if next_value.startswith(previous) or next_value.find(previous) >= 0:
        return next_value
    if previous.startswith(next_value) or previous.find(next_value) >= 0:
        return previous

    max_overlap = min(len(previous), len(next_value))
    for overlap in range(max_overlap, 0, -1):
        if previous[-overlap:] == next_value[:overlap]:
            return previous + next_value[overlap:]
    return previous + next_value


def truncate_summary(text: str, max_len: int = 50) -> str:
    clean = (text or "").replace("\n", " ").strip()
    if len(clean) <= max_len:
        return clean or "OpenVort"
    return clean[: max_len - 3] + "..."


class FeishuStreamingSession:
    """飞书流式卡片会话。"""

    def __init__(
        self,
        api: FeishuAPI,
        *,
        receive_id: str,
        receive_id_type: str = "open_id",
        reply_to_message_id: str = "",
        reply_in_thread: bool = False,
    ):
        self._api = api
        self._receive_id = receive_id
        self._receive_id_type = receive_id_type
        self._reply_to_message_id = reply_to_message_id
        self._reply_in_thread = reply_in_thread
        self._card_id = ""
        self._message_id = ""
        self._sequence = 0
        self._current_text = ""
        self._pending_text = ""
        self._queue: asyncio.Task | None = None
        self._last_update_at = 0.0
        self._closed = False

    async def start(self) -> None:
        if self._card_id or self._closed:
            return

        card = {
            "schema": "2.0",
            "config": {
                "streaming_mode": True,
                "summary": {"content": "[Generating...]"},
                "streaming_config": {
                    "print_frequency_ms": {"default": 50},
                    "print_step": {"default": 1},
                },
            },
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": "⏳ 正在思考...",
                        "element_id": "content",
                    },
                ],
            },
        }
        result = await self._api.create_card(card)
        self._card_id = result.get("data", {}).get("card_id", "")
        if not self._card_id:
            raise RuntimeError(f"创建飞书流式卡片失败: {result}")

        card_ref = {"type": "card", "data": {"card_id": self._card_id}}
        if self._reply_to_message_id:
            send_result = await self._api.reply_message(
                self._reply_to_message_id,
                "interactive",
                card_ref,
                extra_data={"reply_in_thread": self._reply_in_thread} if self._reply_in_thread else None,
            )
        else:
            send_result = await self._api.send_message(
                self._receive_id,
                "interactive",
                card_ref,
                receive_id_type=self._receive_id_type,
            )

        self._message_id = send_result.get("data", {}).get("message_id", "")
        self._sequence = 1

    async def update(self, text: str) -> None:
        if not text or self._closed:
            return
        merged = merge_streaming_text(self._pending_text or self._current_text, text)
        if not merged or merged == self._current_text:
            return

        self._pending_text = merged
        now = time.monotonic()
        if now - self._last_update_at < FEISHU_STREAM_UPDATE_THROTTLE:
            return
        await self._flush_pending()

    async def close(self, final_text: str = "") -> None:
        if self._closed:
            return
        self._closed = True
        if final_text:
            self._pending_text = merge_streaming_text(self._pending_text or self._current_text, final_text)
        await self._flush_pending()
        if not self._card_id:
            return

        self._sequence += 1
        await self._api.update_card_settings(
            self._card_id,
            {
                "config": {
                    "streaming_mode": False,
                    "summary": {"content": truncate_summary(self._current_text)},
                },
            },
            self._sequence,
        )

    async def _flush_pending(self) -> None:
        if not self._pending_text or not self._card_id:
            return
        target_text = self._pending_text
        self._pending_text = ""
        merged = merge_streaming_text(self._current_text, target_text)
        if not merged or merged == self._current_text:
            return
        self._current_text = merged
        self._sequence += 1
        self._last_update_at = time.monotonic()
        await self._api.update_card_markdown(self._card_id, merged, self._sequence)


class FeishuChannel(BaseChannel):
    """飞书通道。"""

    name = "feishu"
    display_name = "飞书"
    description = "飞书 IM 通道，支持 WebSocket 长连接/事件订阅，OpenAPI 发送消息"

    def __init__(self, settings: FeishuSettings | None = None):
        self._settings = settings or FeishuSettings()
        self._handler: MessageHandler | None = None
        self._running = False
        self._ws_mode = False
        self._ws_task: asyncio.Task | None = None
        self._ws_client: lark.ws.Client | None = None
        self._api: FeishuAPI | None = None
        self._stream_handler = None
        self._asr_service = None
        self._inbox = None  # InboxService, injected via set_inbox_service()

    def set_inbox_service(self, inbox) -> None:
        self._inbox = inbox

    @property
    def api(self) -> FeishuAPI:
        """延迟初始化 API 客户端。"""
        if self._api is None:
            self._api = FeishuAPI(
                app_id=self._settings.app_id,
                app_secret=self._settings.app_secret,
                api_base=self._settings.api_base,
            )
        return self._api

    async def start(self) -> None:
        if not self.is_configured():
            log.warning("飞书 Channel 未配置，跳过启动")
            return
        self._running = True
        log.info("飞书 Channel 已启动（等待 Event Subscription 回调）")

    async def stop(self) -> None:
        self._running = False
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
        if self._api is not None:
            await self._api.close()
            self._api = None
        log.info("飞书 Channel 已停止")

    async def send(self, target: str, message: Message) -> None:
        """发送消息到飞书用户或回复原消息。"""
        reply_to_message_id = message.raw.get("reply_to_message_id", "") if isinstance(message.raw, dict) else ""
        try:
            if message.msg_type == "markdown":
                card = {
                    "config": {"wide_screen_mode": True},
                    "elements": [
                        {"tag": "markdown", "content": message.content},
                    ],
                }
                if reply_to_message_id:
                    await self.api.reply_message(reply_to_message_id, "interactive", card)
                else:
                    await self.api.send_interactive(target, card)
                return

            if message.msg_type == "post" and isinstance(message.raw.get("post_content"), dict):
                post_content = message.raw["post_content"]
                if reply_to_message_id:
                    await self.api.reply_message(reply_to_message_id, "post", post_content)
                else:
                    await self.api.send_post(target, post_content)
                return

            if message.msg_type == "image" and message.raw.get("image_key"):
                image_key = message.raw["image_key"]
                if reply_to_message_id:
                    await self.api.reply_message(reply_to_message_id, "image", {"image_key": image_key})
                else:
                    await self.api.send_image(target, image_key)
                return

            if message.msg_type == "voice":
                voice_data = getattr(message, "voice_data", None) or message.raw.get("voice_data")
                if not voice_data or not voice_data.get("file_key"):
                    log.warning("发送飞书语音消息缺少 voice_data.file_key")
                    return
                if reply_to_message_id:
                    await self.api.reply_message(reply_to_message_id, "audio", {"file_key": voice_data["file_key"]})
                else:
                    await self.api.send_audio(target, voice_data["file_key"])
                return

            content = {"text": message.content}
            if reply_to_message_id:
                await self.api.reply_message(reply_to_message_id, "text", content)
            else:
                await self.api.send_text(target, message.content)
        except Exception as e:
            log.error(f"飞书发送异常: {e}")

    def on_message(self, handler: MessageHandler) -> None:
        self._handler = handler

    def set_stream_handler(self, handler) -> None:
        """设置飞书流式消息处理器。"""
        self._stream_handler = handler

    def set_asr_service(self, asr_service) -> None:
        self._asr_service = asr_service

    def is_configured(self) -> bool:
        return bool(self._settings.app_id and self._settings.app_secret)

    def get_sync_provider(self):
        """返回飞书通讯录同步提供者。"""
        from openvort.channels.feishu.sync import FeishuContactSyncProvider

        if not self.is_configured():
            return None
        return FeishuContactSyncProvider(self.api)

    def get_channel_prompt(self) -> str:
        prompt_file = Path(__file__).parent / "prompts" / "channel_style.md"
        if prompt_file.exists():
            try:
                return prompt_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""

    def get_max_reply_length(self) -> int:
        return 4000

    def get_config_schema(self) -> list[dict]:
        return [
            {"key": "app_id", "label": "App ID", "type": "string", "required": True, "secret": False, "placeholder": "飞书应用 App ID",
             "description": "飞书开放平台 → 应用详情 → 凭证与基础信息 → App ID"},
            {"key": "app_secret", "label": "App Secret", "type": "string", "required": True, "secret": True, "placeholder": "",
             "description": "与 App ID 一同获取的 App Secret"},
            {"key": "verification_token", "label": "Verification Token", "type": "string", "required": False, "secret": True, "placeholder": "事件订阅验证 Token",
             "description": "应用 → 事件订阅 → 配置请求地址时生成的 Verification Token"},
            {"key": "encrypt_key", "label": "Encrypt Key", "type": "string", "required": False, "secret": True, "placeholder": "事件订阅加密 Key",
             "description": "事件订阅中的 Encrypt Key，用于消息解密"},
            {"key": "api_base", "label": "API 地址", "type": "string", "required": False, "secret": False, "placeholder": "https://open.feishu.cn/open-apis",
             "description": "飞书 API 地址，通常无需修改"},
        ]

    def get_setup_guide(self) -> str:
        return (
            "### 飞书配置指南\n\n"
            "1. 登录 [飞书开放平台](https://open.feishu.cn/app)\n"
            "2. 创建「企业自建应用」，开通机器人能力\n"
            "3. 在「凭证与基础信息」中获取 **App ID** 和 **App Secret**\n"
            "4. 主模式推荐使用长连接模式，无需公网地址\n"
            "5. 如需公网回调，在「事件订阅」中配置请求地址，获取 **Verification Token** 和 **Encrypt Key**\n"
            "6. 订阅 `im.message.receive_v1`，并开通群聊 @ 机器人、消息资源下载、通讯录等权限\n"
        )

    def get_current_config(self) -> dict:
        def _mask(value: str) -> str:
            if not value:
                return ""
            if len(value) <= 4:
                return "****"
            return "****" + value[-4:]

        s = self._settings
        return {
            "app_id": s.app_id,
            "app_secret": _mask(s.app_secret),
            "verification_token": _mask(s.verification_token),
            "encrypt_key": _mask(s.encrypt_key),
            "api_base": s.api_base,
        }

    def apply_config(self, config: dict) -> None:
        for key in ("app_id", "app_secret", "verification_token", "encrypt_key", "api_base"):
            if key in config:
                setattr(self._settings, key, config[key])
        self._api = None

    async def test_connection(self) -> dict:
        if not self.is_configured():
            return {"ok": False, "message": "App ID 和 App Secret 未配置"}
        try:
            ok = await self.api.health_check()
            if ok:
                return {"ok": True, "message": "连接成功，已获取 tenant_access_token"}
            return {"ok": False, "message": "获取 tenant_access_token 失败"}
        except Exception as e:
            return {"ok": False, "message": f"连接失败: {e}"}

    def get_connection_info(self) -> dict:
        if self._ws_mode:
            return {"mode": "websocket"}
        return {"mode": "event_subscription" if self._running else "未启动"}

    def is_ws_configured(self) -> bool:
        return bool(self._settings.app_id and self._settings.app_secret)

    async def handle_event(self, body: dict) -> dict | None:
        """处理飞书事件订阅回调。"""
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge", "")}

        header = body.get("header", {})
        if header.get("event_type") != "im.message.receive_v1":
            return None

        event = body.get("event", {})
        msg = await self._build_message_from_event(event)
        if not msg:
            return None

        await self._dispatch_message(msg)
        return None

    async def start_ws(self) -> None:
        """通过官方 SDK 启动 WebSocket 长连接模式。"""
        if not self._handler and not self._stream_handler:
            log.error("未注册消息 handler，无法启动 WebSocket 模式")
            return
        if not self.is_ws_configured():
            log.error("飞书 WebSocket 未配置 (需要 app_id + app_secret)")
            return

        import lark_oapi as lark
        from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

        self._ws_mode = True
        self._running = True
        main_loop = asyncio.get_running_loop()

        def _on_message(data: P2ImMessageReceiveV1):
            # Must return within 3s per Lark docs; fire-and-forget to main loop.
            asyncio.run_coroutine_threadsafe(self._handle_ws_message(data), main_loop)

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(_on_message)
            .build()
        )

        def _run_ws():
            # Lark SDK captures event loop at module level; give the WS thread
            # its own loop so run_until_complete() doesn't clash with the main loop.
            import lark_oapi.ws.client as _ws_mod

            ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(ws_loop)
            _ws_mod.loop = ws_loop

            client = lark.ws.Client(
                self._settings.app_id,
                self._settings.app_secret,
                event_handler=event_handler,
                log_level=lark.LogLevel.DEBUG,
            )
            self._ws_client = client
            client.start()

        self._ws_task = asyncio.create_task(asyncio.to_thread(_run_ws))
        log.info("飞书 WebSocket 长连接已启动")

    async def _handle_ws_message(self, data: Any) -> None:
        from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

        try:
            if not isinstance(data, P2ImMessageReceiveV1):
                return
            event = data.event
            if not event or not event.message:
                return

            payload = {
                "sender": {
                    "sender_id": {
                        "open_id": getattr(getattr(event.sender, "sender_id", None), "open_id", ""),
                        "user_id": getattr(getattr(event.sender, "sender_id", None), "user_id", ""),
                        "union_id": getattr(getattr(event.sender, "sender_id", None), "union_id", ""),
                    },
                },
                "message": {
                    "message_id": event.message.message_id or "",
                    "message_type": event.message.message_type or "",
                    "chat_type": event.message.chat_type or "",
                    "chat_id": event.message.chat_id or "",
                    "content": event.message.content or "",
                    "mentions": [self._normalize_ws_mention(m) for m in (event.message.mentions or [])],
                },
            }

            log.info(
                "收到飞书 WS 事件: message_id=%s, type=%s, chat_type=%s",
                payload["message"]["message_id"],
                payload["message"]["message_type"],
                payload["message"]["chat_type"],
            )

            msg = await self._build_message_from_event(payload)
            if not msg:
                return

            log.info(f"飞书 WS 消息: {msg.sender_id} -> {msg.content[:80]}")
            await self._dispatch_message(msg)
        except Exception as e:
            log.error(f"飞书 WS 消息处理异常: {e}", exc_info=True)

    async def _dispatch_message(self, msg: Message) -> None:
        if self._stream_handler:
            await self._handle_stream_message(msg)
            return
        if self._handler:
            reply = await self._handler(msg)
            if reply:
                await self.send(msg.sender_id, Message(content=reply, channel="feishu", raw=msg.raw))

    async def _handle_stream_message(self, msg: Message) -> None:
        reply_to_message_id = msg.raw.get("reply_to_message_id", "") if isinstance(msg.raw, dict) else ""
        session = FeishuStreamingSession(
            self.api,
            receive_id=msg.sender_id,
            receive_id_type="open_id",
            reply_to_message_id=reply_to_message_id,
        )

        visible_text = ""
        final_text = ""
        started = False
        try:
            async for event in self._stream_handler(msg):
                event_type = event.get("type", "")
                if event_type == "thinking_delta":
                    if not started:
                        await session.start()
                        started = True
                    continue

                if event_type == "tool_use":
                    tool_name = event.get("name", "unknown")
                    visible_text = merge_streaming_text(visible_text, f"\n\n🔧 正在执行 {tool_name}...")
                elif event_type == "tool_result":
                    visible_text = merge_streaming_text(visible_text, " ✅")
                elif event_type == "text_delta":
                    visible_text += event.get("text", "")
                elif event_type == "text":
                    visible_text = event.get("text", "") or visible_text
                    final_text = visible_text
                else:
                    continue

                if visible_text and not started:
                    await session.start()
                    started = True
                if visible_text:
                    await session.update(visible_text)
        except Exception as e:
            log.error(f"飞书流式处理异常: {e}", exc_info=True)
            final_text = final_text or visible_text or f"抱歉，处理出现异常：{e}"
            if final_text and not started:
                await self.send(msg.sender_id, Message(content=final_text, channel="feishu", raw=msg.raw))
                return
        else:
            final_text = final_text or visible_text

        if started:
            await session.close(final_text)
        elif final_text:
            await self.send(msg.sender_id, Message(content=final_text, channel="feishu", raw=msg.raw))

    async def _build_message_from_event(self, event: dict) -> Message | None:
        message_data = event.get("message", {})
        msg_id = message_data.get("message_id", "")
        if not msg_id:
            log.debug("忽略飞书消息: 缺少 message_id")
            return None
        if self._inbox:
            if not await self._inbox.try_claim("feishu", msg_id):
                log.debug(f"飞书消息已被其他实例消费: {msg_id}")
                return None

        sender_id = self._extract_sender_id(event)
        if not sender_id:
            log.debug(f"忽略飞书消息 {msg_id}: 缺少 sender_id")
            return None

        msg_type = message_data.get("message_type", "")
        chat_type = message_data.get("chat_type", "")
        chat_id = message_data.get("chat_id", "")
        mentions = message_data.get("mentions", []) or []

        raw_content = message_data.get("content", "{}")
        content: str = ""
        images: list[dict] = []
        raw_extra: dict[str, Any] = {}

        try:
            content_json = json.loads(raw_content or "{}")
        except json.JSONDecodeError:
            content_json = {}

        if self._is_group_chat(chat_type) and not self._has_group_mention(msg_type, mentions, raw_content, content_json):
            log.info("忽略飞书群消息 %s: 未检测到 @ 机器人, type=%s", msg_id, msg_type)
            return None

        if msg_type == "text":
            content = content_json.get("text", "").strip()
        elif msg_type == "image":
            content = "[用户发送了一张图片]"
            file_key = content_json.get("image_key") or content_json.get("file_key")
            if file_key:
                image = await self._download_message_image(msg_id, file_key)
                if image:
                    images.append(image)
                raw_extra["image_key"] = file_key
        elif msg_type == "post":
            content, images = await self._parse_post_message(msg_id, content_json)
            if not content:
                content = "[用户发送了一条富文本消息]"
        elif msg_type == "file":
            content = "[用户发送了一个文件]"
            raw_extra["file_key"] = content_json.get("file_key", "")
            raw_extra["file_name"] = content_json.get("file_name", "")
        elif msg_type == "audio":
            file_key = content_json.get("file_key", "")
            raw_extra["file_key"] = file_key
            raw_extra["audio_format"] = "opus"
            raw_extra["voice_media_id"] = file_key
            content = "[用户发送了一段语音]"
            log.info("开始处理飞书语音消息: message_id=%s, file_key=%s", msg_id, file_key)
            if file_key:
                voice = await self._download_message_voice(msg_id, file_key)
                if voice:
                    transcript = await self._transcribe_voice([voice])
                    raw_extra["voice_data"] = voice
                    if transcript:
                        content = f"[语音消息]\n{transcript}"
                        log.info("飞书语音转写成功: message_id=%s, text=%s", msg_id, transcript[:120])
                    else:
                        log.info("飞书语音未识别出文本: message_id=%s", msg_id)
        else:
            log.info("忽略飞书消息 %s: 不支持的消息类型 %s", msg_id, msg_type)
            return None

        if not content and not images:
            log.debug(f"忽略飞书消息 {msg_id}: 文本和图片均为空")
            return None

        raw = {
            "message_id": msg_id,
            "message_type": msg_type,
            "chat_type": chat_type,
            "chat_id": chat_id,
            "content": raw_content,
            "mentions": mentions,
            **raw_extra,
        }
        if self._is_group_chat(chat_type):
            raw["reply_to_message_id"] = msg_id

        return Message(
            content=content,
            sender_id=sender_id,
            channel="feishu",
            msg_type=msg_type,
            images=images,
            voice_media_ids=[raw_extra["voice_media_id"]] if raw_extra.get("voice_media_id") else [],
            raw=raw,
        )

    async def _parse_post_message(self, message_id: str, content_json: dict) -> tuple[str, list[dict]]:
        text_parts: list[str] = []
        images: list[dict] = []
        for locale_payload in content_json.values():
            if not isinstance(locale_payload, dict):
                continue
            blocks = locale_payload.get("content", [])
            for row in blocks:
                if not isinstance(row, list):
                    continue
                for item in row:
                    if not isinstance(item, dict):
                        continue
                    tag = item.get("tag", "")
                    if tag == "text":
                        text = (item.get("text") or "").strip()
                        if text:
                            text_parts.append(text)
                    elif tag == "img":
                        file_key = item.get("image_key") or item.get("file_key")
                        if file_key:
                            image = await self._download_message_image(message_id, file_key)
                            if image:
                                images.append(image)
        return "\n".join(text_parts).strip(), images

    async def _download_message_image(self, message_id: str, file_key: str) -> dict | None:
        try:
            data = await self.api.download_message_resource(message_id, file_key, "image")
        except Exception as e:
            log.warning(f"下载飞书图片失败: message={message_id}, key={file_key}, err={e}")
            return None

        return {
            "file_key": file_key,
            "media_type": "image/png",
            "data": base64.b64encode(data).decode("ascii"),
        }

    async def _download_message_voice(self, message_id: str, file_key: str) -> dict | None:
        try:
            data = await self.api.download_message_resource(message_id, file_key, "file")
        except Exception as e:
            log.warning(f"下载飞书语音失败: message={message_id}, key={file_key}, err={e}")
            return None

        return {
            "file_key": file_key,
            "data": data,
            "format": "opus",
            "size": len(data),
        }

    async def _transcribe_voice(self, voice_data_list: list[dict]) -> str:
        if not self._asr_service or not voice_data_list:
            return ""
        texts: list[str] = []
        for voice in voice_data_list:
            data = voice.get("data", b"")
            fmt = voice.get("format", "opus")
            if not data:
                continue
            try:
                text = await self._asr_service.recognize(audio_data=data, format=fmt)
                if text and text.strip():
                    texts.append(text.strip())
            except Exception as e:
                log.error(f"飞书 ASR 转写异常: file_key={voice.get('file_key')}, error={e}")
        return "\n".join(texts)

    @staticmethod
    def _extract_sender_id(event: dict) -> str:
        sender_id = event.get("sender", {}).get("sender_id", {}) or {}
        for key in ("open_id", "user_id", "union_id"):
            value = (sender_id.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _is_group_chat(chat_type: str) -> bool:
        return chat_type in {"group", "topic_group"}

    @staticmethod
    def _has_group_mention(msg_type: str, mentions: list[dict], raw_content: str, content_json: dict) -> bool:
        # 飞书语音消息在群聊里通常无法携带 @ 信息；首版允许直接处理，
        # 否则群内语音输入会在进入 ASR 前被前置过滤掉。
        if msg_type == "audio":
            return True

        if mentions:
            return True

        if msg_type == "text":
            text = (content_json.get("text") or raw_content or "").strip()
            return "<at " in text or "@_user_" in text

        if msg_type == "post":
            payload = json.dumps(content_json, ensure_ascii=False)
            return bool(re.search(r'"tag"\s*:\s*"at"', payload)) or "<at " in payload or "@_user_" in payload

        return False

    @staticmethod
    def _normalize_ws_mention(mention: Any) -> dict:
        mention_id = getattr(mention, "id", None)
        return {
            "key": getattr(mention, "key", ""),
            "name": getattr(mention, "name", ""),
            "tenant_key": getattr(mention, "tenant_key", ""),
            "id": {
                "open_id": getattr(mention_id, "open_id", ""),
                "user_id": getattr(mention_id, "user_id", ""),
                "union_id": getattr(mention_id, "union_id", ""),
            },
        }
