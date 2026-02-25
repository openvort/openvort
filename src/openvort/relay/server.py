"""
Relay Server — 企微消息中继服务

部署在公网服务器上，职责：
1. 接收企微回调消息，存入本地 SQLite
2. 暴露 REST API 供 OpenVort 引擎拉取消息
3. 代理转发消息到企微 API

不跑 AI，不跑业务逻辑，资源占用极低。
"""

import json
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse

from openvort.channels.wecom.crypto import WeComCrypto
from openvort.relay.store import RelayStore
from openvort.utils.logging import get_logger, setup_logging

log = get_logger("relay.server")

# 全局状态
_store: RelayStore | None = None
_crypto: WeComCrypto | None = None
_wecom_token: str = ""
_wecom_token_expires: float = 0
_corp_id: str = ""
_app_secret: str = ""
_agent_id: str = ""
_api_base: str = "https://qyapi.weixin.qq.com/cgi-bin"
_relay_secret: str = ""


def create_app(
    corp_id: str,
    app_secret: str,
    agent_id: str,
    callback_token: str = "",
    callback_aes_key: str = "",
    relay_secret: str = "",
    db_path: str = "relay.db",
    api_base: str = "https://qyapi.weixin.qq.com/cgi-bin",
) -> FastAPI:
    """创建 Relay FastAPI 应用"""

    global _store, _crypto, _corp_id, _app_secret, _agent_id, _api_base, _relay_secret

    _corp_id = corp_id
    _app_secret = app_secret
    _agent_id = agent_id
    _api_base = api_base
    _relay_secret = relay_secret

    if callback_token and callback_aes_key:
        _crypto = WeComCrypto(callback_token, callback_aes_key, corp_id)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _store
        _store = RelayStore(db_path)
        _store.init()
        log.info(f"Relay Server 已启动 (db: {db_path})")
        yield
        log.info("Relay Server 已关闭")

    app = FastAPI(title="OpenVort Relay", version="0.1.0", lifespan=lifespan)

    # ---- 鉴权中间件 ----

    def _check_auth(request: Request) -> bool:
        """检查 relay API 鉴权"""
        if not _relay_secret:
            return True
        auth = request.headers.get("Authorization", "")
        return auth == f"Bearer {_relay_secret}"

    # ---- 企微回调 ----

    @app.get("/callback/wecom")
    async def verify_url(
        msg_signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
        echostr: str = Query(...),
    ):
        """企微回调 URL 验证"""
        if not _crypto:
            return Response(content="crypto not configured", status_code=500)
        try:
            if _crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
                decrypted = _crypto.decrypt(echostr)
                return Response(content=decrypted, media_type="text/plain")
        except Exception as e:
            log.error(f"URL 验证失败: {e}")
        return Response(content="verification failed", status_code=403)

    @app.post("/callback/wecom")
    async def receive_message(
        request: Request,
        msg_signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
    ):
        """接收企微回调消息"""
        if not _crypto:
            return Response(content="crypto not configured", status_code=500)
        try:
            body = await request.body()
            msg_dict = _crypto.decrypt_callback(body.decode(), msg_signature, timestamp, nonce)
            _store.save_message(msg_dict)
            log.info(f"收到消息: {msg_dict.get('FromUserName', '')} -> {msg_dict.get('MsgType', '')}")
            return Response(content="success", media_type="text/plain")
        except Exception as e:
            log.error(f"回调处理失败: {e}")
            return Response(content="error", status_code=500)

    # ---- Relay API ----

    @app.get("/relay/messages")
    async def get_messages(
        request: Request,
        since_id: int = Query(0, description="从此 ID 之后拉取"),
        limit: int = Query(50, description="最多返回条数"),
    ):
        """拉取新消息"""
        if not _check_auth(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        messages = _store.get_messages(since_id=since_id, limit=limit)
        return JSONResponse({"messages": messages})

    @app.post("/relay/messages/{msg_id}/ack")
    async def ack_message(request: Request, msg_id: int):
        """标记消息已处理"""
        if not _check_auth(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        _store.mark_processed(msg_id)
        return JSONResponse({"ok": True})

    @app.post("/relay/send")
    async def send_message(request: Request):
        """代理发送消息到企微"""
        if not _check_auth(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        body = await request.json()
        touser = body.get("touser", "")
        content = body.get("content", "")
        msg_type = body.get("msg_type", "text")

        if not touser or not content:
            return JSONResponse({"error": "touser and content required"}, status_code=400)

        try:
            token = await _get_wecom_token()
            payload = {
                "touser": touser,
                "agentid": _agent_id,
                "msgtype": msg_type,
            }
            if msg_type == "markdown":
                payload["markdown"] = {"content": content}
            else:
                payload["text"] = {"content": content}

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{_api_base}/message/send?access_token={token}",
                    json=payload,
                )
                data = resp.json()

            if data.get("errcode", 0) != 0:
                log.error(f"发送失败: {data}")
                return JSONResponse({"error": data.get("errmsg", "unknown")}, status_code=502)

            return JSONResponse({"ok": True})

        except Exception as e:
            log.error(f"代理发送异常: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/relay/health")
    async def health():
        """健康检查"""
        try:
            token = await _get_wecom_token()
            return JSONResponse({"status": "ok", "has_token": bool(token)})
        except Exception as e:
            return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)

    return app


async def _get_wecom_token() -> str:
    """获取企微 access_token（带缓存）"""
    global _wecom_token, _wecom_token_expires

    if _wecom_token and time.time() < _wecom_token_expires - 60:
        return _wecom_token

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_api_base}/gettoken",
            params={"corpid": _corp_id, "corpsecret": _app_secret},
        )
        data = resp.json()

    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"获取 token 失败: {data}")

    _wecom_token = data["access_token"]
    _wecom_token_expires = time.time() + data.get("expires_in", 7200)
    return _wecom_token
