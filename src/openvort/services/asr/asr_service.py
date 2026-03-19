"""ASR service for provider management and speech recognition."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select, update

from openvort.db.models import VoiceProvider
from openvort.services.asr.providers import AliyunASRProvider, BaseASRProvider
from openvort.utils.logging import get_logger

log = get_logger("services.asr")


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


class ASRService:
    """ASR service backed by voice_providers table."""

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._providers: dict[str, BaseASRProvider] = {}
        self._provider_meta: dict[str, dict[str, Any]] = {}
        self._default_provider_id: str = ""

    async def close(self) -> None:
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception:
                pass
        self._providers.clear()
        self._provider_meta.clear()
        self._default_provider_id = ""

    async def load_providers(self) -> None:
        await self.close()

        async with self._session_factory() as session:
            stmt = (
                select(VoiceProvider)
                .where(VoiceProvider.service_type == "asr")
                .where(VoiceProvider.is_enabled.is_(True))
                .order_by(VoiceProvider.is_default.desc(), VoiceProvider.updated_at.desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        for row in rows:
            config = _safe_json_loads(row.config)
            provider = self._create_provider(
                platform=row.platform,
                api_key=self._decrypt_secret(row.api_key),
                config=config,
            )
            if provider is None:
                continue

            self._providers[row.id] = provider
            self._provider_meta[row.id] = {
                "id": row.id,
                "name": row.name,
                "platform": row.platform,
                "is_default": bool(row.is_default),
                "is_enabled": bool(row.is_enabled),
                "config": config,
            }
            if row.is_default and not self._default_provider_id:
                self._default_provider_id = row.id

        if not self._default_provider_id and self._providers:
            self._default_provider_id = next(iter(self._providers.keys()))

    async def list_providers(self) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = (
                select(VoiceProvider)
                .where(VoiceProvider.service_type == "asr")
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
                    .where(VoiceProvider.service_type == "asr")
                    .values(is_default=False)
                )
            else:
                existing_default = await session.execute(
                    select(VoiceProvider.id)
                    .where(VoiceProvider.service_type == "asr")
                    .where(VoiceProvider.is_default.is_(True))
                    .limit(1)
                )
                if existing_default.scalar_one_or_none() is None:
                    is_default = True

            provider = VoiceProvider(
                name=name,
                platform=platform,
                service_type="asr",
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
            if not provider or provider.service_type != "asr":
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
                    .where(VoiceProvider.service_type == "asr")
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
                    .where(VoiceProvider.service_type == "asr")
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
            if not provider or provider.service_type != "asr":
                return False

            was_default = bool(provider.is_default)
            await session.delete(provider)
            await session.commit()

            if was_default:
                replacement = await session.execute(
                    select(VoiceProvider)
                    .where(VoiceProvider.service_type == "asr")
                    .order_by(VoiceProvider.updated_at.desc())
                    .limit(1)
                )
                next_provider = replacement.scalar_one_or_none()
                if next_provider is not None:
                    next_provider.is_default = True
                    await session.commit()

        await self.load_providers()
        return True

    async def recognize(self, audio_data: bytes, *, format: str = "amr") -> str:
        provider = self._get_runtime_provider()
        if provider is None:
            return ""
        return await provider.recognize(audio_data, audio_format=format)

    def _get_runtime_provider(self) -> BaseASRProvider | None:
        if self._default_provider_id and self._default_provider_id in self._providers:
            return self._providers[self._default_provider_id]
        if not self._providers:
            return None
        return next(iter(self._providers.values()))

    def _create_provider(self, *, platform: str, api_key: str, config: dict) -> BaseASRProvider | None:
        if platform == "aliyun":
            return AliyunASRProvider(api_key=api_key, config=config)
        log.warning(f"ASR 平台暂不支持: {platform}")
        return None

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

"""ASR 语音识别服务管理器"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from openvort.db.models import VoiceProvider
from openvort.plugins.vortgit.crypto import decrypt_token
from openvort.services.asr.providers.aliyun import AliyunASRProvider
from openvort.services.asr.providers.base import ASRProviderBase
from openvort.utils.logging import get_logger

log = get_logger("services.asr")

# Provider 类映射
PROVIDER_CLASSES = {
    "aliyun": AliyunASRProvider,
}


class ASRService:
    """ASR 语音识别服务管理器"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._providers: dict[str, ASRProviderBase] = {}
        self._default_provider_id: str = ""
        self._default_platform: str = ""

    async def load_providers(self) -> None:
        """从数据库加载所有启用的 ASR Provider"""
        async with self._session_factory() as session:
            stmt = select(VoiceProvider).where(
                VoiceProvider.service_type == "asr",
                VoiceProvider.is_enabled == True,
            )
            result = await session.execute(stmt)
            providers = result.scalars().all()

            for p in providers:
                await self._load_provider(p)

        log.info(f"已加载 {len(self._providers)} 个 ASR Provider")

    async def _load_provider(self, provider: VoiceProvider) -> None:
        """加载单个 ASR Provider"""
        provider_class = PROVIDER_CLASSES.get(provider.platform)
        if not provider_class:
            log.warning(f"未知的 ASR Provider 平台: {provider.platform}")
            return

        try:
            # 解密 API Key
            api_key = provider.api_key
            if api_key:
                try:
                    api_key = decrypt_token(api_key)
                except Exception:
                    pass  # 未加密的明文

            # 解析配置 JSON
            config = json.loads(provider.config) if provider.config else {}

            # 创建 Provider 实例
            instance = provider_class(api_key=api_key, config=config)
            self._providers[provider.id] = instance

            if provider.is_default:
                self._default_provider_id = provider.id
                self._default_platform = provider.platform

            log.info(f"已加载 ASR Provider: {provider.name} ({provider.platform})")
        except Exception as e:
            log.error(f"加载 ASR Provider 失败: {provider.name}, error: {e}")

    async def recognize(
        self,
        audio_data: bytes,
        format: str = "wav",
        provider_id: str = "",
        provider_platform: str = "",
        **options,
    ) -> str:
        """
        识别语音

        Args:
            audio_data: 音频数据 bytes
            format: 音频格式 (wav, mp3, amr, silk 等)
            provider_id: 指定 Provider ID
            provider_platform: 指定平台名称（如 aliyun）
            **options: 其他参数

        Returns:
            转写的文本内容
        """
        provider = self._get_provider(provider_id, provider_platform)
        if not provider:
            raise ValueError("没有可用的 ASR Provider")

        return await provider.recognize(audio_data, format, **options)

    def _get_provider(self, provider_id: str = "", provider_platform: str = "") -> ASRProviderBase | None:
        """获取 Provider 实例"""
        if provider_id and provider_id in self._providers:
            return self._providers[provider_id]

        # 通过平台名称查找
        if provider_platform:
            for pid, p in self._providers.items():
                if p.platform == provider_platform:
                    return p

        # 返回默认 Provider
        if self._default_provider_id and self._default_provider_id in self._providers:
            return self._providers[self._default_provider_id]

        # 返回第一个可用的
        if self._providers:
            return next(iter(self._providers.values()))

        return None

    async def list_providers(self) -> list[dict]:
        """列出所有 ASR Provider（不含敏感信息）"""
        async with self._session_factory() as session:
            stmt = select(VoiceProvider).where(
                VoiceProvider.service_type == "asr",
            ).order_by(VoiceProvider.is_default.desc(), VoiceProvider.name)
            result = await session.execute(stmt)
            providers = result.scalars().all()

            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "platform": p.platform,
                    "is_default": p.is_default,
                    "is_enabled": p.is_enabled,
                    "config": json.loads(p.config) if p.config else {},
                }
                for p in providers
            ]

    async def add_provider(
        self,
        name: str,
        platform: str,
        api_key: str,
        config: dict,
        is_default: bool = False,
    ) -> VoiceProvider:
        """添加 ASR Provider"""
        from openvort.plugins.vortgit.crypto import encrypt_token

        # 加密 API Key
        encrypted_key = encrypt_token(api_key) if api_key else ""

        async with self._session_factory() as session:
            # 如果设为默认，先取消其他默认
            if is_default:
                stmt = select(VoiceProvider).where(
                    VoiceProvider.service_type == "asr",
                    VoiceProvider.is_default == True,
                )
                result = await session.execute(stmt)
                for p in result.scalars().all():
                    p.is_default = False

            provider = VoiceProvider(
                name=name,
                platform=platform,
                service_type="asr",
                api_key=encrypted_key,
                config=json.dumps(config),
                is_default=is_default,
                is_enabled=True,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)

        # 重新加载
        await self.load_providers()

        log.info(f"添加 ASR Provider: {name} ({platform})")
        return provider

    async def update_provider(
        self,
        provider_id: str,
        name: str = None,
        api_key: str = None,
        config: dict = None,
        is_default: bool = None,
        is_enabled: bool = None,
    ) -> VoiceProvider | None:
        """更新 ASR Provider"""
        from openvort.plugins.vortgit.crypto import encrypt_token

        async with self._session_factory() as session:
            stmt = select(VoiceProvider).where(VoiceProvider.id == provider_id)
            result = await session.execute(stmt)
            provider = result.scalar_one_or_none()

            if not provider:
                return None

            if name is not None:
                provider.name = name
            if api_key is not None:
                provider.api_key = encrypt_token(api_key) if api_key else ""
            if config is not None:
                provider.config = json.dumps(config)
            if is_default is not None:
                if is_default:
                    # 取消其他默认
                    stmt = select(VoiceProvider).where(
                        VoiceProvider.service_type == "asr",
                        VoiceProvider.is_default == True,
                    )
                    result = await session.execute(stmt)
                    for p in result.scalars().all():
                        if p.id != provider_id:
                            p.is_default = False
                provider.is_default = is_default
            if is_enabled is not None:
                provider.is_enabled = is_enabled

            await session.commit()
            await session.refresh(provider)

        # 重新加载
        await self.load_providers()

        log.info(f"更新 ASR Provider: {provider.name}")
        return provider

    async def delete_provider(self, provider_id: str) -> bool:
        """删除 ASR Provider"""
        async with self._session_factory() as session:
            stmt = select(VoiceProvider).where(VoiceProvider.id == provider_id)
            result = await session.execute(stmt)
            provider = result.scalar_one_or_none()

            if not provider:
                return False

            name = provider.name
            await session.delete(provider)
            await session.commit()

        # 重新加载
        await self.load_providers()

        log.info(f"删除 ASR Provider: {name}")
        return True

    async def close(self) -> None:
        """关闭所有 Provider"""
        for provider in self._providers.values():
            if hasattr(provider, "close"):
                await provider.close()
        self._providers.clear()
