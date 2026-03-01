"""Webhook 管理路由（CRUD + 预置模板）"""

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.web.webhooks import (
    _webhooks, WebhookConfig, register_webhook,
    get_presets, get_preset,
)

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


@router.get("/presets")
async def list_presets():
    """列出所有 Webhook 预置模板（featured 排在前面）"""
    presets = get_presets()
    existing_names = set(_webhooks.keys())
    result = []
    for p in presets:
        result.append({
            **p,
            "installed": p["name"] in existing_names,
        })
    result.sort(key=lambda x: (not x.get("featured", False), x["id"]))
    return result


@router.get("/presets/{preset_id}")
async def get_preset_detail(preset_id: str):
    """获取指定预置模板的详细信息（含集成指南）"""
    preset = get_preset(preset_id)
    if not preset:
        return {"success": False, "error": f"预置模板 '{preset_id}' 不存在"}
    return {
        **preset,
        "installed": preset["name"] in _webhooks,
    }


@router.post("/presets/{preset_id}/install")
async def install_preset(preset_id: str, secret: str = ""):
    """一键安装预置模板 Webhook"""
    preset = get_preset(preset_id)
    if not preset:
        return {"success": False, "error": f"预置模板 '{preset_id}' 不存在"}

    name = preset["name"]
    if name in _webhooks:
        return {"success": False, "error": f"Webhook '{name}' 已存在"}

    cfg = preset["config"]
    config = WebhookConfig(
        name=name,
        secret=secret,
        action_type=cfg.get("action_type", "agent_chat"),
        prompt_template=cfg.get("prompt_template", ""),
        channel=cfg.get("channel", "webhook"),
        user_id=cfg.get("user_id", "webhook"),
    )
    register_webhook(config)
    return {"success": True, "name": name}


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
