"""
钉钉 Channel

实现 BaseChannel 接口，支持钉钉机器人消息收发。
支持两种模式：
- Webhook 回调（Stream 模式，推荐）
- HTTP 回调（需要公网地址）
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import base64
import json
import time

import httpx

from openvort.plugin.base import BaseChannel, Message, MessageHandler
from openvort.utils.logging import get_logger

log = get_logger("channels.dingtalk")


class DingTalkSettings:
    """钉钉配置"""

    def __init__(self):
        from openvort.config.settings import get_settings
        # 从环境变量加载（OPENVORT_DINGTALK_*）
        import os
        self.app_key: str = os.getenv("OPENVORT_DINGTALK_APP_KEY", "")
        self.app_secret: str = os.getenv("OPENVORT_DINGTALK_APP_SECRET", "")
        self.robot_code: str = os.getenv("OPENVORT_DINGTALK_ROBOT_CODE", "")
        self.api_base: str = os.getenv("OPENVORT_DINGTALK_API_BASE", "https://api.dingtalk.com")


class DingTalkChannel(BaseChannel):
    """钉钉通道"""

    name = "dingtalk"
    display_name = "钉钉"

    def __init__(self):
        self._settings = DingTalkSettings()
        self._handler: MessageHandler | None = None
        self._running = False
        self._poll_task: asyncio.Task | None = None
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
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
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
            {"key": "app_key", "label": "App Key", "type": "string", "required": True, "secret": False, "placeholder": "钉钉应用 AppKey"},
            {"key": "app_secret", "label": "App Secret", "type": "string", "required": True, "secret": True, "placeholder": ""},
            {"key": "robot_code", "label": "机器人编码", "type": "string", "required": True, "secret": False, "placeholder": "机器人 robotCode"},
            {"key": "api_base", "label": "API 地址", "type": "string", "required": False, "secret": False, "placeholder": "https://api.dingtalk.com"},
        ]

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
        return {"mode": "webhook" if self._running else "未启动"}

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
        self._token_expires = time.time() + expire_in - 300  # 提前 5 分钟刷新
        return self._access_token
