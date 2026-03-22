"""
飞书回调服务

接收飞书 Event Subscription 推送消息。
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from openvort.channels.feishu.crypto import FeishuCrypto
from openvort.utils.logging import get_logger

log = get_logger("channels.feishu.callback")


def create_feishu_callback_router(channel) -> APIRouter:
    """创建飞书回调路由。"""
    router = APIRouter()

    @router.post("/callback/feishu")
    async def handle_event(request: Request):
        try:
            body = await request.json()
        except Exception as e:
            log.error(f"解析飞书回调失败: {e}")
            return JSONResponse({"code": 400, "msg": "invalid json"}, status_code=400)

        try:
            crypto = FeishuCrypto(getattr(channel._settings, "encrypt_key", "")) if getattr(channel._settings, "encrypt_key", "") else None  # noqa: SLF001
            if body.get("encrypt"):
                if crypto is None:
                    return JSONResponse({"code": 400, "msg": "encrypt_key not configured"}, status_code=400)
                body = crypto.decrypt(body["encrypt"])

            verification_token = getattr(channel._settings, "verification_token", "")  # noqa: SLF001
            if verification_token and not FeishuCrypto.verify_token(body, verification_token):
                return JSONResponse({"code": 403, "msg": "invalid token"}, status_code=403)

            result = await channel.handle_event(body)
            if isinstance(result, dict):
                return JSONResponse(result)
            return JSONResponse({"code": 0})
        except Exception as e:
            log.error(f"处理飞书回调失败: {e}", exc_info=True)
            return JSONResponse({"code": 500, "msg": str(e)}, status_code=500)

    return router
