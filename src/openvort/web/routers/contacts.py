"""联系人路由"""

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.web.deps import get_db_session_factory

router = APIRouter()


def _get_service(with_settings: bool = False):
    from openvort.contacts.service import ContactService

    session_factory = get_db_session_factory()
    if with_settings:
        from openvort.config.settings import get_settings
        settings = get_settings()
        return ContactService(session_factory, settings.contacts.auto_match_threshold)
    return ContactService(session_factory)


@router.get("")
async def list_contacts():
    try:
        service = _get_service()
        members = await service.list_members(status="active")

        contacts = []
        for m in members:
            identities = await service.get_member_identities(m.id)
            platform_accounts = {i.platform: i.platform_user_id for i in identities}
            contacts.append({
                "id": m.id,
                "name": m.name,
                "email": m.email or "",
                "phone": m.phone or "",
                "platform_accounts": platform_accounts,
                "roles": [],
            })
        return {"contacts": contacts}
    except Exception:
        return {"contacts": []}


@router.post("/sync")
async def sync_contacts(channel: str | None = None):
    try:
        from openvort.web.deps import get_registry
        from openvort.web.routers.channels import _get_channel_config

        service = _get_service(with_settings=True)
        registry = get_registry()

        providers = []
        for ch in registry.list_channels():
            if channel and ch.name != channel:
                continue
            if not channel:
                db_cfg = await _get_channel_config(ch.name)
                if db_cfg and not db_cfg.enabled:
                    continue
            p = ch.get_sync_provider()
            if p:
                providers.append(p)

        results = []
        for provider in providers:
            try:
                stats = await service.sync_from_provider(provider)
            except Exception as e:
                stats = {"created": 0, "updated": 0, "matched": 0, "pending": 0,
                         "errors": [str(e)]}
            results.append({"platform": provider.platform, **stats})

        return {"success": True, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/suggestions")
async def list_suggestions():
    """获取待确认的匹配建议列表"""
    try:
        service = _get_service()
        suggestions = await service.list_pending_suggestions()
        items = []
        for s in suggestions:
            source = s.source_identity
            target = s.target_member
            items.append({
                "id": s.id,
                "source_member_id": source.member_id if source else "",
                "source_name": source.platform_display_name if source else "",
                "source_platform": source.platform if source else "",
                "target_member_id": s.target_member_id,
                "target_name": target.name if target else "",
                "match_type": s.match_type,
                "confidence": s.confidence,
            })
        return {"suggestions": items}
    except Exception:
        return {"suggestions": []}


@router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(suggestion_id: int):
    """接受匹配建议，合并成员"""
    service = _get_service()
    ok = await service.accept_suggestion(suggestion_id)
    return {"success": ok}


@router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(suggestion_id: int):
    """拒绝匹配建议"""
    service = _get_service()
    ok = await service.reject_suggestion(suggestion_id)
    return {"success": ok}


class MergeRequest(BaseModel):
    source_id: str
    target_id: str


@router.post("/merge")
async def merge_members(req: MergeRequest):
    """手动合并两个成员"""
    service = _get_service()
    ok = await service.merge_members(req.source_id, req.target_id)
    return {"success": ok}


@router.post("/dedup")
async def dedup_contacts():
    """扫描同名成员，自动合并"""
    try:
        service = _get_service()
        stats = await service.dedup_members()
        return {"success": True, **stats}
    except Exception as e:
        return {"success": False, "error": str(e)}
