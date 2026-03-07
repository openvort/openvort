"""
OpenClaw Channel

Integrate with the OpenClaw personal AI assistant platform.
https://github.com/openclaw/openclaw

Bidirectional communication:
- Inbound:  OpenClaw → OpenVort via webhook callback (POST /api/webhooks/openclaw)
- Outbound: OpenVort → OpenClaw via POST /hooks/agent on the OpenClaw Gateway
"""

from __future__ import annotations

import httpx

from openvort.plugin.base import BaseChannel, Message, MessageHandler
from openvort.utils.logging import get_logger

log = get_logger("channels.openclaw")


class OpenClawChannel(BaseChannel):
    """OpenClaw 通道 — 通过 OpenClaw Gateway Webhook API 双向通信"""

    name = "openclaw"
    display_name = "OpenClaw"
    description = "OpenClaw 多平台网关，桥接 WhatsApp/Telegram/Slack/Discord 等即时通讯平台"

    def __init__(self):
        self._handler: MessageHandler | None = None
        self._running = False
        self._http: httpx.AsyncClient | None = None
        self._gateway_url = ""
        self._hook_token = ""
        self._deliver_channel = "last"
        self._deliver_to = ""
        self._load_settings()

    def _load_settings(self) -> None:
        try:
            from openvort.config.settings import get_settings
            s = get_settings().openclaw
            self._gateway_url = s.gateway_url.rstrip("/") if s.gateway_url else ""
            self._hook_token = s.hook_token
            self._deliver_channel = s.deliver_channel or "last"
            self._deliver_to = s.deliver_to
        except Exception:
            pass

    # ---- BaseChannel interface ----

    async def start(self) -> None:
        if not self.is_configured():
            log.warning("OpenClaw Channel 未配置，跳过启动")
            return
        self._running = True
        log.info(f"OpenClaw Channel 已启动 (Gateway: {self._gateway_url})")

    async def stop(self) -> None:
        self._running = False
        if self._http:
            await self._http.aclose()
            self._http = None
        log.info("OpenClaw Channel 已停止")

    async def send(self, target: str, message: Message) -> None:
        """Push a message to OpenClaw Gateway via /hooks/agent.

        The Gateway then delivers it to the user's configured channels
        (WhatsApp, Telegram, Slack, Discord, etc.).
        """
        if not self._gateway_url or not self._hook_token:
            log.warning("OpenClaw 未配置 gateway_url 或 hook_token，无法发送")
            return

        http = self._get_http()
        payload: dict = {
            "message": message.content,
            "name": "OpenVort",
            "deliver": True,
            "channel": self._deliver_channel,
        }
        if self._deliver_to:
            payload["to"] = self._deliver_to
        if target and target != "openclaw":
            payload["to"] = target

        try:
            resp = await http.post(
                f"{self._gateway_url}/hooks/agent",
                headers={
                    "Authorization": f"Bearer {self._hook_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code in (200, 202):
                log.debug(f"OpenClaw 推送成功: {message.content[:60]}")
            else:
                log.warning(f"OpenClaw 推送失败: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            log.error(f"OpenClaw 推送异常: {e}")

    def on_message(self, handler: MessageHandler) -> None:
        self._handler = handler

    def is_configured(self) -> bool:
        return bool(self._gateway_url and self._hook_token)

    def get_channel_prompt(self) -> str:
        return (
            "The user is interacting through OpenClaw, a multi-channel AI assistant platform. "
            "Messages may come from WhatsApp, Telegram, Slack, Discord, or other channels. "
            "Keep replies concise and well-formatted in plain text or markdown."
        )

    def get_max_reply_length(self) -> int:
        return 4000

    # ---- Webhook callback handler (inbound) ----

    async def handle_callback(
        self, body: dict, headers: dict | None = None, *, member_id: str = "",
    ) -> str | None:
        """Handle inbound webhook from OpenClaw.

        OpenClaw can forward messages to OpenVort by calling:
          POST /api/webhooks/openclaw

        Args:
            body: parsed JSON payload
            headers: HTTP headers (optional)
            member_id: bound AI virtual member ID for persona injection
        """
        msg_text = body.get("message", "") or body.get("text", "")
        sender = body.get("from", "") or body.get("sender", "") or "openclaw-user"
        source_channel = body.get("channel", "openclaw")

        if not msg_text:
            return None

        raw = dict(body)
        if member_id:
            raw["_bound_member_id"] = member_id

        msg = Message(
            content=msg_text,
            sender_id=sender,
            channel="openclaw",
            msg_type="text",
            raw=raw,
        )

        if self._handler:
            return await self._handler(msg)
        return None

    # ---- Config management ----

    def get_setup_guide(self) -> str:
        return (
            "### OpenClaw 配置指南\n\n"
            "1. 安装并启动 [OpenClaw](https://github.com/nicekate/openclaw) Gateway\n"
            "2. 查看 `~/.openclaw/openclaw.json`，获取 **hooks.token**\n"
            "3. 填写 Gateway 地址（默认 `http://127.0.0.1:18789`）和 Hook Token\n"
            "4. 在 OpenVort Webhook 管理中创建名为 `openclaw` 的 Webhook 接收 OpenClaw 回调\n"
            "5. 可选配置投递通道（last/whatsapp/telegram 等）和投递目标\n"
        )

    def get_config_schema(self) -> list[dict]:
        return [
            {
                "key": "gateway_url", "label": "Gateway 地址", "type": "string",
                "required": True, "secret": False,
                "placeholder": "http://127.0.0.1:18789",
                "description": "OpenClaw Gateway 的访问地址",
            },
            {
                "key": "hook_token", "label": "Hook Token", "type": "string",
                "required": True, "secret": True,
                "placeholder": "OpenClaw hooks.token",
                "description": "与 OpenClaw ~/.openclaw/openclaw.json 中 hooks.token 一致",
            },
            {
                "key": "deliver_channel", "label": "投递通道", "type": "string",
                "required": False, "secret": False,
                "placeholder": "last",
                "description": "推送消息到 OpenClaw 的哪个通道 (last/whatsapp/telegram/slack/discord)",
            },
            {
                "key": "deliver_to", "label": "投递目标", "type": "string",
                "required": False, "secret": False,
                "placeholder": "",
                "description": "目标用户标识 (手机号/chat ID 等)，留空使用 OpenClaw 默认",
            },
        ]

    def get_current_config(self) -> dict:
        return {
            "gateway_url": self._gateway_url,
            "hook_token": ("****" + self._hook_token[-4:]) if len(self._hook_token) > 4 else ("****" if self._hook_token else ""),
            "deliver_channel": self._deliver_channel,
            "deliver_to": self._deliver_to,
        }

    def apply_config(self, config: dict) -> None:
        if "gateway_url" in config:
            self._gateway_url = config["gateway_url"].rstrip("/")
        if "hook_token" in config:
            self._hook_token = config["hook_token"]
        if "deliver_channel" in config:
            self._deliver_channel = config["deliver_channel"] or "last"
        if "deliver_to" in config:
            self._deliver_to = config["deliver_to"]

    async def test_connection(self) -> dict:
        if not self.is_configured():
            return {"ok": False, "message": "请先配置 Gateway 地址和 Hook Token"}
        try:
            http = self._get_http()
            resp = await http.post(
                f"{self._gateway_url}/hooks/wake",
                headers={
                    "Authorization": f"Bearer {self._hook_token}",
                    "Content-Type": "application/json",
                },
                json={"text": "OpenVort connection test", "mode": "now"},
            )
            if resp.status_code == 200:
                return {"ok": True, "message": f"连接成功 (Gateway: {self._gateway_url})"}
            elif resp.status_code == 401:
                return {"ok": False, "message": "认证失败，请检查 Hook Token"}
            else:
                return {"ok": False, "message": f"Gateway 响应异常: {resp.status_code}"}
        except httpx.ConnectError:
            return {"ok": False, "message": f"无法连接到 {self._gateway_url}，请确认 OpenClaw Gateway 已启动"}
        except Exception as e:
            return {"ok": False, "message": f"连接失败: {e}"}

    def get_connection_info(self) -> dict:
        return {
            "mode": "webhook",
            "gateway_url": self._gateway_url,
            "deliver_channel": self._deliver_channel,
        }

    # ---- Internal ----

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30)
        return self._http
