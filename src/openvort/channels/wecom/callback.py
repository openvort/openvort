"""
企微回调服务

接收企微推送的消息（Webhook 模式）。
基于 FastAPI 路由，可挂载到主应用。
支持自建应用回调 (/callback/wecom) 和智能机器人回调 (/callback/wecom/bot)。
"""

from fastapi import APIRouter, Query, Request, Response

from openvort.channels.wecom.crypto import WeComCrypto
from openvort.plugin.base import Message, MessageHandler
from openvort.utils.logging import get_logger

log = get_logger("channels.wecom.callback")


def create_callback_router(crypto: WeComCrypto, handler: MessageHandler, inbox=None) -> APIRouter:
    """创建企微回调路由

    Args:
        crypto: 加解密实例
        handler: 消息处理回调
        inbox: InboxService for cross-instance dedup (optional)

    Returns:
        FastAPI APIRouter
    """
    router = APIRouter()

    @router.get("/callback/wecom")
    async def verify_url(
        msg_signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
        echostr: str = Query(...),
    ):
        """URL 验证（企微配置回调时调用）"""
        try:
            if crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
                decrypted = crypto.decrypt(echostr)
                return Response(content=decrypted, media_type="text/plain")
        except Exception as e:
            log.error(f"URL 验证失败: {e}")
        return Response(content="verification failed", status_code=403)

    @router.post("/callback/wecom")
    async def receive_message(
        request: Request,
        msg_signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
    ):
        """接收消息"""
        try:
            body = await request.body()
            msg_dict = crypto.decrypt_callback(body.decode(), msg_signature, timestamp, nonce)

            # DB-level dedup
            msg_id = msg_dict.get("MsgId", "")
            if msg_id and inbox:
                if not await inbox.try_claim("wecom", msg_id):
                    return Response(content="success", media_type="text/plain")

            msg = Message(
                content=msg_dict.get("Content", ""),
                sender_id=msg_dict.get("FromUserName", ""),
                channel="wecom",
                msg_type=msg_dict.get("MsgType", "text"),
                raw=msg_dict,
            )

            if msg.msg_type == "image":
                msg.content = "[用户发送了一张图片]"
                msg.images = [{"pic_url": msg_dict.get("PicUrl", ""), "media_id": msg_dict.get("MediaId", "")}]

            if msg.msg_type == "voice":
                msg.content = "[用户发送了一段语音]"
                media_id = msg_dict.get("MediaId", "")
                if media_id:
                    msg.voice_media_ids = [media_id]

            import asyncio
            asyncio.create_task(_handle_message(msg, handler))

            return Response(content="success", media_type="text/plain")

        except Exception as e:
            log.error(f"消息处理失败: {e}")
            return Response(content="error", status_code=500)

    async def _handle_message(msg: Message, handler: MessageHandler):
        """异步处理消息"""
        try:
            await handler(msg)
        except Exception as e:
            log.error(f"消息 handler 异常: {e}")

    return router


def create_bot_callback_router(crypto: WeComCrypto, handler: MessageHandler, inbox=None) -> APIRouter:
    """创建智能机器人回调路由（公网部署可选）

    Protocol is identical to the app callback (XML + AES),
    but the XML contains BotId instead of AgentID.
    """
    router = APIRouter()

    @router.get("/callback/wecom/bot")
    async def verify_bot_url(
        msg_signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
        echostr: str = Query(...),
    ):
        try:
            if crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
                decrypted = crypto.decrypt(echostr)
                return Response(content=decrypted, media_type="text/plain")
        except Exception as e:
            log.error(f"Bot URL 验证失败: {e}")
        return Response(content="verification failed", status_code=403)

    @router.post("/callback/wecom/bot")
    async def receive_bot_message(
        request: Request,
        msg_signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
    ):
        try:
            body = await request.body()
            msg_dict = crypto.decrypt_callback(body.decode(), msg_signature, timestamp, nonce)

            # DB-level dedup
            msg_id = msg_dict.get("MsgId", "")
            if msg_id and inbox:
                if not await inbox.try_claim("wecom", msg_id):
                    return Response(content="success", media_type="text/plain")

            msg = Message(
                content=msg_dict.get("Content", ""),
                sender_id=msg_dict.get("FromUserName", ""),
                channel="wecom",
                msg_type=msg_dict.get("MsgType", "text"),
                raw=msg_dict,
            )

            if msg.msg_type == "image":
                msg.content = "[用户发送了一张图片]"
                msg.images = [{"pic_url": msg_dict.get("PicUrl", ""), "media_id": msg_dict.get("MediaId", "")}]

            if msg.msg_type == "voice":
                msg.content = "[用户发送了一段语音]"
                media_id = msg_dict.get("MediaId", "")
                if media_id:
                    msg.voice_media_ids = [media_id]

            import asyncio
            asyncio.create_task(_handle_bot_msg(msg, handler))

            return Response(content="success", media_type="text/plain")

        except Exception as e:
            log.error(f"Bot 消息处理失败: {e}")
            return Response(content="error", status_code=500)

    async def _handle_bot_msg(msg: Message, handler: MessageHandler):
        try:
            await handler(msg)
        except Exception as e:
            log.error(f"Bot 消息 handler 异常: {e}")

    return router
