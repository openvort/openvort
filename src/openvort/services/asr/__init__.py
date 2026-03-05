"""ASR service package."""

from openvort.services.asr.asr_service import ASRService

__all__ = ["ASRService"]

"""ASR 语音识别服务"""

from openvort.services.asr.providers.base import ASRProviderBase
from openvort.services.asr.asr_service import ASRService

__all__ = ["ASRProviderBase", "ASRService"]
