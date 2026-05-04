"""向量服务（Embedding）服务商管理路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openvort.services.embedding import EmbeddingService
from openvort.web.deps import get_db_session_factory, get_embedding_service

router = APIRouter()


class EmbeddingProviderCreateRequest(BaseModel):
    name: str
    platform: str
    api_key: str = ""
    config: dict = Field(default_factory=dict)
    is_default: bool = False


class EmbeddingProviderUpdateRequest(BaseModel):
    name: str | None = None
    api_key: str | None = None
    config: dict | None = None
    is_default: bool | None = None
    is_enabled: bool | None = None


async def _build_embedding_service() -> EmbeddingService:
    service = EmbeddingService(get_db_session_factory())
    await service.load_providers()
    return service


async def _reload_singleton():
    embedding_svc = get_embedding_service()
    if embedding_svc:
        await embedding_svc.load_providers()


@router.get("")
async def list_embedding_providers():
    """列出向量服务商"""
    service = await _build_embedding_service()
    try:
        providers = await service.list_providers()
        return {"providers": providers}
    finally:
        await service.close()


@router.post("")
async def create_embedding_provider(req: EmbeddingProviderCreateRequest):
    """创建向量服务商"""
    service = await _build_embedding_service()
    try:
        provider = await service.add_provider(
            name=req.name,
            platform=req.platform,
            api_key=req.api_key,
            config=req.config or {},
            is_default=req.is_default,
        )
        await _reload_singleton()
        return {"id": provider.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建向量服务商失败: {e}") from e
    finally:
        await service.close()


@router.put("/{provider_id}")
async def update_embedding_provider(provider_id: str, req: EmbeddingProviderUpdateRequest):
    """更新向量服务商"""
    service = await _build_embedding_service()
    try:
        provider = await service.update_provider(
            provider_id=provider_id,
            name=req.name,
            api_key=req.api_key,
            config=req.config,
            is_default=req.is_default,
            is_enabled=req.is_enabled,
        )
        if not provider:
            raise HTTPException(status_code=404, detail="向量服务商不存在")
        await _reload_singleton()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新向量服务商失败: {e}") from e
    finally:
        await service.close()


@router.delete("/{provider_id}")
async def delete_embedding_provider(provider_id: str):
    """删除向量服务商"""
    service = await _build_embedding_service()
    try:
        deleted = await service.delete_provider(provider_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="向量服务商不存在")
        await _reload_singleton()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"删除向量服务商失败: {e}") from e
    finally:
        await service.close()