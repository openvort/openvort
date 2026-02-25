#!/usr/bin/env python3
"""
OpenVort Relay — 企微消息中继服务（独立部署版）

部署在公网服务器上，接收企微回调消息，供本地/内网的 OpenVort 引擎拉取。
单文件，不依赖 openvort 包。

使用方法：
    1. pip install -r requirements.txt
    2. 修改下方配置（或设置环境变量）
    3. python relay.py
    4. 在企微后台填写回调 URL: http://your-server:8080/callback/wecom

环境变量（优先级高于下方默认值）：
    RELAY_WECOM_CORP_ID       企业ID
    RELAY_WECOM_APP_SECRET    应用Secret
    RELAY_WECOM_AGENT_ID      应用AgentId
    RELAY_WECOM_TOKEN         回调Token
    RELAY_WECOM_AES_KEY       回调EncodingAESKey
    RELAY_SECRET              Relay API 鉴权密钥（可选）
    RELAY_PORT                监听端口（默认 8080）
    RELAY_DB_PATH             SQLite 路径（默认 relay.db）
"""

import base64
import hashlib
import json
import os
import random
import sqlite3
import string
import struct
import time
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager

import httpx
import uvicorn
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse

# ============================================================
# 配置（修改这里，或通过环境变量覆盖）
# ============================================================

WECOM_CORP_ID = os.getenv("RELAY_WECOM_CORP_ID", "")
WECOM_APP_SECRET = os.getenv("RELAY_WECOM_APP_SECRET", "")
WECOM_AGENT_ID = os.getenv("RELAY_WECOM_AGENT_ID", "")
WECOM_TOKEN = os.getenv("RELAY_WECOM_TOKEN", "")
WECOM_AES_KEY = os.getenv("RELAY_WECOM_AES_KEY", "")
WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"

RELAY_SECRET = os.getenv("RELAY_SECRET", "")  # API 鉴权密钥，为空则不鉴权
RELAY_PORT = int(os.getenv("RELAY_PORT", "8080"))
RELAY_DB_PATH = os.getenv("RELAY_DB_PATH", "relay.db")

# ============================================================
# 企微消息加解密
# ============================================================


class WeComCrypto:
    """企微回调消息签名验证 + AES 加解密"""

    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        self.token = token
        self.corp_id = corp_id
        self.aes_key = base64.b64decode(encoding_aes_key + "=")

    def verify_signature(self, signature: str, timestamp: str, nonce: str, echostr: str = "") -> bool:
        items = sorted([self.token, timestamp, nonce, echostr])
        sha1 = hashlib.sha1("".join(items).encode()).hexdigest()
        return sha1 == signature

    def decrypt(self, encrypted: str) -> str:
        cipher_text = base64.b64decode(encrypted)
        iv = self.aes_key[:16]
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(cipher_text) + decryptor.finalize()
        pad_len = decrypted[-1]
        content = decrypted[:-pad_len]
        msg_len = struct.unpack("!I", content[16:20])[0]
        msg = content[20:20 + msg_len].decode("utf-8")
        from_corp_id = content[20 + msg_len:].decode("utf-8")
        if from_corp_id != self.corp_id:
            raise ValueError(f"corp_id 不匹配: {from_corp_id} != {self.corp_id}")
        return msg

    def decrypt_callback(self, xml_text: str, msg_signature: str, timestamp: str, nonce: str) -> dict:
        root = ET.fromstring(xml_text)
        encrypt_node = root.find("Encrypt")
        if encrypt_node is None:
            raise ValueError("XML 中缺少 Encrypt 节点")
        encrypted = encrypt_node.text
        if not self.verify_signature(msg_signature, timestamp, nonce, encrypted):
            raise ValueError("签名验证失败")
        decrypted_xml = self.decrypt(encrypted)
        msg_root = ET.fromstring(decrypted_xml)
        return {child.tag: child.text or "" for child in msg_root}


# ============================================================
# SQLite 消息存储
# ============================================================


class RelayStore:
    """轻量消息存储"""

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id TEXT DEFAULT '',
                from_user TEXT DEFAULT '',
                msg_type TEXT DEFAULT 'text',
                content TEXT DEFAULT '',
                raw_data TEXT DEFAULT '{}',
                processed INTEGER DEFAULT 0,
                created_at REAL DEFAULT 0
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_processed ON messages(processed)")
        self.conn.commit()

    def save(self, msg: dict) -> int:
        cur = self.conn.execute(
            "INSERT INTO messages (msg_id, from_user, msg_type, content, raw_data, created_at) VALUES (?,?,?,?,?,?)",
            (
                msg.get("MsgId", ""),
                msg.get("FromUserName", ""),
                msg.get("MsgType", "text"),
                msg.get("Content", ""),
                json.dumps(msg, ensure_ascii=False),
                float(msg.get("CreateTime", time.time())),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_messages(self, since_id: int = 0, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, msg_id, from_user, msg_type, content, raw_data, processed, created_at "
            "FROM messages WHERE id > ? ORDER BY id ASC LIMIT ?",
            (since_id, limit),
        ).fetchall()
        return [
            {
                "id": r[0], "msg_id": r[1], "from_user": r[2], "msg_type": r[3],
                "content": r[4], "raw_data": json.loads(r[5]) if r[5] else {},
                "processed": bool(r[6]), "created_at": r[7],
            }
            for r in rows
        ]

    def mark_processed(self, msg_id: int):
        self.conn.execute("UPDATE messages SET processed = 1 WHERE id = ?", (msg_id,))
        self.conn.commit()

    def cleanup(self, max_age_hours: int = 72) -> int:
        cutoff = time.time() - max_age_hours * 3600
        cur = self.conn.execute("DELETE FROM messages WHERE created_at < ? AND processed = 1", (cutoff,))
        self.conn.commit()
        return cur.rowcount


# ============================================================
# 企微 Token 管理
# ============================================================

_token_cache = {"token": "", "expires": 0}


async def get_wecom_token() -> str:
    if _token_cache["token"] and time.time() < _token_cache["expires"] - 60:
        return _token_cache["token"]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{WECOM_API_BASE}/gettoken",
            params={"corpid": WECOM_CORP_ID, "corpsecret": WECOM_APP_SECRET},
        )
        data = resp.json()
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"获取 token 失败: {data}")
    _token_cache["token"] = data["access_token"]
    _token_cache["expires"] = time.time() + data.get("expires_in", 7200)
    return _token_cache["token"]


# ============================================================
# FastAPI 应用
# ============================================================

store: RelayStore | None = None
crypto: WeComCrypto | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, crypto
    store = RelayStore(RELAY_DB_PATH)
    if WECOM_TOKEN and WECOM_AES_KEY:
        crypto = WeComCrypto(WECOM_TOKEN, WECOM_AES_KEY, WECOM_CORP_ID)
    print(f"[Relay] 已启动 | DB: {RELAY_DB_PATH} | 加解密: {'✅' if crypto else '❌ 未配置'}")
    yield
    print("[Relay] 已关闭")


app = FastAPI(title="OpenVort Relay", version="0.1.0", lifespan=lifespan)


def check_auth(request: Request) -> bool:
    if not RELAY_SECRET:
        return True
    return request.headers.get("Authorization", "") == f"Bearer {RELAY_SECRET}"


# ---- 企微回调 ----


@app.get("/callback/wecom")
async def verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """企微回调 URL 验证"""
    if not crypto:
        return Response(content="crypto not configured", status_code=500)
    try:
        if crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
            decrypted = crypto.decrypt(echostr)
            print(f"[Relay] URL 验证成功")
            return Response(content=decrypted, media_type="text/plain")
    except Exception as e:
        print(f"[Relay] URL 验证失败: {e}")
    return Response(content="verification failed", status_code=403)


@app.post("/callback/wecom")
async def receive_message(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    """接收企微回调消息"""
    if not crypto:
        return Response(content="crypto not configured", status_code=500)
    try:
        body = await request.body()
        msg_dict = crypto.decrypt_callback(body.decode(), msg_signature, timestamp, nonce)
        msg_id = store.save(msg_dict)
        print(f"[Relay] 收到消息 #{msg_id}: {msg_dict.get('FromUserName', '')} -> {msg_dict.get('MsgType', '')} | {msg_dict.get('Content', '')[:50]}")
        return Response(content="success", media_type="text/plain")
    except Exception as e:
        print(f"[Relay] 回调处理失败: {e}")
        return Response(content="error", status_code=500)


# ---- Relay API ----


@app.get("/relay/messages")
async def get_messages(
    request: Request,
    since_id: int = Query(0),
    limit: int = Query(50),
):
    """拉取新消息"""
    if not check_auth(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    messages = store.get_messages(since_id=since_id, limit=limit)
    return JSONResponse({"messages": messages})


@app.post("/relay/messages/{msg_id}/ack")
async def ack_message(request: Request, msg_id: int):
    """标记消息已处理"""
    if not check_auth(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    store.mark_processed(msg_id)
    return JSONResponse({"ok": True})


@app.post("/relay/send")
async def send_message(request: Request):
    """代理发送消息到企微"""
    if not check_auth(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    body = await request.json()
    touser = body.get("touser", "")
    content = body.get("content", "")
    msg_type = body.get("msg_type", "text")

    if not touser or not content:
        return JSONResponse({"error": "touser and content required"}, status_code=400)

    try:
        token = await get_wecom_token()
        payload = {"touser": touser, "agentid": WECOM_AGENT_ID, "msgtype": msg_type}
        if msg_type == "markdown":
            payload["markdown"] = {"content": content}
        else:
            payload["text"] = {"content": content}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{WECOM_API_BASE}/message/send?access_token={token}", json=payload)
            data = resp.json()

        if data.get("errcode", 0) != 0:
            print(f"[Relay] 发送失败: {data}")
            return JSONResponse({"error": data.get("errmsg", "unknown")}, status_code=502)

        print(f"[Relay] 已发送消息 -> {touser}")
        return JSONResponse({"ok": True})
    except Exception as e:
        print(f"[Relay] 发送异常: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/relay/health")
async def health():
    """健康检查"""
    info = {
        "status": "ok",
        "crypto": bool(crypto),
        "corp_id": WECOM_CORP_ID[:6] + "***" if WECOM_CORP_ID else "",
        "db": RELAY_DB_PATH,
    }
    try:
        token = await get_wecom_token()
        info["wecom_api"] = bool(token)
    except Exception:
        info["wecom_api"] = False
    return JSONResponse(info)


@app.post("/relay/cleanup")
async def cleanup(request: Request):
    """清理过期消息"""
    if not check_auth(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    deleted = store.cleanup()
    return JSONResponse({"deleted": deleted})


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    if not WECOM_CORP_ID or not WECOM_APP_SECRET:
        print("❌ 请配置 RELAY_WECOM_CORP_ID 和 RELAY_WECOM_APP_SECRET")
        print("   可以修改 relay.py 顶部的配置，或设置环境变量")
        exit(1)

    print(f"""
╔══════════════════════════════════════════╗
║       OpenVort Relay Server v0.1         ║
╠══════════════════════════════════════════╣
║  端口: {RELAY_PORT:<33}║
║  数据库: {RELAY_DB_PATH:<31}║
║  加解密: {'已配置' if WECOM_TOKEN and WECOM_AES_KEY else '未配置（无法接收回调）':<25}║
║  鉴权: {'已启用' if RELAY_SECRET else '未启用':<27}║
╠══════════════════════════════════════════╣
║  回调地址:                               ║
║  http://your-domain:{RELAY_PORT}/callback/wecom{' ' * (5 - len(str(RELAY_PORT)))}║
║                                          ║
║  API 地址:                               ║
║  http://your-domain:{RELAY_PORT}/relay/{' ' * (12 - len(str(RELAY_PORT)))}║
╚══════════════════════════════════════════╝
""")
    uvicorn.run(app, host="0.0.0.0", port=RELAY_PORT, log_level="info")
