"""插件管理路由"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from openvort.db.models import PluginConfig
from openvort.web.deps import get_db_session_factory, get_registry


router = APIRouter()


# ---- 辅助函数 ----

async def _get_plugin_config(plugin_name: str) -> PluginConfig | None:
    """从数据库获取插件配置记录"""
    session_factory = get_db_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(PluginConfig).where(PluginConfig.plugin_name == plugin_name)
        )
        return result.scalar_one_or_none()


def _is_masked(value: str) -> bool:
    """判断值是否为脱敏掩码"""
    return isinstance(value, str) and value.startswith("****")


# ---- 路由 ----

@router.get("")
async def list_plugins():
    registry = get_registry()
    plugins = registry.list_plugins()

    result = []
    for p in plugins:
        db_config = await _get_plugin_config(p.name)
        enabled = db_config.enabled if db_config else True
        tools = [{"name": t.name, "description": t.description} for t in p.get_tools()]
        result.append({
            "name": p.name,
            "display_name": p.display_name,
            "description": p.description,
            "version": p.version,
            "source": p.source,
            "core": p.core,
            "status": "ready",
            "enabled": enabled,
            "has_config": len(p.get_config_schema()) > 0,
            "tools": tools,
        })

    return {"plugins": result}


@router.get("/{name}")
async def get_plugin_detail(name: str):
    """获取插件详情（含脱敏配置 + schema）"""
    registry = get_registry()
    plugin = registry.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"插件 '{name}' 不存在")

    db_config = await _get_plugin_config(name)
    enabled = db_config.enabled if db_config else True
    tools = [{"name": t.name, "description": t.description} for t in plugin.get_tools()]

    return {
        "name": plugin.name,
        "display_name": plugin.display_name,
        "description": plugin.description,
        "version": plugin.version,
        "source": plugin.source,
        "core": plugin.core,
        "status": "ready",
        "enabled": enabled,
        "config_schema": plugin.get_config_schema(),
        "config": plugin.get_current_config(),
        "tools": tools,
    }


class UpdatePluginRequest(BaseModel):
    config: dict = {}


@router.put("/{name}")
async def update_plugin(name: str, req: UpdatePluginRequest):
    """更新插件配置（持久化到 DB，运行时生效）"""
    registry = get_registry()
    plugin = registry.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"插件 '{name}' 不存在")

    # 获取 schema 中标记为 secret 的字段
    schema = plugin.get_config_schema()
    secret_keys = {f["key"] for f in schema if f.get("secret")}

    # 读取数据库中已有的原始配置
    db_config = await _get_plugin_config(name)
    existing_raw = json.loads(db_config.config_data) if db_config and db_config.config_data else {}

    # 合并配置：secret 字段如果传入掩码值，保留原值
    merged = {}
    for key, value in req.config.items():
        if key in secret_keys and _is_masked(value):
            if key in existing_raw:
                merged[key] = existing_raw[key]
        else:
            merged[key] = value

    # 应用到 plugin 运行时
    plugin.apply_config(merged)

    # 持久化到数据库
    full_config = {**existing_raw, **merged}
    session_factory = get_db_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(PluginConfig).where(PluginConfig.plugin_name == name)
        )
        config_row = result.scalar_one_or_none()
        if config_row is None:
            config_row = PluginConfig(plugin_name=name, config_data=json.dumps(full_config), enabled=True)
            session.add(config_row)
        else:
            config_row.config_data = json.dumps(full_config)
        await session.commit()

    return {"success": True}


@router.post("/{name}/toggle")
async def toggle_plugin(name: str):
    """启用/禁用插件"""
    registry = get_registry()
    plugin = registry.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"插件 '{name}' 不存在")

    if plugin.core:
        raise HTTPException(status_code=400, detail=f"核心插件 '{name}' 不可禁用")

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(PluginConfig).where(PluginConfig.plugin_name == name)
        )
        config_row = result.scalar_one_or_none()
        if config_row is None:
            config_row = PluginConfig(plugin_name=name, config_data="{}", enabled=False)
            session.add(config_row)
        else:
            config_row.enabled = not config_row.enabled
        await session.commit()
        await session.refresh(config_row)
        new_enabled = config_row.enabled

    return {"success": True, "enabled": new_enabled, "restart_required": True}
