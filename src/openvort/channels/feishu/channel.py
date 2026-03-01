"""
飞书 Channel

实现 BaseChannel 接口，支持飞书机器人消息收发。
使用飞书 Event Subscription 接收消息，OpenAPI 发送消息。
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx

from openvort.plugin.base import BaseChannel, Message, MessageHandler
from openvort.utils.logging import get_logger

log = get_logger("channels.feishu")


class FeishuSettings:
    """飞书配置"""

    def __init__(self):
        import os
        self.app_id: str = os.getenv("OPENVORT_FEISHU_APP_ID", "")
        self.app_secret: str = os.getenv("OPENVORT_FEISHU_APP_SECRET", "")
        self.verification_token: str = os.getenv("OPENVORT_FEISHU_VERIFICATION_TOKEN", "")
        self.encrypt_key: str = os.getenv("OPENVORT_FEISHU_ENCRYPT_KEY", "")
        self.api_base: str = os.getenv("OPENVORT_FEISHU_API_BASE", "https://open.feishu.cn/open-apis")


class FeishuChannel(BaseChannel):
    """飞书通道"""

    name = "feishu"
    display_name = "飞书"
    description = "飞书 IM 通道，通过事件订阅接收消息，OpenAPI 发送消息"

    def __init__(self):
        self._settings = FeishuSettings()
        self._handler: MessageHandler | None = None
        self._running = False
        self._access_token: str = ""
        self._token_expires: float = 0
        self._http: httpx.AsyncClient | None = None
        self._processed_msg_ids: set[str] = set()  # 去重

    # ---- BaseChannel 接口 ----

    async def start(self) -> None:
        if not self.is_configured():
            log.warning("飞书 Channel 未配置，跳过启动")
            return
        self._running = True
        log.info("飞书 Channel 已启动（等待 Event Subscription 回调）")

    async def stop(self) -> None:
        self._running = False
        if self._http:
            await self._http.aclose()
        log.info("飞书 Channel 已停止")

    async def send(self, target: str, message: Message) -> None:
        """发送消息到指定用户"""
        try:
            token = await self._get_access_token()
            http = self._get_http()
            content = json.dumps({"text": message.content})
            resp = await http.post(
                f"{self._settings.api_base}/im/v1/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={"receive_id_type": "open_id"},
                json={
                    "receive_id": target,
                    "msg_type": "text",
                    "content": content,
                },
            )
            data = resp.json()
            if data.get("code", -1) != 0:
                log.error(f"飞书发送失败: {data.get('msg', '')}")
        except Exception as e:
            log.error(f"飞书发送异常: {e}")

    def on_message(self, handler: MessageHandler) -> None:
        self._handler = handler

    def is_configured(self) -> bool:
        return bool(self._settings.app_id and self._settings.app_secret)

    def get_channel_prompt(self) -> str:
        prompt_file = __import__("pathlib").Path(__file__).parent / "prompts" / "channel_style.md"
        if prompt_file.exists():
            try:
                return prompt_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""

    def get_max_reply_length(self) -> int:
        return 4000

    # ---- 配置管理 ----

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
            "2. 创建「企业自建应用」\n"
            "3. 在「凭证与基础信息」中获取 **App ID** 和 **App Secret**\n"
            "4. 在「事件订阅」中配置请求地址，获取 **Verification Token** 和 **Encrypt Key**\n"
            "5. 订阅「接收消息」事件（im.message.receive_v1）\n"
            "6. 在「权限管理」中开通消息相关权限并发布应用版本\n"
        )

    def get_current_config(self) -> dict:
        s = self._settings
        mask = lambda v: ("****" + v[-4:]) if len(v) > 4 else "****" if v else ""
        return {
            "app_id": s.app_id,
            "app_secret": mask(s.app_secret),
            "verification_token": mask(s.verification_token),
            "encrypt_key": mask(s.encrypt_key),
            "api_base": s.api_base,
        }

    def apply_config(self, config: dict) -> None:
        s = self._settings
        for key in ("app_id", "app_secret", "verification_token", "encrypt_key", "api_base"):
            if key in config:
                setattr(s, key, config[key])
        self._access_token = ""
        self._token_expires = 0

    async def test_connection(self) -> dict:
        if not self.is_configured():
            return {"ok": False, "message": "App ID 和 App Secret 未配置"}
        try:
            token = await self._get_access_token()
            if token:
                return {"ok": True, "message": "连接成功，已获取 tenant_access_token"}
            return {"ok": False, "message": "获取 token 失败"}
        except Exception as e:
            return {"ok": False, "message": f"连接失败: {e}"}

    def get_connection_info(self) -> dict:
        return {"mode": "event_subscription" if self._running else "未启动"}

    # ---- Event Subscription 回调处理 ----

    async def handle_event(self, body: dict) -> dict | None:
        """处理飞书事件订阅回调

        Args:
            body: 回调请求体（已解密）

        Returns:
            响应 dict 或 None
        """
        # URL 验证请求
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge", "")}

        # 事件回调
        header = body.get("header", {})
        event = body.get("event", {})
        event_type = header.get("event_type", "")

        if event_type != "im.message.receive_v1":
            return None

        message_data = event.get("message", {})
        msg_id = message_data.get("message_id", "")

        # 去重
        if msg_id in self._processed_msg_ids:
            return None
        self._processed_msg_ids.add(msg_id)
        if len(self._processed_msg_ids) > 500:
            self._processed_msg_ids = set(list(self._processed_msg_ids)[-250:])

        # 提取消息内容
        msg_type = message_data.get("message_type", "")
        sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")
        chat_type = message_data.get("chat_type", "")  # p2p / group

        content = ""
        if msg_type == "text":
            try:
                content_json = json.loads(message_data.get("content", "{}"))
                content = content_json.get("text", "").strip()
            except json.JSONDecodeError:
                pass

        if not content or not sender_id:
            return None

        msg = Message(
            content=content,
            sender_id=sender_id,
            channel="feishu",
            msg_type=msg_type,
            raw=body,
        )

        if self._handler:
            reply = await self._handler(msg)
            if reply:
                await self.send(sender_id, Message(content=reply, channel="feishu"))

        return None

    # ---- 内部方法 ----

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=15)
        return self._http

    async def _get_access_token(self) -> str:
        """获取飞书 tenant_access_token（自动缓存）"""
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        http = self._get_http()
        resp = await http.post(
            f"{self._settings.api_base}/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self._settings.app_id,
                "app_secret": self._settings.app_secret,
            },
        )
        data = resp.json()
        self._access_token = data.get("tenant_access_token", "")
        expire = data.get("expire", 7200)
        self._token_expires = time.time() + expire - 300
        return self._access_token
