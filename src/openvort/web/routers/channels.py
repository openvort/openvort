"""通道管理路由"""

import io
import json
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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
        "type": ch.name,
        "status": "connected" if ch.is_configured() else "disconnected",
        "enabled": enabled,
        "config_schema": ch.get_config_schema(),
        "config": ch.get_current_config(),
        "connection": ch.get_connection_info(),
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


@router.get("/{name}/deploy-package")
async def download_deploy_package(name: str):
    """下载 Relay 部署文件包（docker-compose + .env + README）"""
    registry = get_registry()
    ch = registry.get_channel(name)
    if not ch:
        raise HTTPException(status_code=404, detail=f"通道 '{name}' 不存在")

    # 获取当前配置用于预填模板
    config = ch.get_current_config() if hasattr(ch, "get_current_config") else {}

    corp_id = config.get("corp_id", "")
    agent_id = config.get("agent_id", "")

    docker_compose = f"""\
version: "3.8"

services:
  relay:
    image: python:3.11-slim
    container_name: openvort-relay
    restart: unless-stopped
    working_dir: /app
    volumes:
      - ./data:/app/data
    ports:
      - "${{RELAY_PORT:-8080}}:8080"
    env_file:
      - .env
    command: >
      bash -c "
        pip install openvort --quiet &&
        python -m openvort relay
          --port 8080
          --db-path /app/data/relay.db
      "
"""

    env_example = f"""\
# === 企业微信配置 ===
OPENVORT_WECOM_CORP_ID={corp_id}
OPENVORT_WECOM_APP_SECRET=<填写应用 Secret>
OPENVORT_WECOM_AGENT_ID={agent_id}
OPENVORT_WECOM_CALLBACK_TOKEN=<填写回调 Token>
OPENVORT_WECOM_CALLBACK_AES_KEY=<填写回调 EncodingAESKey>

# === Relay 配置 ===
OPENVORT_RELAY_SECRET=<自定义鉴权密钥>
RELAY_PORT=8080
"""

    readme = f"""\
# OpenVort Relay Server 部署指南

Relay Server 是一个轻量级的企微消息中继服务，部署在公网服务器上，
负责接收企微回调消息并转发给本地的 OpenVort 引擎。

## 快速部署

1. 将本目录上传到公网服务器

2. 复制并编辑环境变量：
   ```bash
   cp .env.example .env
   # 编辑 .env，填写企微凭证和 Relay 密钥
   ```

3. 启动服务：
   ```bash
   docker compose up -d
   ```

4. 在企微后台设置回调地址为：
   ```
   http://<你的服务器IP>:8080/callback/wecom
   ```

5. 在 OpenVort 本地启动时指定 relay 地址：
   ```bash
   openvort start --relay-url http://<你的服务器IP>:8080
   ```
   或在 .env 中设置：
   ```
   OPENVORT_RELAY_URL=http://<你的服务器IP>:8080
   OPENVORT_RELAY_SECRET=<与上面一致的密钥>
   ```

## 健康检查

```bash
curl http://<你的服务器IP>:8080/relay/health
```

## 数据持久化

消息数据存储在 `./data/relay.db`（SQLite），挂载为 Docker volume 确保重启不丢失。
"""

    # 生成 zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("openvort-relay/docker-compose.yml", docker_compose)
        zf.writestr("openvort-relay/.env.example", env_example)
        zf.writestr("openvort-relay/README.md", readme)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=openvort-relay-{name}.zip"},
    )
