"""
Web 面板 FastAPI 应用工厂
"""

from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from openvort.web.auth import verify_token


def require_auth(request: Request) -> dict:
    """JWT 认证依赖 — 所有登录用户"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        token = request.query_params.get("token", "")
    else:
        token = auth[7:]

    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    return payload


def require_admin(request: Request) -> dict:
    """管理员权限依赖 — 仅 admin 角色"""
    payload = require_auth(request)
    roles = payload.get("roles", [])
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return payload


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(title="OpenVort", docs_url="/api/docs", openapi_url="/api/openapi.json")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from openvort.web.routers import (
        auth_router, chat_router, dashboard_router, me_router,
        contacts_router, members_router, departments_router, plugins_router, skills_router, channels_router,
        settings_router, logs_router, schedules_router, admin_schedules_router,
        webhooks_admin_router, agents_router, models_router,
    )
    from openvort.web.ws import ws_router
    from openvort.web.webhooks import webhooks_router

    # WebSocket（无需 JWT 依赖，内部自行认证）
    app.include_router(ws_router, tags=["websocket"])

    # Webhook 触发器（外部系统回调，自行验证签名）
    app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])

    # 公开路由
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

    # 登录用户可访问
    app.include_router(chat_router, prefix="/api/chat", tags=["chat"], dependencies=[Depends(require_auth)])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_auth)])
    app.include_router(me_router, prefix="/api/me", tags=["me"], dependencies=[Depends(require_auth)])
    app.include_router(schedules_router, prefix="/api/schedules", tags=["schedules"], dependencies=[Depends(require_auth)])

    # 仅管理员可访问
    app.include_router(contacts_router, prefix="/api/admin/contacts", tags=["admin-contacts"], dependencies=[Depends(require_admin)])
    app.include_router(members_router, prefix="/api/admin/members", tags=["admin-members"], dependencies=[Depends(require_admin)])
    app.include_router(departments_router, prefix="/api/admin/departments", tags=["admin-departments"], dependencies=[Depends(require_admin)])
    app.include_router(plugins_router, prefix="/api/admin/plugins", tags=["admin-plugins"], dependencies=[Depends(require_admin)])
    app.include_router(skills_router, prefix="/api/admin/skills", tags=["admin-skills"], dependencies=[Depends(require_admin)])
    app.include_router(channels_router, prefix="/api/admin/channels", tags=["admin-channels"], dependencies=[Depends(require_admin)])
    app.include_router(settings_router, prefix="/api/admin/settings", tags=["admin-settings"], dependencies=[Depends(require_admin)])
    app.include_router(logs_router, prefix="/api/admin/logs", tags=["admin-logs"], dependencies=[Depends(require_admin)])
    app.include_router(admin_schedules_router, prefix="/api/admin/schedules", tags=["admin-schedules"], dependencies=[Depends(require_admin)])
    app.include_router(webhooks_admin_router, prefix="/api/admin/webhooks", tags=["admin-webhooks"], dependencies=[Depends(require_admin)])
    app.include_router(agents_router, prefix="/api/admin/agents", tags=["admin-agents"], dependencies=[Depends(require_admin)])
    app.include_router(models_router, prefix="/api/admin/models", tags=["admin-models"], dependencies=[Depends(require_admin)])

    # ---- 健康检查（公开，无需认证） ----
    @app.get("/api/health")
    async def health_check():
        from openvort import __version__
        from openvort.config.settings import get_settings

        settings = get_settings()
        llm_model = settings.llm.model
        llm_healthy = bool(settings.llm.api_key and settings.llm.model)

        return {
            "version": __version__,
            "llm_healthy": llm_healthy,
            "llm_model": llm_model,
        }

    # 尝试挂载前端静态文件（构建产物）+ SPA fallback
    static_dir = Path(__file__).parent.parent.parent.parent / "web" / "dist"
    if static_dir.exists():
        from fastapi.responses import FileResponse

        # 静态资源（js/css/svg 等）
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        # 上传文件目录
        uploads_dir = static_dir / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

        # SPA fallback：非 /api 开头的请求都返回 index.html
        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(static_dir / "index.html"))

    return app
