"""TTS Providers."""

from openvort.services.tts.providers.aliyun import AliyunTTSProvider
from openvort.services.tts.providers.base import TTSProviderBase

__all__ = ["TTSProviderBase", "AliyunTTSProvider"]
