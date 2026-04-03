"""通道管理路由"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from openvort.db.models import ChannelConfig
from openvort.web.deps import get_db_session_factory, get_registry

router = APIRouter()


# ---- 辅助函数 ----

async def _get_channel_config(channel_name: str) -> ChannelConfig | None:
    """从数据库获取通道配置记录"""
    session_factory = get_db_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(ChannelConfig).where(ChannelConfig.channel_name == channel_name)
        )
        return result.scalar_one_or_none()


def _is_masked(value: str) -> bool:
    """判断值是否为脱敏掩码"""
    return isinstance(value, str) and value.startswith("****")


# ---- 路由 ----

@router.get("")
async def list_channels():
    """列出所有已注册通道"""
    registry = get_registry()
    channels = registry.list_channels()

    result = []
    for ch in channels:
        db_config = await _get_channel_config(ch.name)
        enabled = db_config.enabled if db_config else True
        result.append({
            "name": ch.name,
            "display_name": ch.display_name,
            "description": ch.description,
            "type": ch.name,
            "status": "connected" if ch.is_configured() else "disconnected",
            "enabled": enabled,
        })

    return {"channels": result}


@router.get("/{name}")
async def get_channel_detail(name: str):
    """获取通道详情（含脱敏配置 + schema）"""
    registry = get_registry()
    ch = registry.get_channel(name)
    if not ch:
        raise HTTPException(status_code=404, detail=f"通道 '{name}' 不存在")

    db_config = await _get_channel_config(name)
    enabled = db_config.enabled if db_config else True

    return {
        "name": ch.name,
        "display_name": ch.display_name,
        "description": ch.description,
        "type": ch.name,
        "status": "connected" if ch.is_configured() else "disconnected",
        "enabled": enabled,
        "config_schema": ch.get_config_schema(),
        "config": ch.get_current_config(),
        "config_modes": ch.get_config_modes(),
        "connection": ch.get_connection_info(),
        "setup_guide": ch.get_setup_guide(),
        "setup_permissions": ch.get_setup_permissions(),
    }


class UpdateChannelRequest(BaseModel):
    config: dict = {}


@router.put("/{name}")
async def update_channel(name: str, req: UpdateChannelRequest):
    """更新通道配置（持久化到 DB，运行时生效）"""
    registry = get_registry()
    ch = registry.get_channel(name)
    if not ch:
        raise HTTPException(status_code=404, detail=f"通道 '{name}' 不存在")

    # 获取 schema 中标记为 secret 的字段
    schema = ch.get_config_schema()
    secret_keys = {f["key"] for f in schema if f.get("secret")}

    # 读取数据库中已有的原始配置
    db_config = await _get_channel_config(name)
    existing_raw = json.loads(db_config.config_data) if db_config and db_config.config_data else {}

    # 合并配置：secret 字段如果传入掩码值，保留原值
    merged = {}
    for key, value in req.config.items():
        if key in secret_keys and _is_masked(value):
            if key in existing_raw:
                merged[key] = existing_raw[key]
        else:
            merged[key] = value

    # 应用到 channel 运行时
    ch.apply_config(merged)

    # 持久化到数据库
    full_config = {**existing_raw, **merged}
    session_factory = get_db_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(ChannelConfig).where(ChannelConfig.channel_name == name)
        )
        config_row = result.scalar_one_or_none()
        if config_row is None:
            config_row = ChannelConfig(channel_name=name, config_data=json.dumps(full_config), enabled=True)
            session.add(config_row)
        else:
            config_row.config_data = json.dumps(full_config)
        await session.commit()

    return {"success": True}


@router.post("/{name}/toggle")
async def toggle_channel(name: str):
    """启用/禁用通道"""
    registry = get_registry()
    ch = registry.get_channel(name)
    if not ch:
        raise HTTPException(status_code=404, detail=f"通道 '{name}' 不存在")

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(ChannelConfig).where(ChannelConfig.channel_name == name)
        )
        config_row = result.scalar_one_or_none()
        if config_row is None:
            config_row = ChannelConfig(channel_name=name, config_data="{}", enabled=False)
            session.add(config_row)
        else:
            config_row.enabled = not config_row.enabled
        await session.commit()
        await session.refresh(config_row)
        new_enabled = config_row.enabled

    return {"success": True, "enabled": new_enabled}


@router.post("/{name}/test")
async def test_channel(name: str):
    """测试通道连通性"""
    registry = get_registry()
    ch = registry.get_channel(name)
    if not ch:
        raise HTTPException(status_code=404, detail=f"通道 '{name}' 不存在")

    result = await ch.test_connection()
    return result
