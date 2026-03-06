"""TTS service manager — loads providers from voice_providers table."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from openvort.db.models import VoiceProvider
from openvort.services.tts.providers.aliyun import AliyunTTSProvider
from openvort.services.tts.providers.base import TTSProviderBase
from openvort.utils.logging import get_logger

log = get_logger("services.tts")

PROVIDER_CLASSES: dict[str, type[TTSProviderBase]] = {
    "aliyun": AliyunTTSProvider,
}


class TTSService:
    """TTS service backed by voice_providers table (service_type='tts')."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._providers: dict[str, TTSProviderBase] = {}
        self._default_provider_id: str = ""

    async def load_providers(self) -> None:
        """Load all enabled TTS providers from DB."""
        await self.close()

        async with self._session_factory() as session:
            stmt = select(VoiceProvider).where(
                VoiceProvider.service_type == "tts",
                VoiceProvider.is_enabled == True,  # noqa: E712
            )
            result = await session.execute(stmt)
            providers = result.scalars().all()

        for p in providers:
            await self._load_provider(p)

        log.info(f"已加载 {len(self._providers)} 个 TTS Provider")

    async def _load_provider(self, provider: VoiceProvider) -> None:
        provider_class = PROVIDER_CLASSES.get(provider.platform)
        if not provider_class:
            log.warning(f"未知的 TTS Provider 平台: {provider.platform}")
            return

        try:
            api_key = provider.api_key
            if api_key:
                try:
                    from openvort.plugins.vortgit.crypto import decrypt_token
                    api_key = decrypt_token(api_key)
                except Exception:
                    pass

            config = json.loads(provider.config) if provider.config else {}
            instance = provider_class(api_key=api_key, config=config)
            self._providers[provider.id] = instance

            if provider.is_default:
                self._default_provider_id = provider.id

            log.info(f"已加载 TTS Provider: {provider.name} ({provider.platform})")
        except Exception as e:
            log.error(f"加载 TTS Provider 失败: {provider.name}, error: {e}")

    async def synthesize(self, text: str, *, voice: str = "", **options) -> bytes:
        """Synthesize text to audio bytes using the default provider."""
        provider = self._get_provider()
        if not provider:
            raise ValueError("没有可用的 TTS Provider")
        return await provider.synthesize(text, voice=voice, **options)

    def _get_provider(self) -> TTSProviderBase | None:
        if self._default_provider_id and self._default_provider_id in self._providers:
            return self._providers[self._default_provider_id]
        if self._providers:
            return next(iter(self._providers.values()))
        return None

    @property
    def available(self) -> bool:
        return bool(self._providers)

    async def close(self) -> None:
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception:
                pass
        self._providers.clear()
        self._default_provider_id = ""
