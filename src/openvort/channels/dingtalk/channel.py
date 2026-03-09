"""
钉钉 Channel

实现 BaseChannel 接口，支持钉钉机器人消息收发。
支持两种模式：
- Stream 长连接（推荐，无需公网地址）
- Webhook 回调（需要公网地址）
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx

from openvort.plugin.base import BaseChannel, Message, MessageHandler
from openvort.utils.logging import get_logger

log = get_logger("channels.dingtalk")

DT_GATEWAY_URL = "https://api.dingtalk.com/v1.0/gateway/connections/open"
DT_STREAM_CALLBACK_TOPIC = "/v1.0/im/bot/messages/get"


class DingTalkSettings:
    """钉钉配置"""

    def __init__(self):
        import os
        self.app_key: str = os.getenv("OPENVORT_DINGTALK_APP_KEY", "")
        self.app_secret: str = os.getenv("OPENVORT_DINGTALK_APP_SECRET", "")
        self.robot_code: str = os.getenv("OPENVORT_DINGTALK_ROBOT_CODE", "")
        self.api_base: str = os.getenv("OPENVORT_DINGTALK_API_BASE", "https://api.dingtalk.com")


class DingTalkChannel(BaseChannel):
    """钉钉通道"""

    name = "dingtalk"
    display_name = "钉钉"
    description = "钉钉 IM 通道，支持 Stream 长连接/Webhook 回调，OpenAPI 发送消息"

    def __init__(self):
        self._settings = DingTalkSettings()
        self._handler: MessageHandler | None = None
        self._running = False
        self._stream_task: asyncio.Task | None = None
        self._stream_mode = False
        self._access_token: str = ""
        self._token_expires: float = 0
        self._http: httpx.AsyncClient | None = None

    # ---- BaseChannel 接口 ----

    async def start(self) -> None:
        if not self.is_configured():
            log.warning("钉钉 Channel 未配置，跳过启动")
            return
        self._running = True
        log.info("钉钉 Channel 已启动（等待 Webhook 回调）")

    async def stop(self) -> None:
        self._running = False
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
        if self._http:
            await self._http.aclose()
        log.info("钉钉 Channel 已停止")

    async def send(self, target: str, message: Message) -> None:
        """发送消息到指定用户（通过 OpenAPI）"""
        try:
            token = await self._get_access_token()
            http = self._get_http()
            resp = await http.post(
                f"{self._settings.api_base}/v1.0/robot/oToMessages/batchSend",
                headers={"x-acs-dingtalk-access-token": token},
                json={
                    "robotCode": self._settings.robot_code,
                    "userIds": [target],
                    "msgKey": "sampleText",
                    "msgParam": json.dumps({"content": message.content}),
                },
            )
            if resp.status_code != 200:
                log.error(f"钉钉发送失败: {resp.status_code} {resp.text}")
        except Exception as e:
            log.error(f"钉钉发送异常: {e}")

    def on_message(self, handler: MessageHandler) -> None:
        self._handler = handler

    def is_configured(self) -> bool:
        return bool(self._settings.app_key and self._settings.app_secret)

    def get_channel_prompt(self) -> str:
        prompt_file = __import__("pathlib").Path(__file__).parent / "prompts" / "channel_style.md"
        if prompt_file.exists():
            try:
                return prompt_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""

    def get_max_reply_length(self) -> int:
        return 6000  # 钉钉单条消息限制

    # ---- 配置管理 ----

    def get_config_schema(self) -> list[dict]:
        return [
            {"key": "app_key", "label": "App Key", "type": "string", "required": True, "secret": False, "placeholder": "钉钉应用 AppKey",
             "description": "钉钉开放平台 → 应用开发 → 企业内部应用 → 凭证与基础信息 → AppKey"},
            {"key": "app_secret", "label": "App Secret", "type": "string", "required": True, "secret": True, "placeholder": "",
             "description": "与 AppKey 一同获取的 AppSecret"},
            {"key": "robot_code", "label": "机器人编码", "type": "string", "required": True, "secret": False, "placeholder": "机器人 robotCode",
             "description": "应用 → 机器人与消息推送 → 机器人编码（robotCode）"},
            {"key": "api_base", "label": "API 地址", "type": "string", "required": False, "secret": False, "placeholder": "https://api.dingtalk.com",
             "description": "钉钉 API 地址，通常无需修改"},
        ]

    def get_setup_guide(self) -> str:
        return (
            "### 钉钉配置指南\n\n"
            "1. 登录 [钉钉开放平台](https://open-dev.dingtalk.com/)\n"
            "2. 进入「应用开发」→「企业内部开发」→ 创建应用\n"
            "3. 在「凭证与基础信息」中获取 **AppKey** 和 **AppSecret**\n"
            "4. 在「机器人与消息推送」中开启机器人能力，获取 **robotCode**\n"
            "5. 配置消息接收地址为 OpenVort 的回调 URL\n"
            "6. 在「权限管理」中添加所需权限（消息收发相关）\n"
        )

    def get_current_config(self) -> dict:
        s = self._settings
        return {
            "app_key": s.app_key,
            "app_secret": ("****" + s.app_secret[-4:]) if len(s.app_secret) > 4 else "****",
            "robot_code": s.robot_code,
            "api_base": s.api_base,
        }

    def apply_config(self, config: dict) -> None:
        s = self._settings
        for key in ("app_key", "app_secret", "robot_code", "api_base"):
            if key in config:
                setattr(s, key, config[key])
        self._access_token = ""
        self._token_expires = 0

    async def test_connection(self) -> dict:
        if not self.is_configured():
            return {"ok": False, "message": "App Key 和 App Secret 未配置"}
        try:
            token = await self._get_access_token()
            if token:
                return {"ok": True, "message": "连接成功，已获取 access_token"}
            return {"ok": False, "message": "获取 access_token 失败"}
        except Exception as e:
            return {"ok": False, "message": f"连接失败: {e}"}

    def get_connection_info(self) -> dict:
        if self._stream_mode:
            return {"mode": "stream"}
        return {"mode": "webhook" if self._running else "未启动"}

    def is_stream_configured(self) -> bool:
        return bool(self._settings.app_key and self._settings.app_secret)

    # ---- Webhook 回调处理 ----

    async def handle_callback(self, body: dict, headers: dict | None = None) -> str | None:
        """处理钉钉 Webhook 回调

        Args:
            body: 回调请求体
            headers: 请求头（用于签名验证）

        Returns:
            回复文本或 None
        """
        msg_type = body.get("msgtype", "")
        sender_id = body.get("senderStaffId", "") or body.get("senderId", "")
        conversation_type = body.get("conversationType", "1")  # 1=单聊 2=群聊

        # 提取文本内容
        content = ""
        if msg_type == "text":
            content = body.get("text", {}).get("content", "").strip()
        elif msg_type == "richText":
            # 富文本提取纯文本
            for item in body.get("content", {}).get("richText", []):
                if item.get("text"):
                    content += item["text"]

        if not content or not sender_id:
            return None

        msg = Message(
            content=content,
            sender_id=sender_id,
            channel="dingtalk",
            msg_type=msg_type,
            raw=body,
        )

        if self._handler:
            return await self._handler(msg)
        return None

    # ---- 内部方法 ----

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=15)
        return self._http

    async def _get_access_token(self) -> str:
        """获取钉钉 access_token（自动缓存）"""
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        http = self._get_http()
        resp = await http.post(
            f"{self._settings.api_base}/v1.0/oauth2/accessToken",
            json={
                "appKey": self._settings.app_key,
                "appSecret": self._settings.app_secret,
            },
        )
        data = resp.json()
        self._access_token = data.get("accessToken", "")
        expire_in = data.get("expireIn", 7200)
        self._token_expires = time.time() + expire_in - 300
        return self._access_token

    # ---- Stream 长连接模式 ----

    async def start_stream(self) -> None:
        """启动 Stream 长连接模式（无需公网 IP）"""
        if not self._handler:
            log.error("未注册消息 handler，无法启动 Stream 模式")
            return
        if not self.is_stream_configured():
            log.error("钉钉 Stream 未配置 (需要 app_key + app_secret)")
            return

        self._stream_mode = True
        self._running = True
        self._stream_task = asyncio.create_task(self._stream_ws_loop())
        log.info("钉钉 Stream 模式已启动")

    async def _stream_register(self) -> tuple[str, str]:
        """Register with DingTalk gateway to get WebSocket endpoint + ticket."""
        http = self._get_http()
        resp = await http.post(
            DT_GATEWAY_URL,
            json={
                "clientId": self._settings.app_key,
                "clientSecret": self._settings.app_secret,
                "subscriptions": [
                    {"type": "EVENT", "topic": "*"},
                    {"type": "CALLBACK", "topic": DT_STREAM_CALLBACK_TOPIC},
                ],
            },
        )
        data = resp.json()
        endpoint = data.get("endpoint", "")
        ticket = data.get("ticket", "")
        if not endpoint or not ticket:
            raise RuntimeError(f"注册 Stream 端点失败: {data}")
        return endpoint, ticket

    async def _stream_ws_loop(self) -> None:
        """Stream WebSocket long-connection loop with auto-reconnect."""
        import websockets

        retry_delay = 1.0
        max_retry_delay = 60.0

        while self._running:
            try:
                endpoint, ticket = await self._stream_register()
                ws_url = f"wss://{endpoint}/connect?ticket={ticket}"
                log.info(f"钉钉 Stream 连接中: {endpoint}")

                async with websockets.connect(ws_url, ping_interval=None, ping_timeout=None) as ws:
                    log.info("钉钉 Stream 已连接")
                    retry_delay = 1.0

                    async for raw_msg in ws:
                        if not self._running:
                            break
                        try:
                            await self._handle_stream_frame(ws, raw_msg)
                        except Exception as e:
                            log.error(f"钉钉 Stream 消息处理异常: {e}", exc_info=True)

            except asyncio.CancelledError:
                log.info("钉钉 Stream 循环已取消")
                break
            except Exception as e:
                if self._running:
                    log.warning(f"钉钉 Stream 断开 ({e})，{retry_delay:.0f}s 后重连...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_retry_delay)

        log.info("钉钉 Stream 循环已退出")

    async def _handle_stream_frame(self, ws, raw: str | bytes) -> None:
        """Handle a single frame from DingTalk Stream WebSocket."""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        data = json.loads(raw)
        frame_type = data.get("type", "")
        headers = data.get("headers", {})
        topic = headers.get("topic", "")

        if frame_type == "SYSTEM":
            if topic == "disconnect":
                log.info("钉钉 Stream 收到 disconnect，准备重连")
                raise ConnectionError("server disconnect")
            # ping -> pong
            await ws.send(json.dumps(data))
            return

        if frame_type == "CALLBACK" and topic == DT_STREAM_CALLBACK_TOPIC:
            message_id = headers.get("messageId", "")
            # ACK immediately
            ack = {
                "code": 200,
                "headers": {"contentType": "application/json", "messageId": message_id},
                "message": "OK",
                "data": "",
            }
            await ws.send(json.dumps(ack))

            msg_data = json.loads(data.get("data", "{}"))
            await self._handle_stream_bot_message(msg_data)
            return

        if frame_type == "EVENT":
            message_id = headers.get("messageId", "")
            ack = {
                "code": 200,
                "headers": {"contentType": "application/json", "messageId": message_id},
                "message": "OK",
                "data": "",
            }
            await ws.send(json.dumps(ack))

    async def _handle_stream_bot_message(self, data: dict) -> None:
        """Process a bot message received via Stream mode."""
        msg_type = data.get("msgtype", "")
        sender_id = data.get("senderStaffId", "") or data.get("senderId", "")
        conversation_type = data.get("conversationType", "1")

        content = ""
        if msg_type == "text":
            content = data.get("text", {}).get("content", "").strip()
        elif msg_type == "richText":
            for item in data.get("content", {}).get("richText", []):
                if item.get("text"):
                    content += item["text"]

        if not content or not sender_id:
            return

        msg = Message(
            content=content,
            sender_id=sender_id,
            channel="dingtalk",
            msg_type=msg_type,
            raw=data,
        )

        log.info(f"钉钉 Stream 消息: {sender_id} -> {content[:80]}")

        if self._handler:
            reply = await self._handler(msg)
            if reply:
                log.info(f"钉钉回复: {reply[:80]}")
                await self.send(sender_id, Message(content=reply, channel="dingtalk"))
