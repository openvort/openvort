"""Base ASR provider interface."""


class BaseASRProvider:
    """ASR provider abstract interface."""

    async def recognize(self, audio_data: bytes, *, audio_format: str = "amr") -> str:
        """Recognize speech from audio bytes."""
        raise NotImplementedError("ASR provider must implement recognize().")

    async def close(self) -> None:
        """Release provider resources."""
        return None

"""ASR Provider 抽象基类"""

from abc import ABC, abstractmethod


class ASRProviderBase(ABC):
    """语音识别服务 Provider 抽象基类"""

    platform: str = ""  # aliyun/tencent/openai

    @abstractmethod
    async def recognize(self, audio_data: bytes, format: str = "wav", **options) -> str:
        """
        识别语音，返回转写文本

        Args:
            audio_data: 音频数据 bytes
            format: 音频格式 (wav, mp3, amr, silk 等)
            **options: 其他参数

        Returns:
            转写的文本内容
        """
        ...

    async def health_check(self) -> bool:
        """检查服务可用性"""
        return True
