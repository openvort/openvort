"""Webhook 管理路由（CRUD）"""

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.web.webhooks import _webhooks, WebhookConfig, register_webhook

router = APIRouter()


class WebhookItem(BaseModel):
    name: str
    secret: str = ""
    action_type: str = "agent_chat"
    prompt_template: str = ""
    channel: str = "webhook"
    user_id: str = "webhook"


@router.get("")
async def list_webhooks():
    """列出所有已注册的 Webhook"""
    return [
        {
            "name": w.name,
            "secret": "***" if w.secret else "",
            "action_type": w.action_type,
            "prompt_template": w.prompt_template,
            "channel": w.channel,
            "user_id": w.user_id,
        }
        for w in _webhooks.values()
    ]


@router.post("")
async def create_webhook(req: WebhookItem):
    """创建 Webhook"""
    if req.name in _webhooks:
        return {"success": False, "error": f"Webhook '{req.name}' 已存在"}
    config = WebhookConfig(
        name=req.name, secret=req.secret, action_type=req.action_type,
        prompt_template=req.prompt_template, channel=req.channel, user_id=req.user_id,
    )
    register_webhook(config)
    return {"success": True}


@router.put("/{name}")
async def update_webhook(name: str, req: WebhookItem):
    """更新 Webhook"""
    if name not in _webhooks:
        return {"success": False, "error": f"Webhook '{name}' 不存在"}
    config = WebhookConfig(
        name=req.name, secret=req.secret, action_type=req.action_type,
        prompt_template=req.prompt_template, channel=req.channel, user_id=req.user_id,
    )
    # 如果改名了，删除旧的
    if name != req.name:
        _webhooks.pop(name, None)
    _webhooks[req.name] = config
    return {"success": True}


@router.delete("/{name}")
async def delete_webhook(name: str):
    """删除 Webhook"""
    if name not in _webhooks:
        return {"success": False, "error": f"Webhook '{name}' 不存在"}
    _webhooks.pop(name)
    return {"success": True}
