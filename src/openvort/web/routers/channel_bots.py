"""Channel Bot 管理路由 — AI 员工独立 IM Bot 凭证 CRUD"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from openvort.db.models import ChannelBot
from openvort.web.deps import get_db_session_factory, get_registry

router = APIRouter()


BOT_CREDENTIAL_FIELDS: dict[str, list[dict]] = {
    "wecom": [
        {"key": "bot_id", "label": "Bot ID", "secret": False, "required": True,
         "placeholder": "", "description": "智能机器人 -> 创建 AI 同事后获取"},
        {"key": "bot_secret", "label": "Bot Secret", "secret": True, "required": True,
         "placeholder": "", "description": "与 Bot ID 一同生成"},
    ],
    "dingtalk": [
        {"key": "app_key", "label": "App Key", "secret": False, "required": True,
         "placeholder": "", "description": "钉钉开放平台 -> 应用开发 -> 机器人"},
        {"key": "app_secret", "label": "App Secret", "secret": True, "required": True,
         "placeholder": "", "description": "与 App Key 一同生成"},
        {"key": "robot_code", "label": "Robot Code", "secret": False, "required": True,
         "placeholder": "", "description": "机器人的唯一标识"},
    ],
    "feishu": [
        {"key": "app_id", "label": "App ID", "secret": False, "required": True,
         "placeholder": "", "description": "飞书开放平台 -> 应用详情"},
        {"key": "app_secret", "label": "App Secret", "secret": True, "required": True,
         "placeholder": "", "description": "与 App ID 一同生成"},
    ],
}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


def _mask_credentials(channel_type: str, creds: dict) -> dict:
    schema = BOT_CREDENTIAL_FIELDS.get(channel_type, [])
    secret_keys = {f["key"] for f in schema if f.get("secret")}
    return {k: _mask(v) if k in secret_keys else v for k, v in creds.items()}


def _is_masked(value: str) -> bool:
    return isinstance(value, str) and value.startswith("****")


def _bot_to_dict(bot: ChannelBot) -> dict:
    creds = json.loads(bot.credentials) if bot.credentials else {}
    return {
        "id": bot.id,
        "channel_type": bot.channel_type,
        "member_id": bot.member_id,
        "credentials": _mask_credentials(bot.channel_type, creds),
        "status": bot.status,
        "last_test_at": bot.last_test_at.isoformat() if bot.last_test_at else None,
        "last_test_ok": bot.last_test_ok,
        "created_at": bot.created_at.isoformat() if bot.created_at else None,
    }


@router.get("")
async def list_channel_bots(member_id: str | None = None, channel_type: str | None = None):
    """List channel bots, optionally filtered by member or channel."""
    sf = get_db_session_factory()
    async with sf() as session:
        q = select(ChannelBot)
        if member_id:
            q = q.where(ChannelBot.member_id == member_id)
        if channel_type:
            q = q.where(ChannelBot.channel_type == channel_type)
        q = q.order_by(ChannelBot.created_at.desc())
        result = await session.execute(q)
        bots = result.scalars().all()
    return {"bots": [_bot_to_dict(b) for b in bots]}


@router.get("/credential-fields")
async def get_credential_fields():
    """Return per-channel bot credential field schemas for frontend form rendering."""
    return {"fields": BOT_CREDENTIAL_FIELDS}


@router.get("/summary")
async def channel_bot_summary():
    """Per-channel bot counts for the channels management page."""
    sf = get_db_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(ChannelBot.channel_type, func.count(ChannelBot.id))
            .where(ChannelBot.status == "active")
            .group_by(ChannelBot.channel_type)
        )
        rows = result.all()
    return {"counts": {row[0]: row[1] for row in rows}}


class CreateBotRequest(BaseModel):
    channel_type: str
    member_id: str
    credentials: dict = {}


@router.post("")
async def create_channel_bot(req: CreateBotRequest):
    """Bind a new IM bot to an AI employee."""
    if req.channel_type not in BOT_CREDENTIAL_FIELDS:
        raise HTTPException(400, f"Unsupported channel type: {req.channel_type}")

    sf = get_db_session_factory()
    async with sf() as session:
        existing = await session.execute(
            select(ChannelBot).where(
                ChannelBot.channel_type == req.channel_type,
                ChannelBot.member_id == req.member_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(409, "该员工已绑定此通道的 Bot")

        bot = ChannelBot(
            channel_type=req.channel_type,
            member_id=req.member_id,
            credentials=json.dumps(req.credentials),
            status="active",
        )
        session.add(bot)
        await session.commit()
        await session.refresh(bot)
    return {"success": True, "bot": _bot_to_dict(bot)}


class UpdateBotRequest(BaseModel):
    credentials: dict | None = None
    status: str | None = None


@router.put("/{bot_id}")
async def update_channel_bot(bot_id: str, req: UpdateBotRequest):
    """Update bot credentials or status."""
    sf = get_db_session_factory()
    async with sf() as session:
        result = await session.execute(select(ChannelBot).where(ChannelBot.id == bot_id))
        bot = result.scalar_one_or_none()
        if not bot:
            raise HTTPException(404, "Bot not found")

        if req.credentials is not None:
            existing_creds = json.loads(bot.credentials) if bot.credentials else {}
            schema = BOT_CREDENTIAL_FIELDS.get(bot.channel_type, [])
            secret_keys = {f["key"] for f in schema if f.get("secret")}
            merged = {}
            for key, value in req.credentials.items():
                if key in secret_keys and _is_masked(value):
                    merged[key] = existing_creds.get(key, "")
                else:
                    merged[key] = value
            bot.credentials = json.dumps({**existing_creds, **merged})

        if req.status is not None:
            bot.status = req.status

        await session.commit()
        await session.refresh(bot)
    return {"success": True, "bot": _bot_to_dict(bot)}


@router.delete("/{bot_id}")
async def delete_channel_bot(bot_id: str):
    """Unbind a bot from an AI employee."""
    sf = get_db_session_factory()
    async with sf() as session:
        result = await session.execute(select(ChannelBot).where(ChannelBot.id == bot_id))
        bot = result.scalar_one_or_none()
        if not bot:
            raise HTTPException(404, "Bot not found")
        await session.delete(bot)
        await session.commit()
    return {"success": True}


@router.post("/{bot_id}/test")
async def test_channel_bot(bot_id: str):
    """Test bot connectivity using stored credentials."""
    sf = get_db_session_factory()
    async with sf() as session:
        result = await session.execute(select(ChannelBot).where(ChannelBot.id == bot_id))
        bot = result.scalar_one_or_none()
        if not bot:
            raise HTTPException(404, "Bot not found")

        creds = json.loads(bot.credentials) if bot.credentials else {}
        channel_type = bot.channel_type

        test_result = {"ok": False, "message": "Unsupported channel type"}

        registry = get_registry()
        ch = registry.get_channel(channel_type)

        if channel_type == "wecom" and ch:
            try:
                import asyncio
                import websockets
                async with websockets.connect("wss://openws.work.weixin.qq.com", close_timeout=5) as ws:
                    from uuid import uuid4
                    auth_frame = {
                        "cmd": "aibot_subscribe",
                        "headers": {"req_id": str(uuid4())},
                        "body": {"secret": creds.get("bot_secret", ""), "bot_id": creds.get("bot_id", "")},
                    }
                    await ws.send(json.dumps(auth_frame))
                    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                    if resp.get("errcode", -1) == 0:
                        test_result = {"ok": True, "message": "Bot WebSocket 认证成功"}
                    else:
                        test_result = {"ok": False, "message": f"认证失败: {resp.get('errmsg', '未知错误')}"}
            except Exception as e:
                test_result = {"ok": False, "message": f"连接失败: {e}"}
        elif channel_type in ("dingtalk", "feishu") and ch:
            test_result = {"ok": True, "message": "凭证已保存（该通道暂不支持独立 Bot 连接测试）"}

        now = datetime.now(timezone.utc)
        bot.last_test_at = now
        bot.last_test_ok = test_result["ok"]
        await session.commit()

    return test_result
