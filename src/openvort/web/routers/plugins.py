"""插件管理路由"""

import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from openvort.db.models import PluginConfig
from openvort.utils.logging import get_logger
from openvort.web.deps import get_db_session_factory, get_registry

log = get_logger("web.plugins")

router = APIRouter()

# 包名白名单正则：字母、数字、-、_、.
_VALID_PACKAGE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


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


def _get_plugins_dir() -> Path:
    """获取本地插件目录"""
    from openvort.config.settings import get_settings
    plugins_dir = get_settings().data_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    return plugins_dir


class InstallPluginRequest(BaseModel):
    package_name: str


@router.post("/install")
async def install_plugin(req: InstallPluginRequest):
    """通过 pip 安装插件包"""
    name = req.package_name.strip()
    if not name or not _VALID_PACKAGE_RE.match(name):
        raise HTTPException(status_code=400, detail="无效的包名，只允许字母、数字、-、_、.")

    try:
        result = subprocess.run(
            ["pip", "install", name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            log.warning(f"pip install {name} 失败: {result.stderr}")
            raise HTTPException(status_code=400, detail=f"安装失败: {result.stderr.strip()[-200:]}")

        log.info(f"pip install {name} 成功")
        return {"success": True, "message": f"'{name}' 安装成功，重启后生效", "restart_required": True}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="安装超时，请检查网络")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"安装异常: {e}")


@router.post("/upload")
async def upload_plugin(file: UploadFile):
    """上传 zip 格式的本地插件"""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 文件")

    # 读取并检查大小
    content = await file.read()
    if len(content) > _MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大，最大 {_MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    # 验证 zip 格式
    import io
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 zip 文件")

    # 路径遍历检查
    for name in zf.namelist():
        if name.startswith("/") or ".." in name:
            raise HTTPException(status_code=400, detail=f"zip 中包含不安全路径: {name}")

    # 查找 plugin.py
    plugin_files = [n for n in zf.namelist() if n.endswith("plugin.py")]
    if not plugin_files:
        raise HTTPException(status_code=400, detail="zip 中未找到 plugin.py，请确认插件结构")

    # 推断插件目录名（取 zip 中第一级目录，或用文件名）
    top_dirs = {n.split("/")[0] for n in zf.namelist() if "/" in n}
    if len(top_dirs) == 1:
        plugin_dir_name = top_dirs.pop()
    else:
        plugin_dir_name = file.filename.replace(".zip", "")

    plugins_dir = _get_plugins_dir()
    target_dir = plugins_dir / plugin_dir_name

    # 如果已存在，先删除旧版
    if target_dir.exists():
        shutil.rmtree(target_dir)

    # 解压
    zf.extractall(plugins_dir)
    log.info(f"插件上传成功: {plugin_dir_name} -> {target_dir}")

    return {"success": True, "message": f"插件 '{plugin_dir_name}' 上传成功，重启后生效", "restart_required": True}


@router.get("/ui-extensions")
async def get_ui_extensions():
    """聚合所有已启用插件的 UI 扩展声明"""
    registry = get_registry()
    extensions = []
    for plugin in registry.list_plugins():
        if registry.is_plugin_disabled(plugin.name):
            continue
        try:
            ui_ext = plugin.get_ui_extensions()
            if ui_ext:
                extensions.append({
                    "plugin": plugin.name,
                    "display_name": plugin.display_name,
                    **ui_ext,
                })
        except Exception as e:
            log.warning(f"获取插件 '{plugin.name}' UI 扩展失败: {e}")
    return {"extensions": extensions}


# ---- 以下为 /{name} 路径参数路由，必须放在固定路径之后 ----

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
    """启用/禁用插件（立即生效：注册/移除 Tools 和 Prompts）"""
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

    if new_enabled:
        registry.enable_plugin(name)
    else:
        registry.disable_plugin(name)

    return {"success": True, "enabled": new_enabled, "restart_required": False}


@router.delete("/{name}")
async def delete_plugin(name: str):
    """删除本地插件"""
    registry = get_registry()
    plugin = registry.get_plugin(name)

    if plugin and plugin.core:
        raise HTTPException(status_code=400, detail="核心插件不可删除")

    if plugin and plugin.source != "local":
        raise HTTPException(status_code=400, detail=f"只能删除本地插件，'{name}' 来源为 {plugin.source}")

    # 删除本地目录
    plugins_dir = _get_plugins_dir()
    target_dir = plugins_dir / name
    if target_dir.exists():
        shutil.rmtree(target_dir)
        log.info(f"已删除本地插件目录: {target_dir}")
    else:
        raise HTTPException(status_code=404, detail=f"本地插件目录 '{name}' 不存在")

    # 清理 DB 配置
    session_factory = get_db_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(PluginConfig).where(PluginConfig.plugin_name == name)
        )
        config_row = result.scalar_one_or_none()
        if config_row:
            await session.delete(config_row)
            await session.commit()

    return {"success": True, "message": f"插件 '{name}' 已删除，重启后生效", "restart_required": True}
