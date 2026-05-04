"""Embedding service manager — loads providers from DB, supports CRUD."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select, update

from openvort.db.models import VoiceProvider
from openvort.services.embedding.providers.base import EmbeddingProviderBase
from openvort.services.embedding.providers.dashscope import DashScopeEmbeddingProvider
from openvort.utils.logging import get_logger

log = get_logger("services.embedding")

PROVIDER_CLASSES: dict[str, type[EmbeddingProviderBase]] = {
    "aliyun": DashScopeEmbeddingProvider,
    "dashscope": DashScopeEmbeddingProvider,
}


def _safe_json_loads(value: str | dict | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _safe_json_dumps(value: dict | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}***{value[-3:]}"


class EmbeddingService:
    """Embedding service backed by voice_providers table (service_type='embedding')."""

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._providers: dict[str, EmbeddingProviderBase] = {}
        self._default_provider_id: str = ""

    async def close(self) -> None:
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception:
                pass
        self._providers.clear()
        self._default_provider_id = ""

    async def load_providers(self) -> None:
        """Load all enabled embedding providers from DB."""
        await self.close()

        async with self._session_factory() as session:
            stmt = (
                select(VoiceProvider)
                .where(VoiceProvider.service_type == "embedding")
                .where(VoiceProvider.is_enabled.is_(True))
                .order_by(VoiceProvider.is_default.desc(), VoiceProvider.updated_at.desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        for row in rows:
            config = _safe_json_loads(row.config)
            provider_class = PROVIDER_CLASSES.get(row.platform)
            if not provider_class:
                log.warning(f"未知的 Embedding Provider 平台: {row.platform}")
                continue
            try:
                api_key = self._decrypt_secret(row.api_key)
                instance = provider_class(api_key=api_key, config=config)
                self._providers[row.id] = instance
                if row.is_default and not self._default_provider_id:
                    self._default_provider_id = row.id
            except Exception as e:
                log.error(f"加载 Embedding Provider 失败: {row.name}, error: {e}")

        if not self._default_provider_id and self._providers:
            self._default_provider_id = next(iter(self._providers.keys()))

        log.info(f"已加载 {len(self._providers)} 个 Embedding Provider")

    # ---- CRUD ----

    async def list_providers(self) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = (
                select(VoiceProvider)
                .where(VoiceProvider.service_type == "embedding")
                .order_by(VoiceProvider.is_default.desc(), VoiceProvider.updated_at.desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "platform": row.platform,
                    "service_type": row.service_type,
                    "api_key_masked": _mask_secret(self._decrypt_secret(row.api_key)),
                    "config": _safe_json_loads(row.config),
                    "is_default": bool(row.is_default),
                    "is_enabled": bool(row.is_enabled),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ]

    async def add_provider(
        self,
        *,
        name: str,
        platform: str,
        api_key: str = "",
        config: dict | None = None,
        is_default: bool = False,
    ) -> VoiceProvider:
        async with self._session_factory() as session:
            if is_default:
                await session.execute(
                    update(VoiceProvider)
                    .where(VoiceProvider.service_type == "embedding")
                    .values(is_default=False)
                )
            else:
                existing_default = await session.execute(
                    select(VoiceProvider.id)
                    .where(VoiceProvider.service_type == "embedding")
                    .where(VoiceProvider.is_default.is_(True))
                    .limit(1)
                )
                if existing_default.scalar_one_or_none() is None:
                    is_default = True

            provider = VoiceProvider(
                name=name,
                platform=platform,
                service_type="embedding",
                api_key=self._encrypt_secret(api_key),
                config=_safe_json_dumps(config or {}),
                is_default=is_default,
                is_enabled=True,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)

        await self.load_providers()
        return provider

    async def update_provider(
        self,
        *,
        provider_id: str,
        name: str | None = None,
        api_key: str | None = None,
        config: dict | None = None,
        is_default: bool | None = None,
        is_enabled: bool | None = None,
    ) -> VoiceProvider | None:
        async with self._session_factory() as session:
            provider = await session.get(VoiceProvider, provider_id)
            if not provider or provider.service_type != "embedding":
                return None

            if name is not None:
                provider.name = name
            if api_key is not None:
                provider.api_key = self._encrypt_secret(api_key)
            if config is not None:
                provider.config = _safe_json_dumps(config)
            if is_enabled is not None:
                provider.is_enabled = is_enabled

            if is_default is True:
                await session.execute(
                    update(VoiceProvider)
                    .where(VoiceProvider.service_type == "embedding")
                    .values(is_default=False)
                )
                provider.is_default = True
            elif is_default is False:
                provider.is_default = False

            await session.commit()
            await session.refresh(provider)

            if not provider.is_default:
                existing_default = await session.execute(
                    select(VoiceProvider.id)
                    .where(VoiceProvider.service_type == "embedding")
                    .where(VoiceProvider.is_default.is_(True))
                    .limit(1)
                )
                if existing_default.scalar_one_or_none() is None:
                    provider.is_default = True
                    await session.commit()
                    await session.refresh(provider)

        await self.load_providers()
        return provider

    async def delete_provider(self, provider_id: str) -> bool:
        async with self._session_factory() as session:
            provider = await session.get(VoiceProvider, provider_id)
            if not provider or provider.service_type != "embedding":
                return False

            was_default = bool(provider.is_default)
            await session.delete(provider)
            await session.commit()

            if was_default:
                replacement = await session.execute(
                    select(VoiceProvider)
                    .where(VoiceProvider.service_type == "embedding")
                    .order_by(VoiceProvider.updated_at.desc())
                    .limit(1)
                )
                next_provider = replacement.scalar_one_or_none()
                if next_provider is not None:
                    next_provider.is_default = True
                    await session.commit()

        await self.load_providers()
        return True

    # ---- Embed ----

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using the default provider."""
        provider = self._get_provider()
        if not provider:
            raise ValueError("没有可用的 Embedding Provider，请在 AI 配置中添加向量服务")
        return await provider.embed(texts)

    @property
    def dimensions(self) -> int:
        """Return vector dimensions of the current provider."""
        provider = self._get_provider()
        return provider.dimensions if provider else 1024

    def _get_provider(self) -> EmbeddingProviderBase | None:
        if self._default_provider_id and self._default_provider_id in self._providers:
            return self._providers[self._default_provider_id]
        if self._providers:
            return next(iter(self._providers.values()))
        return None

    @property
    def available(self) -> bool:
        return bool(self._providers)

    @staticmethod
    def _encrypt_secret(value: str) -> str:
        if not value:
            return ""
        try:
            from openvort.plugins.vortgit.crypto import encrypt_token
            return encrypt_token(value)
        except Exception:
            return value

    @staticmethod
    def _decrypt_secret(value: str) -> str:
        if not value:
            return ""
        try:
            from openvort.plugins.vortgit.crypto import decrypt_token
            return decrypt_token(value)
        except Exception:
            return value