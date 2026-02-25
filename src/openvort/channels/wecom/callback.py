"""
企微回调服务

接收企微推送的消息（Webhook 模式）。
基于 FastAPI 路由，可挂载到主应用。
"""

from fastapi import APIRouter, Query, Request, Response

from openvort.channels.wecom.crypto import WeComCrypto
from openvort.plugin.base import Message, MessageHandler
from openvort.utils.logging import get_logger

log = get_logger("channels.wecom.callback")


def create_callback_router(crypto: WeComCrypto, handler: MessageHandler) -> APIRouter:
    """创建企微回调路由

    Args:
        crypto: 加解密实例
        handler: 消息处理回调

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

            # 转换为统一 Message
            msg = Message(
                content=msg_dict.get("Content", ""),
                sender_id=msg_dict.get("FromUserName", ""),
                channel="wecom",
                msg_type=msg_dict.get("MsgType", "text"),
                raw=msg_dict,
            )

            # 图片消息
            if msg.msg_type == "image":
                msg.content = "[用户发送了一张图片]"
                msg.images = [{"pic_url": msg_dict.get("PicUrl", ""), "media_id": msg_dict.get("MediaId", "")}]

            # 异步处理，不阻塞回调响应
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
