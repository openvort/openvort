"""
企业微信 Channel

实现 BaseChannel 接口，支持两种消息接收模式：
- Webhook 回调（标准模式，需要公网地址）
- 远程数据库轮询（兼容模式，适用于无公网 IP 的场景）
"""

import asyncio
import json

import httpx
import pymysql

from openvort.channels.wecom.api import WeComAPI
from openvort.config.settings import WeComSettings
from openvort.plugin.base import BaseChannel, Message, MessageHandler
from openvort.utils.logging import get_logger

log = get_logger("channels.wecom")


class WeComChannel(BaseChannel):
    """企业微信通道"""

    name = "wecom"
    display_name = "企业微信"

    def __init__(self, settings: WeComSettings | None = None):
        if settings is None:
            settings = WeComSettings()
        self._settings = settings
        self._api: WeComAPI | None = None
        self._handler: MessageHandler | None = None
        self._running = False
        self._poll_task: asyncio.Task | None = None

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
        log.info("企微 Channel 已停止")

    async def send(self, target: str, message: Message) -> None:
        """发送消息"""
        if message.msg_type == "markdown":
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
        """启动远程数据库轮询模式

        Args:
            db_config: 远程 MySQL 配置 {"host", "user", "password", "database", "charset"}
            poll_interval: 轮询间隔（秒）
            aggregate_wait: 消息聚合等待时间（秒）
        """
        if not self._handler:
            log.error("未注册消息 handler，无法启动轮询")
            return

        self._running = True
        self._poll_task = asyncio.create_task(
            self._poll_loop(db_config, poll_interval, aggregate_wait)
        )
        log.info(f"企微轮询模式已启动（间隔 {poll_interval}s）")

    async def _poll_loop(self, db_config: dict, interval: float, agg_wait: float) -> None:
        """轮询主循环"""
        last_id = 0
        processed_ids: set = set()

        while self._running:
            try:
                messages = await asyncio.to_thread(self._fetch_messages, db_config, last_id)

                if messages:
                    new_msgs = [m for m in messages if m["msg_id"] not in processed_ids]

                    if new_msgs:
                        # 聚合窗口
                        await asyncio.sleep(agg_wait)
                        extra = await asyncio.to_thread(self._fetch_messages, db_config, new_msgs[-1]["db_id"])
                        if extra:
                            new_msgs.extend(extra)

                        aggregated = self._aggregate(new_msgs)
                        for msg in aggregated:
                            if self._handler:
                                reply = await self._handler(msg)
                                if reply:
                                    await self.send(msg.sender_id, Message(content=reply, channel="wecom"))

                            # 标记已处理
                            if hasattr(msg, "raw") and "_all_msg_ids" in msg.raw:
                                processed_ids.update(msg.raw["_all_msg_ids"])
                            else:
                                processed_ids.add(msg.raw.get("msg_id", ""))

                    last_id = messages[-1]["db_id"]

                    # 缓存清理
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
        """从远程数据库获取新消息（同步，在线程中执行）"""
        try:
            conn = pymysql.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, add_time, data FROM wecom_api_data WHERE id > %s ORDER BY id ASC",
                (last_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            messages = []
            for db_id, add_time, data_str in rows:
                try:
                    data = json.loads(data_str)
                    messages.append({
                        "db_id": db_id,
                        "msg_id": data.get("MsgId", ""),
                        "from_user": data.get("FromUserName", ""),
                        "msg_type": data.get("MsgType", ""),
                        "content": data.get("Content", ""),
                        "create_time": int(data.get("CreateTime", add_time)),
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
            if len(msgs) == 1:
                m = msgs[0]
                result.append(Message(
                    content=m["content"],
                    sender_id=m["from_user"],
                    channel="wecom",
                    msg_type=m["msg_type"],
                    raw=m,
                ))
            else:
                combined = "\n".join(m["content"] for m in msgs)
                last = msgs[-1]
                raw = dict(last)
                raw["_all_msg_ids"] = [m["msg_id"] for m in msgs]
                result.append(Message(
                    content=combined,
                    sender_id=uid,
                    channel="wecom",
                    msg_type=last["msg_type"],
                    raw=raw,
                ))
        return result
