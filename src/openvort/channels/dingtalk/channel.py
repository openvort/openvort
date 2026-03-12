"""
钉钉 Channel

当前实现提供：
- Stream 长连接收消息
- 普通文本/Markdown 回复
- AI Card 流式回复（可选，需要配置 card template）
- 基础消息去重
- 群聊仅在显式 @ 机器人时处理

Webhook 回调处理接口仅保留为预留能力，本期不挂载到主 Web 应用。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx

from openvort.config.settings import DingTalkSettings
from openvort.plugin.base import BaseChannel, Message, MessageHandler
from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

log = get_logger("channels.dingtalk")

DT_GATEWAY_URL = "https://api.dingtalk.com/v1.0/gateway/connections/open"
DT_STREAM_CALLBACK_TOPIC = "/v1.0/im/bot/messages/get"
DT_CARD_CALLBACK_TOPIC = "/v1.0/card/instances/callback"
DT_API_BASE = "https://api.dingtalk.com"
DT_OAPI_BASE = "https://oapi.dingtalk.com"
DT_STREAM_UPDATE_THROTTLE = 0.35


def merge_streaming_text(previous_text: str | None, next_text: str | None) -> str:
    previous = previous_text or ""
    next_value = next_text or ""
    if not next_value:
        return previous
    if not previous or previous == next_value:
        return next_value
    if next_value.startswith(previous) or previous in next_value:
        return next_value
    if previous.startswith(next_value) or next_value in previous:
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


def stringify_card_values(values: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values.items():
        if isinstance(value, str):
            result[key] = value
        else:
            result[key] = json.dumps(value, ensure_ascii=False)
    return result


class DingTalkStreamingCardSession:
    """钉钉 AI Card 流式会话。"""

    def __init__(
        self,
        channel: "DingTalkChannel",
        *,
        conversation_id: str,
        is_group: bool,
    ):
        self._channel = channel
        self._conversation_id = conversation_id
        self._is_group = is_group
        self._card_instance_id = ""
        self._current_text = ""
        self._pending_text = ""
        self._last_update_at = 0.0
        self._closed = False

    async def start(self) -> bool:
        if self._closed or self._card_instance_id:
            return bool(self._card_instance_id)
        card_instance_id = await self._channel._create_ai_card(  # noqa: SLF001
            conversation_id=self._conversation_id,
            is_group=self._is_group,
        )
        if not card_instance_id:
            self._closed = True
            return False
        self._card_instance_id = card_instance_id
        log.info("钉钉 AI Card 会话已创建: card_instance_id=%s", self._card_instance_id)
        return True

    async def update(self, text: str) -> bool:
        if self._closed or not text:
            return False
        merged = merge_streaming_text(self._pending_text or self._current_text, text)
        if not merged or merged == self._current_text:
            return True

        self._pending_text = merged
        now = time.monotonic()
        if now - self._last_update_at < DT_STREAM_UPDATE_THROTTLE:
            return True
        return await self._flush_pending()

    async def close(self, final_text: str = "") -> bool:
        if self._closed:
            return bool(self._card_instance_id)
        self._closed = True
        if final_text:
            self._pending_text = merge_streaming_text(self._pending_text or self._current_text, final_text)
        return await self._flush_pending(finalize=True)

    async def fail(self, final_text: str = "") -> bool:
        if self._closed:
            return bool(self._card_instance_id)
        self._closed = True
        if final_text:
            self._pending_text = merge_streaming_text(self._pending_text or self._current_text, final_text)
        return await self._flush_pending(finalize=False, failed=True)

    async def _flush_pending(self, finalize: bool = False, failed: bool = False) -> bool:
        if not self._card_instance_id:
            return False

        target_text = self._pending_text or self._current_text
        if not target_text and not failed:
            return True

        self._pending_text = ""
        merged = merge_streaming_text(self._current_text, target_text)
        if merged != self._current_text:
            self._current_text = merged
        self._last_update_at = time.monotonic()

        ok = await self._channel._stream_ai_card(  # noqa: SLF001
            card_instance_id=self._card_instance_id,
            content=self._current_text,
            finalize=finalize,
            failed=failed,
        )
        if ok:
            log.info(
                "钉钉 AI Card 更新成功: card_instance_id=%s finalize=%s failed=%s text_len=%s",
                self._card_instance_id,
                finalize,
                failed,
                len(self._current_text),
            )
        if (finalize or failed) and not ok:
            self._closed = True
        return ok


class DingTalkChannel(BaseChannel):
    """钉钉通道。"""

    name = "dingtalk"
    display_name = "钉钉"
    description = "钉钉 IM 通道，支持 Stream 收消息与可选 AI Card 流式回复。"

    def __init__(self, settings: DingTalkSettings | None = None):
        self._settings = settings or DingTalkSettings()
        self._handler: MessageHandler | None = None
        self._stream_handler = None
        self._running = False
        self._stream_mode = False
        self._stream_task: asyncio.Task | None = None
        self._access_token = ""
        self._token_expires = 0.0
        self._http: httpx.AsyncClient | None = None
        self._sync_provider = None
        self._inbox = None  # InboxService, injected via set_inbox_service()

    def set_inbox_service(self, inbox) -> None:
        self._inbox = inbox

    async def start(self) -> None:
        if not self.is_configured():
            log.warning("钉钉 Channel 未配置，跳过启动")
            return
        self._running = True
        log.info("钉钉 Channel 已启动，当前推荐使用 Stream 模式")

    async def stop(self) -> None:
        self._running = False
        self._stream_mode = False
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stream_task
        self._stream_task = None
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        log.info("钉钉 Channel 已停止")

    async def send(self, target: str, message: Message) -> None:
        if not target:
            log.warning("钉钉发送失败：target 为空")
            return

        session_webhook = ""
        if isinstance(message.raw, dict):
            session_webhook = str(message.raw.get("sessionWebhook") or "").strip()

        try:
            if session_webhook:
                await self._send_via_session_webhook(session_webhook, message)
                return
            await self._send_proactive_message(target, message)
        except Exception as exc:
            log.error("钉钉发送异常: target=%s error=%s", target, exc, exc_info=True)
            raise

    def on_message(self, handler: MessageHandler) -> None:
        self._handler = handler

    def set_stream_handler(self, handler) -> None:
        self._stream_handler = handler

    def is_configured(self) -> bool:
        return bool(self._settings.app_key and self._settings.app_secret and self._settings.robot_code)

    def get_sync_provider(self):
        if not self.is_configured():
            return None
        if self._sync_provider is None:
            from openvort.channels.dingtalk.sync import DingTalkContactSyncProvider

            self._sync_provider = DingTalkContactSyncProvider(self)
        return self._sync_provider

    def get_channel_prompt(self) -> str:
        prompt_file = Path(__file__).parent / "prompts" / "channel_style.md"
        if prompt_file.exists():
            try:
                return prompt_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""

    def get_max_reply_length(self) -> int:
        return 6000

    def get_config_schema(self) -> list[dict]:
        return [
            {
                "key": "app_key",
                "label": "App Key",
                "type": "string",
                "required": True,
                "secret": False,
                "placeholder": "钉钉应用 AppKey",
                "description": "钉钉开放平台 -> 企业内部应用 -> 凭证与基础信息中的 AppKey",
            },
            {
                "key": "app_secret",
                "label": "App Secret",
                "type": "string",
                "required": True,
                "secret": True,
                "placeholder": "",
                "description": "与 AppKey 配套的 AppSecret",
            },
            {
                "key": "robot_code",
                "label": "机器人编码",
                "type": "string",
                "required": True,
                "secret": False,
                "placeholder": "机器人 robotCode",
                "description": "应用 -> 机器人与消息推送中的机器人编码 robotCode",
            },
            {
                "key": "message_type",
                "label": "回复模式",
                "type": "string",
                "required": False,
                "secret": False,
                "placeholder": "card 或 markdown",
                "description": "card 表示启用 AI Card 流式回复；markdown 表示普通文本/Markdown 回复",
            },
            {
                "key": "card_template_id",
                "label": "Card Template ID",
                "type": "string",
                "required": False,
                "secret": False,
                "placeholder": "钉钉卡片模板 ID",
                "description": "启用 AI Card 流式回复时必填，对应钉钉卡片模板 ID",
            },
            {
                "key": "card_template_key",
                "label": "Card Content Key",
                "type": "string",
                "required": False,
                "secret": False,
                "placeholder": "content",
                "description": "卡片模板中承载正文内容的变量名，通常可用 content",
            },
            {
                "key": "api_base",
                "label": "API 地址",
                "type": "string",
                "required": False,
                "secret": False,
                "placeholder": "https://api.dingtalk.com",
                "description": "钉钉 API 基础地址，通常无需修改",
            },
        ]

    def get_setup_guide(self) -> str:
        return (
            "### 钉钉配置指南\n\n"
            "1. 登录 [钉钉开放平台](https://open-dev.dingtalk.com/)\n"
            "2. 进入“应用开发” -> “企业内部应用”，创建或打开你的应用\n"
            "3. 在“凭证与基础信息”中获取 **AppKey** 和 **AppSecret**\n"
            "4. 在“机器人与消息推送”中开启机器人能力，并记录 **robotCode**\n"
            "5. 本期推荐使用 **Stream 模式**，无需配置公网回调地址\n"
            "6. 若要启用流式输出，请在钉钉后台先创建 **AI Card 模板**，并配置 `message_type=card`、`card_template_id` 与 `card_template_key`\n"
            "7. 群聊场景建议先通过 @ 机器人触发；若未显式 @，消息会被忽略\n\n"
            "> 说明：Webhook 回调接口目前仅保留为预留能力，不作为本期主流程。"
        )

    def get_current_config(self) -> dict:
        return {
            "app_key": self._settings.app_key,
            "app_secret": self._mask(self._settings.app_secret),
            "robot_code": self._settings.robot_code,
            "message_type": self._settings.message_type,
            "card_template_id": self._settings.card_template_id,
            "card_template_key": self._settings.card_template_key,
            "api_base": self._settings.api_base,
        }

    def apply_config(self, config: dict) -> None:
        for key in (
            "app_key",
            "app_secret",
            "robot_code",
            "message_type",
            "card_template_id",
            "card_template_key",
            "api_base",
        ):
            if key in config:
                setattr(self._settings, key, config[key])
        self._access_token = ""
        self._token_expires = 0.0

    async def test_connection(self) -> dict:
        if not self.is_configured():
            return {"ok": False, "message": "请先配置 App Key、App Secret 和机器人编码"}
        try:
            token = await self._get_access_token()
        except Exception as exc:
            return {"ok": False, "message": f"连接失败: {exc}"}
        if not token:
            return {"ok": False, "message": "未获取到 access_token"}

        if self._use_card_streaming() and not self._settings.card_template_id:
            return {
                "ok": True,
                "message": "基础连接成功；但未配置 card_template_id，当前会回退为非流式文本回复",
            }

        return {"ok": True, "message": "连接成功，已获取 access_token"}

    def get_connection_info(self) -> dict:
        if self._stream_mode:
            return {"mode": "stream"}
        return {"mode": "未启动"}

    def is_stream_configured(self) -> bool:
        return self.is_configured()

    async def handle_callback(self, body: dict, headers: dict | None = None) -> str | None:
        # DB-level dedup before building message
        msg_id = self._extract_message_id(body)
        if msg_id and self._inbox:
            if not await self._inbox.try_claim("dingtalk", msg_id):
                log.debug("钉钉消息已被其他实例消费: %s", msg_id)
                return None
        msg = self._build_message(body)
        if msg is None or self._handler is None:
            return None
        return await self._handler(msg)

    async def start_stream(self) -> None:
        if not self._handler and not self._stream_handler:
            log.error("钉钉 Stream 启动失败：未注册消息处理器")
            return
        if not self.is_stream_configured():
            log.error("钉钉 Stream 未配置，缺少 app_key/app_secret/robot_code")
            return

        self._stream_mode = True
        self._running = True
        self._stream_task = asyncio.create_task(self._stream_ws_loop())
        log.info("钉钉 Stream 模式已启动")

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=20)
        return self._http

    async def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        resp = await self._get_http().post(
            f"{self._settings.api_base}/v1.0/oauth2/accessToken",
            json={
                "appKey": self._settings.app_key,
                "appSecret": self._settings.app_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get("accessToken", "")
        if not access_token:
            raise RuntimeError(f"钉钉 access_token 获取失败: {data}")

        expire_in = int(data.get("expireIn", 7200) or 7200)
        self._access_token = access_token
        self._token_expires = time.time() + expire_in - 300
        return self._access_token

    async def _stream_register(self) -> tuple[str, str]:
        resp = await self._get_http().post(
            DT_GATEWAY_URL,
            json={
                "clientId": self._settings.app_key,
                "clientSecret": self._settings.app_secret,
                "subscriptions": [
                    {"type": "EVENT", "topic": "*"},
                    {"type": "CALLBACK", "topic": DT_STREAM_CALLBACK_TOPIC},
                    {"type": "CALLBACK", "topic": DT_CARD_CALLBACK_TOPIC},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        endpoint = data.get("endpoint", "")
        ticket = data.get("ticket", "")
        if not endpoint or not ticket:
            raise RuntimeError(f"钉钉 Stream 注册失败: {data}")
        return endpoint, ticket

    async def _stream_ws_loop(self) -> None:
        import websockets

        retry_delay = 1.0
        max_retry_delay = 60.0

        while self._running:
            try:
                endpoint, ticket = await self._stream_register()
                base_ws_url = endpoint.rstrip("/")
                if not base_ws_url.startswith(("wss://", "ws://")):
                    base_ws_url = f"wss://{base_ws_url}"
                separator = "&" if "?" in base_ws_url else "?"
                ws_url = f"{base_ws_url}{separator}ticket={ticket}"
                log.info("钉钉 Stream 连接中: %s", endpoint)

                async with websockets.connect(ws_url, ping_interval=None, ping_timeout=None) as ws:
                    log.info("钉钉 Stream 已连接")
                    retry_delay = 1.0

                    async for raw_msg in ws:
                        if not self._running:
                            break
                        await self._handle_stream_frame(ws, raw_msg)
            except asyncio.CancelledError:
                log.info("钉钉 Stream 已取消")
                break
            except Exception as exc:
                if self._running:
                    log.warning("钉钉 Stream 断开: %s，%ss 后重试", exc, int(retry_delay))
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_retry_delay)

        log.info("钉钉 Stream 循环已退出")

    async def _handle_stream_frame(self, ws: Any, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        data = json.loads(raw)
        frame_type = data.get("type", "")
        headers = data.get("headers", {}) or {}
        topic = headers.get("topic", "")

        if frame_type == "SYSTEM":
            if topic == "disconnect":
                raise ConnectionError("server disconnect")
            await ws.send(json.dumps(data, ensure_ascii=False))
            return

        if frame_type == "CALLBACK" and topic == DT_STREAM_CALLBACK_TOPIC:
            message_id = headers.get("messageId", "")
            await ws.send(self._build_stream_ack(message_id))
            msg_data = json.loads(data.get("data", "{}"))
            await self._handle_stream_bot_message(msg_data)
            return

        if frame_type == "CALLBACK" and topic == DT_CARD_CALLBACK_TOPIC:
            message_id = headers.get("messageId", "")
            await ws.send(self._build_stream_ack(message_id))
            callback_data = json.loads(data.get("data", "{}"))
            await self._handle_stream_card_callback(callback_data)
            return

        if frame_type == "EVENT":
            message_id = headers.get("messageId", "")
            await ws.send(self._build_stream_ack(message_id))

    async def _handle_stream_bot_message(self, data: dict) -> None:
        # DB-level dedup before building message
        msg_id = self._extract_message_id(data)
        if msg_id and self._inbox:
            if not await self._inbox.try_claim("dingtalk", msg_id):
                log.debug("钉钉消息已被其他实例消费: %s", msg_id)
                return
        msg = self._build_message(data)
        if msg is None:
            return

        log.info("钉钉 Stream 消息: %s -> %s", msg.sender_id, msg.content[:80])

        if self._stream_handler:
            await self._handle_stream_message(msg)
            return

        if self._handler is None:
            return

        reply = await self._handler(msg)
        if reply:
            log.info("钉钉回复: %s", reply[:80])
            await self.send(msg.sender_id, Message(content=reply, channel="dingtalk", raw=msg.raw))

    async def _handle_stream_message(self, msg: Message) -> None:
        use_card_streaming = self._use_card_streaming() and bool(self._settings.card_template_id)
        raw = msg.raw if isinstance(msg.raw, dict) else {}
        is_group = bool(raw.get("is_group"))
        card_target = str(raw.get("conversation_id") or "").strip() if is_group else str(msg.sender_id or "").strip()
        session = DingTalkStreamingCardSession(
            self,
            conversation_id=card_target,
            is_group=is_group,
        )

        visible_text = ""
        final_text = ""
        started = False
        card_started = False

        try:
            async for event in self._stream_handler(msg):
                event_type = event.get("type", "")
                if event_type == "thinking_delta":
                    continue

                if event_type == "tool_use":
                    tool_name = event.get("name", "unknown")
                    visible_text = merge_streaming_text(visible_text, f"\n\n[执行工具] {tool_name} ...")
                elif event_type == "tool_result":
                    visible_text = merge_streaming_text(visible_text, " [完成]")
                elif event_type == "text_delta":
                    visible_text += event.get("text", "")
                elif event_type == "text":
                    visible_text = event.get("text", "") or visible_text
                    final_text = visible_text
                else:
                    continue

                if visible_text and use_card_streaming and not started:
                    card_started = await session.start()
                    started = card_started
                    if not card_started:
                        log.warning("钉钉 AI Card 创建失败，回退为普通文本回复")

                if visible_text and started:
                    await session.update(visible_text)
        except Exception as exc:
            log.error("钉钉流式处理异常: %s", exc, exc_info=True)
            final_text = final_text or visible_text or f"抱歉，处理时出现异常：{exc}"
        else:
            final_text = final_text or visible_text

        if started and final_text and not final_text.strip():
            final_text = "抱歉，这次没有生成可展示的内容。"

        if started and "抱歉，处理时出现异常" in final_text:
            ok = await session.fail(final_text)
            if ok:
                log.info("钉钉流式回复已通过 AI Card 失败态完成投递")
                return

        if started:
            ok = await session.close(final_text)
            if ok:
                log.info("钉钉流式回复已通过 AI Card 完成投递")
                return

        if final_text:
            log.info("钉钉流式回复回退为普通文本发送: text_len=%s", len(final_text))
            fallback_msg_type = "markdown" if "\n" in final_text else "text"
            await self.send(
                msg.sender_id,
                Message(content=final_text, channel="dingtalk", msg_type=fallback_msg_type, raw=msg.raw),
            )

    async def _send_via_session_webhook(self, session_webhook: str, message: Message) -> None:
        token = await self._get_access_token()
        if message.msg_type == "markdown":
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": truncate_summary(message.content),
                    "text": message.content,
                },
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {"content": message.content},
            }

        resp = await self._get_http().post(
            session_webhook,
            headers={
                "x-acs-dingtalk-access-token": token,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"session webhook send failed: status={resp.status_code}, body={resp.text}")
        self._raise_for_business_error(resp, action="session webhook send")

    async def _send_proactive_message(self, target: str, message: Message) -> None:
        token = await self._get_access_token()
        is_group = target.startswith("cid")
        if is_group:
            url = f"{DT_API_BASE}/v1.0/robot/groupMessages/send"
            payload: dict[str, Any] = {
                "robotCode": self._settings.robot_code,
                "openConversationId": target,
            }
        else:
            url = f"{DT_API_BASE}/v1.0/robot/oToMessages/batchSend"
            payload = {
                "robotCode": self._settings.robot_code,
                "userIds": [target],
            }

        if message.msg_type == "voice":
            voice_data = message.raw.get("voice_data", {}) if isinstance(message.raw, dict) else {}
            media_id = str(voice_data.get("media_id") or "").strip()
            duration = int(voice_data.get("duration") or 0)
            if not media_id:
                raise ValueError("发送钉钉语音消息缺少 voice_data.media_id")
            payload.update(
                {
                    "msgKey": "sampleAudio",
                    "msgParam": json.dumps(
                        {
                            "mediaId": media_id,
                            "duration": str(max(duration, 1)),
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        elif message.msg_type == "markdown":
            payload.update(
                {
                    "msgKey": "sampleMarkdown",
                    "msgParam": json.dumps(
                        {"title": truncate_summary(message.content), "text": message.content},
                        ensure_ascii=False,
                    ),
                }
            )
        else:
            payload.update(
                {
                    "msgKey": "sampleText",
                    "msgParam": json.dumps({"content": message.content}, ensure_ascii=False),
                }
            )

        resp = await self._get_http().post(
            url,
            headers={
                "x-acs-dingtalk-access-token": token,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"proactive send failed: status={resp.status_code}, target={target}, body={resp.text}")
        self._raise_for_business_error(resp, action="proactive send")

    async def upload_media(self, media_type: str, file_content: bytes, file_name: str) -> dict:
        token = await self._get_access_token()
        files = {
            "media": (
                file_name,
                file_content,
                f"audio/{file_name.rsplit('.', 1)[-1].lower()}" if "." in file_name else "application/octet-stream",
            )
        }
        response = await self._get_http().post(
            f"{DT_OAPI_BASE}/media/upload",
            params={"access_token": token, "type": media_type},
            files=files,
        )
        response.raise_for_status()
        data = response.json()
        errcode = data.get("errcode", 0)
        if errcode not in (0, "0", None):
            errmsg = data.get("errmsg") or "unknown error"
            raise RuntimeError(f"upload media failed: errcode={errcode}, errmsg={errmsg}")
        return data

    async def _create_ai_card(self, conversation_id: str, is_group: bool) -> str:
        if not conversation_id or not self._settings.card_template_id:
            return ""

        token = await self._get_access_token()
        card_instance_id = f"card_{uuid4()}"
        card_template_key = (self._settings.card_template_key or "content").strip() or "content"
        card_param_map = stringify_card_values(
            {
                "config": {"autoLayout": True, "enableForward": True},
                card_template_key: "",
            }
        )
        body: dict[str, Any] = {
            "cardTemplateId": self._settings.card_template_id,
            "outTrackId": card_instance_id,
            "cardData": {"cardParamMap": card_param_map},
            "callbackType": "STREAM",
            "imGroupOpenSpaceModel": {"supportForward": True},
            "imRobotOpenSpaceModel": {"supportForward": True},
            "userIdType": 1,
            "openSpaceId": (
                f"dtv1.card//IM_GROUP.{conversation_id}"
                if is_group
                else f"dtv1.card//IM_ROBOT.{conversation_id}"
            ),
        }
        if is_group:
            body["imGroupOpenDeliverModel"] = {"robotCode": self._settings.robot_code}
        else:
            body["imRobotOpenDeliverModel"] = {
                "spaceType": "IM_ROBOT",
                "robotCode": self._settings.robot_code,
            }

        try:
            resp = await self._get_http().post(
                f"{DT_API_BASE}/v1.0/card/instances/createAndDeliver",
                headers={
                    "x-acs-dingtalk-access-token": token,
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if resp.status_code != 200:
                log.error(
                    "钉钉 AI Card 创建失败: status=%s body=%s payload=%s",
                    resp.status_code,
                    resp.text,
                    json.dumps(body, ensure_ascii=False),
                )
                return ""
            log.info("钉钉 AI Card 创建成功: card_instance_id=%s conversation_id=%s", card_instance_id, conversation_id)
            return card_instance_id
        except Exception as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                log.error(
                    "钉钉 AI Card 创建异常: status=%s body=%s payload=%s",
                    getattr(response, "status_code", "unknown"),
                    getattr(response, "text", ""),
                    json.dumps(body, ensure_ascii=False),
                )
            log.error("钉钉 AI Card 创建失败: %s", exc, exc_info=True)
            return ""

    async def _stream_ai_card(
        self,
        card_instance_id: str,
        content: str,
        finalize: bool = False,
        failed: bool = False,
    ) -> bool:
        token = await self._get_access_token()
        card_template_key = (self._settings.card_template_key or "content").strip() or "content"
        body = {
            "outTrackId": card_instance_id,
            "guid": str(uuid4()),
            "key": card_template_key,
            "content": content,
            "isFull": True,
            "isFinalize": finalize,
            "isError": failed,
        }
        try:
            resp = await self._get_http().put(
                f"{DT_API_BASE}/v1.0/card/streaming",
                headers={
                    "x-acs-dingtalk-access-token": token,
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if resp.status_code != 200:
                log.error(
                    "钉钉 AI Card 流式更新失败: status=%s body=%s card_instance_id=%s finalize=%s",
                    resp.status_code,
                    resp.text,
                    card_instance_id,
                    finalize,
                )
                return False
            log.debug(
                "钉钉 AI Card 流式更新响应: card_instance_id=%s finalize=%s body=%s",
                card_instance_id,
                finalize,
                resp.text,
            )
            return True
        except Exception as exc:
            log.error("钉钉 AI Card 流式更新失败: %s", exc, exc_info=True)
            return False

    def _build_message(self, data: dict) -> Message | None:
        message_id = self._extract_message_id(data)

        msg_type = (data.get("msgtype") or "").strip()
        sender_id = (data.get("senderStaffId") or data.get("senderId") or "").strip()
        if not sender_id:
            return None

        conversation_id = (
            data.get("conversationId")
            or data.get("openConversationId")
            or data.get("chatbotConversationId")
            or ""
        ).strip()
        conversation_type = str(data.get("conversationType", "") or "").strip()
        is_group = self._is_group_message(conversation_type, conversation_id)

        content = self._extract_text_content(data, msg_type)
        if not content:
            return None

        at_users = self._extract_at_users(data)
        if is_group and not self._is_explicit_mention(data, at_users):
            log.info("忽略钉钉群聊消息 %s：未检测到显式 @ 机器人", message_id or "<no-id>")
            return None

        raw = {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "conversation_type": conversation_type,
            "is_group": is_group,
            "at_users": at_users,
            "sender_staff_id": data.get("senderStaffId", ""),
            **data,
        }
        return Message(
            content=content,
            sender_id=sender_id,
            channel="dingtalk",
            msg_type=msg_type or "text",
            raw=raw,
        )

    @staticmethod
    def _extract_message_id(data: dict) -> str:
        return str(data.get("msgId") or data.get("messageId") or "").strip()

    @staticmethod
    def _extract_text_content(data: dict, msg_type: str) -> str:
        if msg_type == "text":
            return (data.get("text", {}) or {}).get("content", "").strip()

        if msg_type == "richText":
            rich_items = ((data.get("content", {}) or {}).get("richText", [])) or []
            parts: list[str] = []
            for item in rich_items:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if text:
                    parts.append(str(text))
            return "".join(parts).strip()

        if msg_type in {"audio", "voice"}:
            content = data.get("content", {}) or {}
            transcript = (
                content.get("recognition")
                or data.get("recognition")
                or (data.get("voice", {}) or {}).get("recognition")
                or ""
            )
            transcript = str(transcript).strip()
            if transcript:
                return f"[语音消息]\n{transcript}"
            return "[语音消息]"

        return ""

    @staticmethod
    def _extract_at_users(data: dict) -> list[str]:
        values = data.get("atUsers") or data.get("atUserIds") or []
        result: list[str] = []
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict):
                    user_id = item.get("staffId") or item.get("dingtalkId") or item.get("userId") or ""
                    if user_id:
                        result.append(str(user_id))
                elif item:
                    result.append(str(item))
        return result

    @staticmethod
    def _is_group_message(conversation_type: str, conversation_id: str) -> bool:
        del conversation_id
        return conversation_type in {"2", "group"}

    def _is_explicit_mention(self, data: dict, at_users: list[str]) -> bool:
        robot_code = self._settings.robot_code.strip()
        bot_user_id = str(
            data.get("chatbotUserId") or data.get("robotCode") or data.get("chatbotCorpId") or ""
        ).strip()

        if at_users:
            if robot_code and robot_code in at_users:
                return True
            if bot_user_id and bot_user_id in at_users:
                return True
            return False

        at_me = data.get("isInAtList")
        if isinstance(at_me, bool):
            return at_me
        if isinstance(at_me, str):
            return at_me.lower() == "true"
        return False

    def _use_card_streaming(self) -> bool:
        return (self._settings.message_type or "markdown").strip().lower() == "card"

    @staticmethod
    def _raise_for_business_error(resp: httpx.Response, action: str) -> None:
        try:
            data = resp.json()
        except ValueError:
            return

        if not isinstance(data, dict):
            return

        errcode = data.get("errcode")
        if errcode not in (None, 0, "0"):
            errmsg = data.get("errmsg") or data.get("message") or "unknown error"
            raise RuntimeError(f"{action} failed: errcode={errcode}, errmsg={errmsg}")

        code = data.get("code")
        if code in (None, 0, "0", 200, "200", "OK", "ok", "success", "SUCCESS"):
            return

        if isinstance(code, str) and code.startswith("Forbidden."):
            message = data.get("message") or "unknown error"
            raise RuntimeError(f"{action} failed: code={code}, message={message}")

    @staticmethod
    def _build_stream_ack(message_id: str) -> str:
        return json.dumps(
            {
                "code": 200,
                "headers": {"contentType": "application/json", "messageId": message_id},
                "message": "OK",
                "data": "",
            },
            ensure_ascii=False,
        )

    async def _handle_stream_card_callback(self, data: dict) -> None:
        card_instance_id = str(
            data.get("cardInstanceId") or data.get("outTrackId") or data.get("cardBizId") or ""
        ).strip()
        action_ids = data.get("actionIds") or data.get("actionId") or []
        log.debug(
            "收到钉钉 AI Card 回调: card_instance_id=%s action_ids=%s",
            card_instance_id or "<unknown>",
            action_ids,
        )

    @staticmethod
    def _mask(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "****"
        return "****" + value[-4:]
