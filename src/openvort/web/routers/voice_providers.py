"""语音服务商管理路由（当前用于 ASR）"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openvort.services.asr import ASRService
from openvort.web.deps import get_db_session_factory

router = APIRouter()


class VoiceProviderCreateRequest(BaseModel):
    name: str
    platform: str
    api_key: str = ""
    config: dict = Field(default_factory=dict)
    is_default: bool = False


class VoiceProviderUpdateRequest(BaseModel):
    name: str | None = None
    api_key: str | None = None
    config: dict | None = None
    is_default: bool | None = None
    is_enabled: bool | None = None


async def _build_asr_service() -> ASRService:
    service = ASRService(get_db_session_factory())
    await service.load_providers()
    return service


@router.get("")
async def list_voice_providers():
    """列出语音服务商（ASR）"""
    asr_service = await _build_asr_service()
    try:
        providers = await asr_service.list_providers()
        return {"providers": providers}
    finally:
        await asr_service.close()


@router.post("")
async def create_voice_provider(req: VoiceProviderCreateRequest):
    """创建语音服务商（ASR）"""
    asr_service = await _build_asr_service()
    try:
        provider = await asr_service.add_provider(
            name=req.name,
            platform=req.platform,
            api_key=req.api_key,
            config=req.config or {},
            is_default=req.is_default,
        )
        return {"id": provider.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建语音服务商失败: {e}") from e
    finally:
        await asr_service.close()


@router.put("/{provider_id}")
async def update_voice_provider(provider_id: str, req: VoiceProviderUpdateRequest):
    """更新语音服务商（ASR）"""
    asr_service = await _build_asr_service()
    try:
        provider = await asr_service.update_provider(
            provider_id=provider_id,
            name=req.name,
            api_key=req.api_key,
            config=req.config,
            is_default=req.is_default,
            is_enabled=req.is_enabled,
        )
        if not provider:
            raise HTTPException(status_code=404, detail="语音服务商不存在")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新语音服务商失败: {e}") from e
    finally:
        await asr_service.close()


@router.delete("/{provider_id}")
async def delete_voice_provider(provider_id: str):
    """删除语音服务商（ASR）"""
    asr_service = await _build_asr_service()
    try:
        deleted = await asr_service.delete_provider(provider_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="语音服务商不存在")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"删除语音服务商失败: {e}") from e
    finally:
        await asr_service.close()
