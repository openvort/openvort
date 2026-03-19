"""ASR providers registry."""

from openvort.services.asr.providers.aliyun import AliyunASRProvider
from openvort.services.asr.providers.base import BaseASRProvider

__all__ = [
    "AliyunASRProvider",
    "BaseASRProvider",
]

"""ASR Providers"""

from openvort.services.asr.providers.aliyun import AliyunASRProvider
from openvort.services.asr.providers.base import ASRProviderBase

__all__ = ["ASRProviderBase", "AliyunASRProvider"]
