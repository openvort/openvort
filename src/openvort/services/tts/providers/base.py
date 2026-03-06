"""TTS Provider abstract base class."""

from abc import ABC, abstractmethod


class TTSProviderBase(ABC):
    """TTS provider interface."""

    platform: str = ""

    @abstractmethod
    async def synthesize(self, text: str, *, voice: str = "", **options) -> bytes:
        """Synthesize text to audio bytes (MP3).

        Args:
            text: Text to synthesize.
            voice: Voice name override (uses provider default if empty).
            **options: Extra provider-specific options.

        Returns:
            Audio bytes in MP3 format.
        """
        ...

    async def close(self) -> None:
        """Release provider resources."""
