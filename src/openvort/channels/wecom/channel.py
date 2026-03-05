"""
企业微信 Channel

实现 BaseChannel 接口，支持三种消息接收模式：
- Webhook 回调（标准模式，需要公网地址）
- Relay 中继（推荐开发模式，OpenVort Relay Server 部署在公网）
- 远程数据库轮询（兼容模式，适用于无公网 IP 的场景）
"""

import asyncio
import base64
import json
from pathlib import Path

import httpx

from openvort.channels.wecom.api import WeComAPI
from openvort.config.settings import WeComSettings
from openvort.plugin.base import BaseChannel, Message, MessageHandler
from openvort.utils.logging import get_logger

log = get_logger("channels.wecom")


class WeComChannel(BaseChannel):
    """企业微信通道"""

    name = "wecom"
    display_name = "企业微信"
    description = "企业微信 IM 通道，支持 Webhook/Relay/DB轮询三种模式接收消息"

    # 持久化文件：记录各模式的消费位点，重启后从断点继续
    _CURSOR_FILE = Path.home() / ".openvort" / "wecom_cursor.json"

    def __init__(self, settings: WeComSettings | None = None):
        if settings is None:
            settings = WeComSettings()
        self._settings = settings
        self._allowed_users: set[str] = self._parse_allowed_users(settings.allowed_users)
        self._api: WeComAPI | None = None
        self._handler: MessageHandler | None = None
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._relay_url: str = ""
        self._relay_secret: str = ""
        self._relay_http: httpx.AsyncClient | None = None

    # ---- 消费位点持久化 ----

    def _load_cursor(self, mode: str) -> int:
        """加载持久化的消费位点"""
        try:
            if self._CURSOR_FILE.exists():
                data = json.loads(self._CURSOR_FILE.read_text(encoding="utf-8"))
                return data.get(mode, 0)
        except Exception as e:
            log.warning(f"加载消费位点失败: {e}")
        return 0

    def _save_cursor(self, mode: str, last_id: int) -> None:
        """持久化消费位点"""
        try:
            self._CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if self._CURSOR_FILE.exists():
                data = json.loads(self._CURSOR_FILE.read_text(encoding="utf-8"))
            data[mode] = last_id
            self._CURSOR_FILE.write_text(json.dumps(data), encoding="utf-8")
        except Exception as e:
            log.warning(f"保存消费位点失败: {e}")

    def _parse_allowed_users(self, allowed_users: str) -> set[str]:
        """解析白名单用户 ID"""
        if not allowed_users:
            return set()
        return {u.strip() for u in allowed_users.split(",") if u.strip()}

    @property
    def api(self) -> WeComAPI:
        """延迟初始化 API 客户端"""
        if self._api is None:
            self._api = WeComAPI(
                corp_id=self._settings.corp_id,
                app_secret=self._settings.app_secret,
                agent_id=self._settings.agent_id,
                api_base=self._settings.api_base_url,
            )
        return self._api

    def get_sync_provider(self):
        """返回企微通讯录同步提供者"""
        from openvort.channels.wecom.sync import WeComContactSyncProvider
        if not self.is_configured():
            return None
        return WeComContactSyncProvider(self.api)

    def get_channel_prompt(self) -> str:
        """返回企微渠道的回复风格 prompt"""
        from pathlib import Path
        prompt_file = Path(__file__).parent / "prompts" / "channel_style.md"
        if prompt_file.exists():
            try:
                return prompt_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""

    def get_max_reply_length(self) -> int:
        """企微单条消息限制"""
        return 2000

    # ---- 配置管理 ----

    def get_config_schema(self) -> list[dict]:
        return [
            {"key": "corp_id", "label": "企业 ID", "type": "string", "required": True, "secret": False, "placeholder": "ww1234567890abcdef",
             "description": "企微管理后台 → 我的企业 → 企业信息 → 企业 ID"},
            {"key": "app_secret", "label": "应用 Secret", "type": "string", "required": True, "secret": True, "placeholder": "",
             "description": "企微管理后台 → 应用管理 → 自建应用 → Secret"},
            {"key": "agent_id", "label": "应用 AgentId", "type": "string", "required": True, "secret": False, "placeholder": "1000002",
             "description": "自建应用详情页顶部的 AgentId"},
            {"key": "callback_token", "label": "回调 Token", "type": "string", "required": False, "secret": True, "placeholder": "用于 Webhook 回调验证",
             "description": "自建应用 → API接收消息 → 设置接收事件服务器时生成"},
            {"key": "callback_aes_key", "label": "回调 EncodingAESKey", "type": "string", "required": False, "secret": True, "placeholder": "用于 Webhook 回调解密",
             "description": "与回调 Token 一同生成，用于消息解密"},
            {"key": "api_base_url", "label": "API 地址", "type": "string", "required": False, "secret": False, "placeholder": "https://qyapi.weixin.qq.com/cgi-bin",
             "description": "企微 API 地址，通常无需修改"},
        ]

    def get_setup_guide(self) -> str:
        return (
            "### 企业微信配置指南\n\n"
            "1. 登录 [企业微信管理后台](https://work.weixin.qq.com/wework_admin/frame)\n"
            "2. 进入「我的企业」→「企业信息」，复制 **企业 ID**\n"
            "3. 进入「应用管理」→「自建」→ 创建应用（或选择已有应用）\n"
            "4. 在应用详情页获取 **AgentId** 和 **Secret**\n"
            "5. 如需 Webhook 模式：在「API接收消息」中设置接收服务器，获取 **Token** 和 **EncodingAESKey**\n"
            "6. 如无公网 IP，推荐使用 Relay 中继模式（启动时加 `--relay-url`）\n"
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
            "corp_id": s.corp_id,
            "app_secret": _mask(s.app_secret),
            "agent_id": s.agent_id,
            "callback_token": _mask(s.callback_token),
            "callback_aes_key": _mask(s.callback_aes_key),
            "api_base_url": s.api_base_url,
        }

    def apply_config(self, config: dict) -> None:
        s = self._settings
        if "corp_id" in config:
            s.corp_id = config["corp_id"]
        if "app_secret" in config:
            s.app_secret = config["app_secret"]
        if "agent_id" in config:
            s.agent_id = config["agent_id"]
        if "callback_token" in config:
            s.callback_token = config["callback_token"]
        if "callback_aes_key" in config:
            s.callback_aes_key = config["callback_aes_key"]
        if "api_base_url" in config:
            s.api_base_url = config["api_base_url"]
        # 重置 API 客户端，下次使用时重新初始化
        self._api = None

    async def test_connection(self) -> dict:
        if not self.is_configured():
            return {"ok": False, "message": "企业 ID 和应用 Secret 未配置"}
        try:
            token = await self.api.get_access_token()
            if token:
                return {"ok": True, "message": "连接成功，已获取 access_token"}
            return {"ok": False, "message": "获取 access_token 失败"}
        except Exception as e:
            return {"ok": False, "message": f"连接失败: {e}"}

    def get_connection_info(self) -> dict:
        def _mask(value: str) -> str:
            if not value:
                return ""
            if len(value) <= 4:
                return "****"
            return "****" + value[-4:]

        if self._relay_url:
            mode = "relay"
        elif self._poll_task and not self._poll_task.done():
            mode = "poll-db"
        elif self._running:
            mode = "webhook"
        else:
            mode = "未启动"

        return {
            "mode": mode,
            "relay_url": self._relay_url or "",
            "relay_secret": _mask(self._relay_secret),
        }

    async def start(self) -> None:
        """启动通道"""
        if not self.is_configured():
            log.warning("企微 Channel 未配置，跳过启动")
            return
        self._running = True
        log.info("企微 Channel 已启动")

    async def stop(self) -> None:
        """停止通道"""
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        if self._api:
            await self._api.close()
        if self._relay_http:
            await self._relay_http.aclose()
        log.info("企微 Channel 已停止")

    async def send(self, target: str, message: Message) -> None:
        """发送消息（自动选择直连或 relay）"""
        if self._relay_url:
            await self._relay_send(target, message)
        elif message.msg_type == "voice":
            # 发送语音消息
            voice_data = getattr(message, "voice_data", None)
            if voice_data:
                await self.api.send_voice(voice_data["media_id"], touser=target)
            else:
                log.warning("发送语音消息缺少 voice_data")
        elif message.msg_type == "markdown":
            await self.api.send_markdown(message.content, touser=target)
        else:
            await self.api.send_text(message.content, touser=target)

    def on_message(self, handler: MessageHandler) -> None:
        """注册消息回调"""
        self._handler = handler

    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self._settings.corp_id and self._settings.app_secret)

    # ---- 轮询模式（兼容无公网 IP 场景）----

    async def start_polling(self, db_config: dict, poll_interval: float = 3, aggregate_wait: float = 3) -> None:
        if not self._handler:
            log.error("未注册消息 handler，无法启动轮询")
            return
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop(db_config, poll_interval, aggregate_wait))
        log.info(f"企微轮询模式已启动（间隔 {poll_interval}s）")

    async def _poll_loop(self, db_config: dict, interval: float, agg_wait: float) -> None:
        last_id = self._load_cursor("poll_db")
        processed_ids: set = set()
        if last_id > 0:
            log.info(f"从持久化位点恢复 poll-db: last_id={last_id}")
        while self._running:
            try:
                messages = await asyncio.to_thread(self._fetch_messages, db_config, last_id)
                if messages:
                    new_msgs = [m for m in messages if m["msg_id"] not in processed_ids]
                    if new_msgs:
                        await asyncio.sleep(agg_wait)
                        extra = await asyncio.to_thread(self._fetch_messages, db_config, new_msgs[-1]["db_id"])
                        if extra:
                            new_msgs.extend(extra)
                        aggregated = self._aggregate(new_msgs)
                        for msg in aggregated:
                            # 白名单过滤
                            if self._allowed_users and msg.sender_id not in self._allowed_users:
                                log.debug(f"跳过非白名单用户: {msg.sender_id}")
                                continue
                            if self._handler:
                                reply = await self._handler(msg)
                                if reply:
                                    await self.send(msg.sender_id, Message(content=reply, channel="wecom"))
                            if hasattr(msg, "raw") and "_all_msg_ids" in msg.raw:
                                processed_ids.update(msg.raw["_all_msg_ids"])
                            else:
                                processed_ids.add(msg.raw.get("msg_id", ""))
                    last_id = messages[-1]["db_id"]
                    self._save_cursor("poll_db", last_id)
                    if len(processed_ids) > 500:
                        processed_ids = set(list(processed_ids)[-250:])
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"轮询异常: {e}")
                await asyncio.sleep(interval * 2)

    @staticmethod
    def _fetch_messages(db_config: dict, last_id: int) -> list[dict]:
        import pymysql
        try:
            conn = pymysql.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("SELECT id, add_time, data FROM wecom_api_data WHERE id > %s ORDER BY id ASC", (last_id,))
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            messages = []
            for db_id, add_time, data_str in rows:
                try:
                    data = json.loads(data_str)
                    messages.append({
                        "db_id": db_id, "msg_id": data.get("MsgId", ""),
                        "from_user": data.get("FromUserName", ""), "msg_type": data.get("MsgType", ""),
                        "content": data.get("Content", ""), "create_time": int(data.get("CreateTime", add_time)),
                        "raw": data,
                    })
                except Exception as e:
                    log.error(f"解析消息失败 db_id={db_id}: {e}")
            return messages
        except Exception as e:
            log.error(f"查询远程数据库失败: {e}")
            return []

    @staticmethod
    def _aggregate(messages: list[dict]) -> list[Message]:
        """聚合同一用户的连续消息"""
        user_msgs: dict[str, list[dict]] = {}
        for m in messages:
            user_msgs.setdefault(m["from_user"], []).append(m)
        result = []
        for uid, msgs in user_msgs.items():
            # 合并图片和语音
            all_images = []
            all_voice_media_ids = []
            for m in msgs:
                all_images.extend(m.get("images", []))
                voice_id = m.get("voice_media_id")
                if voice_id:
                    all_voice_media_ids.append(voice_id)

            if len(msgs) == 1:
                m = msgs[0]
                result.append(Message(
                    content=m["content"], sender_id=m["from_user"],
                    channel="wecom", msg_type=m["msg_type"],
                    images=all_images, voice_media_ids=all_voice_media_ids, raw=m,
                ))
            else:
                combined = "\n".join(m["content"] for m in msgs if m["content"])
                last = msgs[-1]
                raw = dict(last)
                raw["_all_msg_ids"] = [m["msg_id"] for m in msgs]
                # 有图片或语音时 msg_type 标记为 mixed
                has_media = all_images or all_voice_media_ids
                msg_type = "mixed" if has_media and combined else last["msg_type"]
                result.append(Message(
                    content=combined, sender_id=uid,
                    channel="wecom", msg_type=msg_type,
                    images=all_images, voice_media_ids=all_voice_media_ids, raw=raw,
                ))
        return result

    # ---- Relay 中继模式 ----

    def _get_relay_http(self) -> httpx.AsyncClient:
        """获取 relay HTTP 客户端"""
        if self._relay_http is None:
            headers = {}
            if self._relay_secret:
                headers["Authorization"] = f"Bearer {self._relay_secret}"
            self._relay_http = httpx.AsyncClient(base_url=self._relay_url, headers=headers, timeout=15)
        return self._relay_http

    async def start_relay(self, relay_url: str, relay_secret: str = "",
                          poll_interval: float = 3, aggregate_wait: float = 3) -> None:
        """启动 Relay 中继模式"""
        if not self._handler:
            log.error("未注册消息 handler，无法启动 relay")
            return
        self._relay_url = relay_url.rstrip("/")
        self._relay_secret = relay_secret
        self._running = True
        self._poll_task = asyncio.create_task(self._relay_poll_loop(poll_interval, aggregate_wait))
        log.info(f"企微 Relay 模式已启动 → {self._relay_url}")

    async def _relay_poll_loop(self, interval: float, agg_wait: float) -> None:
        """Relay 轮询主循环"""
        http = self._get_relay_http()

        # 从持久化位点恢复，跳过已处理的消息
        last_id = self._load_cursor("relay")

        if last_id > 0:
            log.info(f"从持久化位点恢复 relay: last_id={last_id}")
        else:
            # 首次启动：跳过历史消息，只 ack 不处理
            try:
                resp = await http.get("/relay/messages", params={"since_id": 0, "limit": 50})
                old_msgs = resp.json().get("messages", [])
                while old_msgs:
                    last_id = old_msgs[-1]["id"]
                    for m in old_msgs:
                        try:
                            await http.post(f"/relay/messages/{m['id']}/ack")
                        except Exception:
                            pass
                    log.info(f"跳过 {len(old_msgs)} 条历史消息 (last_id={last_id})")
                    # 继续拉取，直到没有更多历史消息
                    resp = await http.get("/relay/messages", params={"since_id": last_id, "limit": 50})
                    old_msgs = resp.json().get("messages", [])
                self._save_cursor("relay", last_id)
            except Exception as e:
                log.error(f"获取历史消息失败: {e}")
                last_id = 0

        while self._running:
            try:
                resp = await http.get("/relay/messages", params={"since_id": last_id, "limit": 50})
                data = resp.json()
                messages = data.get("messages", [])

                if messages:
                    # 聚合窗口
                    await asyncio.sleep(agg_wait)
                    resp2 = await http.get("/relay/messages", params={"since_id": messages[-1]["id"], "limit": 50})
                    extra = resp2.json().get("messages", [])
                    if extra:
                        messages.extend(extra)

                    # 转换格式并聚合
                    raw_msgs = []
                    for m in messages:
                        msg_type = m["msg_type"]
                        raw_data = m.get("raw_data", {})
                        images = []
                        voice_media_id = None

                        # 图片消息：提取 PicUrl / MediaId
                        if msg_type == "image":
                            pic_url = raw_data.get("PicUrl", "")
                            media_id = raw_data.get("MediaId", "")
                            if pic_url or media_id:
                                images.append({"pic_url": pic_url, "media_id": media_id})

                        # 语音消息：提取 MediaId
                        if msg_type == "voice":
                            voice_media_id = raw_data.get("MediaId", "")

                        raw_msgs.append({
                            "db_id": m["id"], "msg_id": m.get("msg_id", ""),
                            "from_user": m["from_user"], "msg_type": msg_type,
                            "content": m["content"], "raw": raw_data,
                            "images": images,
                            "voice_media_id": voice_media_id,
                        })

                    aggregated = self._aggregate(raw_msgs)
                    for msg in aggregated:
                        # 白名单过滤
                        if self._allowed_users and msg.sender_id not in self._allowed_users:
                            log.debug(f"跳过非白名单用户: {msg.sender_id}")
                            continue

                        # 纯图片/语音消息（无文本）：补充描述
                        if not msg.content or not msg.content.strip():
                            if msg.images:
                                msg.content = "[用户发送了图片]"
                            elif msg.voice_media_ids:
                                msg.content = "[用户发送了语音]"
                            elif msg.msg_type and msg.msg_type not in ("text", "mixed"):
                                log.info(f"收到不支持的消息类型: {msg.sender_id} (type={msg.msg_type})")
                                await self.send(
                                    msg.sender_id,
                                    Message(content="暂时只支持文字和图片消息哦，语音/文件等后续会支持 🙂", channel="wecom"),
                                )
                                continue
                            else:
                                log.warning(f"跳过空消息: {msg.sender_id} (msg_type={msg.msg_type})")
                                continue

                        # 下载图片（PicUrl → base64）
                        if msg.images:
                            msg.images = await self._download_images(msg.images)

                        # 下载语音（MediaId → bytes）
                        if msg.voice_media_ids:
                            msg.voice_data = await self._download_voices(msg.voice_media_ids)

                        if self._handler:
                            log.info(f"处理消息: {msg.sender_id} -> {msg.content[:50]}")
                            # handler 返回 None 表示消息已入队（dispatcher 模式），不发送
                            reply = await self._handler(msg)
                            if reply:
                                log.info(f"回复: {reply[:50]}")
                                await self.send(msg.sender_id, Message(content=reply, channel="wecom"))

                    # 标记已处理（包括跳过的消息）
                    for m in messages:
                        try:
                            await http.post(f"/relay/messages/{m['id']}/ack")
                        except Exception:
                            pass

                    last_id = messages[-1]["id"]
                    self._save_cursor("relay", last_id)

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Relay 轮询异常: {e}")
                await asyncio.sleep(interval * 2)

    async def _relay_send(self, target: str, message: Message) -> None:
        """通过 Relay 代理发送消息"""
        http = self._get_relay_http()
        try:
            payload = {
                "touser": target,
                "content": message.content,
                "msg_type": message.msg_type,
            }

            # 如果是语音消息，需要先上传获取 media_id
            if message.msg_type == "voice":
                voice_data = getattr(message, "voice_data", None)
                if voice_data:
                    # 调用企微 API 上传语音
                    file_content = voice_data.get("data", b"")
                    file_format = voice_data.get("format", "amr")
                    file_name = f"voice.{file_format}"
                    media_result = await self.api.upload_media("voice", file_content, file_name)
                    payload["media_id"] = media_result.get("media_id")
                else:
                    log.warning("Relay 发送语音消息缺少 voice_data")
                    return
                # 转换为 voice 类型让 relay 知道如何处理
                payload["msg_type"] = "voice"

            resp = await http.post("/relay/send", json=payload)
            data = resp.json()
            if not data.get("ok"):
                log.error(f"Relay 发送失败: {data}")
        except Exception as e:
            log.error(f"Relay 发送异常: {e}")

    async def relay_health_check(self) -> bool:
        """检查 Relay Server 连通性"""
        try:
            http = self._get_relay_http()
            resp = await http.get("/relay/health")
            return resp.json().get("status") == "ok"
        except Exception as e:
            log.error(f"Relay 健康检查失败: {e}")
            return False

    # ---- 图片处理 ----

    async def _download_images(self, images: list[dict]) -> list[dict]:
        """下载图片并转为 base64，返回增强后的 images 列表

        每个 image dict 增加 data (base64) 和 media_type 字段。
        """
        result = []
        async with httpx.AsyncClient(timeout=30) as client:
            for img in images:
                pic_url = img.get("pic_url", "")
                if not pic_url:
                    log.warning("图片缺少 pic_url，跳过")
                    continue
                try:
                    resp = await client.get(pic_url)
                    if resp.status_code != 200:
                        log.error(f"下载图片失败: HTTP {resp.status_code}")
                        continue
                    # 检测 media type
                    content_type = resp.headers.get("content-type", "image/jpeg")
                    if "png" in content_type:
                        media_type = "image/png"
                    elif "gif" in content_type:
                        media_type = "image/gif"
                    elif "webp" in content_type:
                        media_type = "image/webp"
                    else:
                        media_type = "image/jpeg"
                    img_b64 = base64.b64encode(resp.content).decode("ascii")
                    result.append({
                        **img,
                        "data": img_b64,
                        "media_type": media_type,
                    })
                    log.info(f"图片下载成功: {len(resp.content)} bytes ({media_type})")
                except Exception as e:
                    log.error(f"下载图片异常: {e}")
        return result

    async def _download_voices(self, media_ids: list[str]) -> list[dict]:
        """下载语音文件并返回列表

        每个 voice dict 增加 data (bytes) 和 format 字段。
        """
        result = []
        for media_id in media_ids:
            if not media_id:
                continue
            try:
                voice_data = await self.api.get_media(media_id)
                # 企微语音通常是 amr 或 silk 格式
                # 尝试检测格式
                format = "amr"
                if voice_data[:4] == b"\xFF\xFB\x90" or voice_data[:4] == b"\xFF\xFB\xA0":
                    format = "amr"
                elif voice_data[:2] == b"\x02\x21":
                    format = "silk"
                result.append({
                    "media_id": media_id,
                    "data": voice_data,
                    "format": format,
                    "size": len(voice_data),
                })
                log.info(f"语音下载成功: media_id={media_id}, size={len(voice_data)} bytes, format={format}")
            except Exception as e:
                log.error(f"下载语音异常: media_id={media_id}, error={e}")
        return result
