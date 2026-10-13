"""
Web 面板 FastAPI 应用工厂
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import HTTPConnection
from starlette.responses import Response

from openvort.web.auth import verify_token
from openvort.utils.logging import get_logger

_log_app = get_logger("web.app")

DEMO_READONLY_ERROR = "演示账号无操作权限"


def _extract_payload(conn: HTTPConnection) -> dict | None:
    """Extract and verify JWT payload from request headers or query params."""
    auth = conn.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        token = conn.query_params.get("token", "")
    else:
        token = auth[7:]
    if not token:
        return None
    return verify_token(token)


def require_auth(conn: HTTPConnection) -> dict:
    """JWT 认证依赖 — 所有登录用户。WebSocket 端点自行鉴权，此处跳过。"""
    if conn.scope.get("type") == "websocket":
        return {}

    payload = _extract_payload(conn)
    if not payload:
        raise HTTPException(status_code=401, detail="未登录")
    return payload


def require_admin(conn: HTTPConnection) -> dict:
    """管理员权限依赖 — admin 或 demo（只读）角色。WebSocket 端点自行鉴权，此处跳过。"""
    if conn.scope.get("type") == "websocket":
        return {}

    payload = require_auth(conn)
    roles = payload.get("roles", [])
    if "admin" not in roles and "demo" not in roles:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return payload


def _setup_mcp(app: FastAPI) -> None:
    """Mount MCP Server as ASGI sub-app at /mcp for Cursor/Claude Desktop integration."""
    try:
        from openvort.web.deps import get_registry as _get_reg
        from openvort.web.mcp_server import create_mcp_server, McpAuthMiddleware

        registry = _get_reg()
        mcp = create_mcp_server(registry)
        mcp_asgi = McpAuthMiddleware(mcp.streamable_http_app())

        @asynccontextmanager
        async def _mcp_lifespan_ctx(a):
            async with mcp.session_manager.run():
                yield

        # Starlette sub-app lifespan won't fire automatically when mounted,
        # so we run the MCP session manager in a background task instead.
        @app.on_event("startup")
        async def _start_mcp_session_manager():
            import asyncio
            _sm = mcp.session_manager

            async def _run_sm():
                async with _sm.run():
                    # Block forever — keeps the session manager alive
                    await asyncio.Event().wait()

            asyncio.create_task(_run_sm())
            _log_app.info("MCP session manager started")

        app.mount("/mcp", mcp_asgi)

        from starlette.types import ASGIApp, Scope, Receive, Send

        class _MCPTrailingSlashMiddleware:
            """Rewrite /mcp → /mcp/ so Starlette Mount matches correctly for all HTTP methods."""

            def __init__(self, app: ASGIApp):
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send):
                if scope["type"] == "http" and scope.get("path") == "/mcp":
                    scope = dict(scope, path="/mcp/", raw_path=b"/mcp/")
                await self.app(scope, receive, send)

        app.add_middleware(_MCPTrailingSlashMiddleware)
        _log_app.info("MCP Server mounted at /mcp")
    except Exception as e:
        _log_app.warning(f"MCP Server setup failed: {e}")


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

    class NoCacheAPIMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response: Response = await call_next(request)
            if request.url.path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
                response.headers["Pragma"] = "no-cache"
            return response

    app.add_middleware(NoCacheAPIMiddleware)

    _DEMO_WRITE_WHITELIST = {"/api/auth/login"}

    class DemoReadonlyMiddleware(BaseHTTPMiddleware):
        """Block non-GET API requests for demo users."""

        async def dispatch(self, request: Request, call_next):
            if (
                request.method not in ("GET", "HEAD", "OPTIONS")
                and request.url.path.startswith("/api/")
                and request.url.path not in _DEMO_WRITE_WHITELIST
            ):
                payload = _extract_payload(request)
                if payload and "demo" in payload.get("roles", []):
                    from starlette.responses import JSONResponse
                    return JSONResponse(
                        status_code=403,
                        content={"detail": DEMO_READONLY_ERROR},
                    )
            return await call_next(request)

    app.add_middleware(DemoReadonlyMiddleware)

    _member_exists_cache: dict[str, float] = {}
    _MEMBER_CACHE_TTL = 300  # 5 min

    _AUTH_SKIP_PREFIXES = ("/api/auth/", "/api/health", "/api/webhooks/")

    class MemberVerifyMiddleware(BaseHTTPMiddleware):
        """Reject requests whose JWT member_id no longer exists in DB (e.g. after DB switch)."""

        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            if not path.startswith("/api/") or any(path.startswith(p) for p in _AUTH_SKIP_PREFIXES):
                return await call_next(request)

            payload = _extract_payload(request)
            if not payload:
                return await call_next(request)

            member_id = payload.get("sub", "")
            if not member_id:
                return await call_next(request)

            import time as _t
            now = _t.time()
            if member_id in _member_exists_cache and now - _member_exists_cache[member_id] < _MEMBER_CACHE_TTL:
                return await call_next(request)

            try:
                from openvort.contacts.models import Member
                from openvort.web.deps import get_db_session_factory
                sf = get_db_session_factory()
                async with sf() as session:
                    m = await session.get(Member, member_id)
                    if not m or m.status != "active":
                        _member_exists_cache.pop(member_id, None)
                        from starlette.responses import JSONResponse
                        return JSONResponse(status_code=401, content={"detail": "账号不存在或已停用，请重新登录"})
                _member_exists_cache[member_id] = now
            except Exception:
                pass

            return await call_next(request)

    app.add_middleware(MemberVerifyMiddleware)

    # 注册路由
    from openvort.web.routers import (
        auth_router, chat_router, dashboard_router, me_router,
        contacts_router, members_router, departments_router, reporting_router, org_calendar_router,
        plugins_router, skills_router, channels_router,
        settings_router, logs_router, schedules_router, admin_schedules_router,
        webhooks_admin_router, agents_router, models_router,
        member_skills_router, upgrade_router, posts_router,
        work_assignments_router, voice_providers_router,
        embedding_providers_router,
        remote_nodes_router, marketplace_router,
        jenkins_router, channel_bots_router,
        members_public_router,
    )
    from openvort.web.ws import ws_router
    from openvort.web.webhooks import webhooks_router

    # WebSocket（无需 JWT 依赖，内部自行认证）
    app.include_router(ws_router, prefix="/api", tags=["websocket"])

    # Webhook 触发器（外部系统回调，自行验证签名）
    app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])

    # 公开路由
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

    # 登录用户可访问
    app.include_router(chat_router, prefix="/api/chat", tags=["chat"], dependencies=[Depends(require_auth)])

    from openvort.web.routers.notifications import router as notifications_router
    app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"], dependencies=[Depends(require_auth)])

    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_auth)])
    app.include_router(me_router, prefix="/api/me", tags=["me"], dependencies=[Depends(require_auth)])
    app.include_router(schedules_router, prefix="/api/schedules", tags=["schedules"], dependencies=[Depends(require_auth)])
    app.include_router(member_skills_router, prefix="/api/skills", tags=["skills"], dependencies=[Depends(require_auth)])
    app.include_router(members_public_router, prefix="/api/members", tags=["members"], dependencies=[Depends(require_auth)])

    # 仅管理员可访问
    app.include_router(contacts_router, prefix="/api/admin/contacts", tags=["admin-contacts"], dependencies=[Depends(require_admin)])
    app.include_router(members_router, prefix="/api/admin/members", tags=["admin-members"], dependencies=[Depends(require_admin)])
    app.include_router(departments_router, prefix="/api/admin/departments", tags=["admin-departments"], dependencies=[Depends(require_admin)])
    app.include_router(reporting_router, prefix="/api/admin/reporting-relations", tags=["admin-reporting"], dependencies=[Depends(require_admin)])
    app.include_router(org_calendar_router, prefix="/api/admin/org-calendar", tags=["admin-org-calendar"], dependencies=[Depends(require_admin)])
    app.include_router(plugins_router, prefix="/api/admin/plugins", tags=["admin-plugins"], dependencies=[Depends(require_admin)])
    app.include_router(skills_router, prefix="/api/admin/skills", tags=["admin-skills"], dependencies=[Depends(require_admin)])
    # 岗位管理（AI 员工岗位）
    app.include_router(posts_router, prefix="/api/posts", tags=["posts"], dependencies=[Depends(require_auth)])
    app.include_router(work_assignments_router, prefix="/api/work-assignments", tags=["work-assignments"], dependencies=[Depends(require_auth)])
    app.include_router(channels_router, prefix="/api/admin/channels", tags=["admin-channels"], dependencies=[Depends(require_admin)])
    app.include_router(settings_router, prefix="/api/admin/settings", tags=["admin-settings"], dependencies=[Depends(require_admin)])
    app.include_router(logs_router, prefix="/api/admin/logs", tags=["admin-logs"], dependencies=[Depends(require_admin)])
    app.include_router(admin_schedules_router, prefix="/api/admin/schedules", tags=["admin-schedules"], dependencies=[Depends(require_admin)])
    app.include_router(webhooks_admin_router, prefix="/api/admin/webhooks", tags=["admin-webhooks"], dependencies=[Depends(require_admin)])
    app.include_router(agents_router, prefix="/api/admin/agents", tags=["admin-agents"], dependencies=[Depends(require_admin)])
    app.include_router(models_router, prefix="/api/admin/models", tags=["admin-models"], dependencies=[Depends(require_admin)])
    app.include_router(voice_providers_router, prefix="/api/admin/voice-providers", tags=["admin-voice-providers"], dependencies=[Depends(require_admin)])
    app.include_router(embedding_providers_router, prefix="/api/admin/embedding-providers", tags=["admin-embedding-providers"], dependencies=[Depends(require_admin)])
    app.include_router(upgrade_router, prefix="/api/admin/upgrade", tags=["admin-upgrade"], dependencies=[Depends(require_admin)])
    app.include_router(remote_nodes_router, prefix="/api/admin/remote-nodes", tags=["admin-remote-nodes"], dependencies=[Depends(require_admin)])
    app.include_router(marketplace_router, prefix="/api/admin/marketplace", tags=["admin-marketplace"], dependencies=[Depends(require_admin)])

    # Platform standard API (Slot-backed, for plugins to access core data)
    from openvort.web.routers.platform import router as platform_router
    app.include_router(platform_router, prefix="/api/platform", tags=["platform"], dependencies=[Depends(require_auth)])

    # 通用文件上传（登录用户可访问）
    from openvort.web.routers.uploads import router as uploads_router
    app.include_router(uploads_router, prefix="/api/uploads", tags=["uploads"], dependencies=[Depends(require_auth)])

    # Jenkins 管理（登录用户可访问，内部按角色区分管理员操作）
    app.include_router(jenkins_router, prefix="/api/jenkins", tags=["jenkins"], dependencies=[Depends(require_auth)])

    # Channel Bots — AI 员工独立 IM Bot 管理
    app.include_router(channel_bots_router, prefix="/api/admin/channel-bots", tags=["admin-channel-bots"], dependencies=[Depends(require_admin)])

    # ---- 动态挂载已启用插件的 API Router ----
    try:
        from openvort.web.deps import get_registry as _get_registry
        from openvort.utils.logging import get_logger
        _log = get_logger("web.app")
        registry = _get_registry()
        for plugin in registry.list_plugins():
            try:
                router = plugin.get_api_router()
                if router is not None:
                    app.include_router(router, dependencies=[Depends(require_auth)])
                    _log.info(f"已挂载插件 API Router: {plugin.name}")
            except Exception as e:
                _log.warning(f"挂载插件 '{plugin.name}' API Router 失败: {e}")
    except Exception:
        pass

    # ---- MCP Server（Cursor / Claude Desktop 集成） ----
    _setup_mcp(app)

    # ---- 健康检查（公开，无需认证） ----
    import time as _time
    from openvort.core.services.updater import get_update_service as _get_update_svc
    _llm_health_cache: dict[str, object] = {"healthy": None, "checked_at": 0.0, "error": ""}

    @app.get("/api/health")
    async def health_check(force: bool = False):
        from openvort import __version__
        from openvort.web.deps import get_config_service as _get_cs

        now = _time.monotonic()
        cache_ttl = 60

        # Use cached result if fresh (within 60s) and not forced
        if not force and _llm_health_cache["healthy"] is not None and (now - _llm_health_cache["checked_at"]) < cache_ttl:
            update_info: dict = {}
            if _get_settings().web.auto_check_update:
                try:
                    update_info = await _get_update_svc().check_update()
                except Exception:
                    pass
            return {
                "version": __version__,
                "llm_healthy": _llm_health_cache["healthy"],
                "llm_model": _llm_health_cache.get("model", ""),
                "llm_error": _llm_health_cache["error"],
                "update_available": update_info.get("update_available", False),
                "latest_version": update_info.get("latest_version", ""),
                "release_notes": update_info.get("release_notes", ""),
            }

        # Get primary model from model library
        try:
            config_service = _get_cs()
            chain = await config_service.get_effective_llm_chain()
        except Exception:
            chain = []

        if not chain:
            _llm_health_cache.update(healthy=False, checked_at=now, error="未配置主模型，请在模型管理中添加并在系统设置中选择", model="")
            up = {}
            if _get_settings().web.auto_check_update:
                try:
                    up = await _get_update_svc().check_update()
                except Exception:
                    pass
            return {
                "version": __version__,
                "llm_healthy": False,
                "llm_model": "",
                "llm_error": _llm_health_cache["error"],
                "update_available": up.get("update_available", False),
                "latest_version": up.get("latest_version", ""),
                "release_notes": up.get("release_notes", ""),
            }

        primary = chain[0]
        llm_model = primary.get("model", "")

        # Actually ping the LLM API with a minimal request
        try:
            from openvort.core.engine.llm import create_provider
            provider = create_provider(
                provider=primary.get("provider", "anthropic"),
                api_key=primary.get("api_key", ""),
                api_base=primary.get("api_base", ""),
                timeout=10,
                api_format=primary.get("api_format", "auto"),
            )
            resp = await provider.create(
                model=llm_model,
                max_tokens=1,
                system="Reply with OK.",
                messages=[{"role": "user", "content": "hi"}],
            )
            await provider.close()
            _llm_health_cache.update(healthy=True, checked_at=now, error="", model=llm_model)
        except Exception as e:
            _llm_health_cache.update(healthy=False, checked_at=now, error=str(e)[:200], model=llm_model)

        # Piggyback update check (uses its own cache, non-blocking)
        # Only check if auto_check_update is enabled
        update_info: dict = {}
        if _get_settings().web.auto_check_update:
            try:
                update_info = await _get_update_svc().check_update()
            except Exception:
                pass

        return {
            "version": __version__,
            "llm_healthy": _llm_health_cache["healthy"],
            "llm_model": llm_model,
            "llm_error": _llm_health_cache["error"],
            "update_available": update_info.get("update_available", False),
            "latest_version": update_info.get("latest_version", ""),
            "release_notes": update_info.get("release_notes", ""),
        }

    # 上传文件统一放在 data_dir 下，避免依赖前端 dist 目录是否存在
    from openvort.config.settings import get_settings as _get_settings
    _uploads_root = _get_settings().data_dir / "uploads"
    _uploads_root.mkdir(parents=True, exist_ok=True)

    _chat_uploads = _uploads_root / "chat"
    _chat_uploads.mkdir(parents=True, exist_ok=True)
    _editor_uploads = _uploads_root / "editor"
    _editor_uploads.mkdir(parents=True, exist_ok=True)
    _mcp_uploads = _uploads_root / "mcp"
    _mcp_uploads.mkdir(parents=True, exist_ok=True)
    _vortflow_uploads = _uploads_root / "vortflow"
    _vortflow_uploads.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads/chat", StaticFiles(directory=str(_chat_uploads)), name="chat-uploads")
    app.mount("/uploads/editor", StaticFiles(directory=str(_editor_uploads)), name="editor-uploads")
    app.mount("/uploads/mcp", StaticFiles(directory=str(_mcp_uploads)), name="mcp-uploads")
    app.mount("/uploads/vortflow", StaticFiles(directory=str(_vortflow_uploads)), name="vortflow-uploads")
    app.mount("/uploads", StaticFiles(directory=str(_uploads_root)), name="uploads")

    # 尝试挂载前端静态文件（构建产物）+ SPA fallback
    import os as _os
    _static_override = _os.environ.get("OPENVORT_STATIC_DIR")
    if _static_override:
        static_dir = Path(_static_override)
    elif Path("/app/web/dist").exists():
        static_dir = Path("/app/web/dist")
    else:
        static_dir = Path(__file__).parent.parent.parent.parent / "web" / "dist"
    if not (static_dir / "index.html").exists():
        _frontend_fallback = _get_settings().data_dir / "frontend"
        if (_frontend_fallback / "index.html").exists():
            static_dir = _frontend_fallback
    if static_dir.exists() and (static_dir / "index.html").exists():
        from fastapi.responses import FileResponse

        # 静态资源（js/css/svg 等）
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        # SPA fallback：非 /api 开头的请求都返回 index.html
        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(static_dir / "index.html"))

    return app
