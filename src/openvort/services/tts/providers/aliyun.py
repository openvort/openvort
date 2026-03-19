"""Aliyun CosyVoice TTS Provider."""

import asyncio
from xml.sax.saxutils import escape

from openvort.services.tts.providers.base import TTSProviderBase
from openvort.utils.logging import get_logger

log = get_logger("services.tts.aliyun")


class AliyunTTSProvider(TTSProviderBase):
    """Aliyun CosyVoice TTS via dashscope SDK (non-streaming)."""

    platform = "aliyun"

    def __init__(self, api_key: str, config: dict):
        self.api_key = api_key
        self.model = config.get("model", "cosyvoice-v3-flash")
        self.voice = config.get("voice", "longanyang")
        self.region = config.get("region", "cn")

    async def synthesize(self, text: str, *, voice: str = "", **options) -> bytes:
        if not text or not text.strip():
            raise ValueError("TTS text is empty")

        import dashscope
        from dashscope.audio.tts_v2 import SpeechSynthesizer

        dashscope.api_key = self.api_key
        if self.region == "cn":
            dashscope.base_websocket_api_url = (
                "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
            )
        else:
            dashscope.base_websocket_api_url = (
                "wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference"
            )

        use_voice = voice or self.voice
        model = options.get("model", self.model)

        log.info(
            f"TTS 合成: model={model}, voice={use_voice}, text_len={len(text)}"
        )

        # Non-streaming call returns complete audio bytes (MP3 by default).
        # dashscope TTS is synchronous under the hood (WebSocket),
        # run in executor to avoid blocking the event loop.
        def _call():
            synth = SpeechSynthesizer(model=model, voice=use_voice)
            # dashscope SDK forces enable_ssml=True internally for call(),
            # so plain text must be wrapped as minimal SSML.
            ssml_text = f"<speak>{escape(text.strip())}</speak>"
            return synth.call(ssml_text)

        loop = asyncio.get_running_loop()
        audio = await loop.run_in_executor(None, _call)

        if not audio:
            raise RuntimeError("TTS returned empty audio")

        log.info(f"TTS 合成成功: {len(audio)} bytes")
        return audio

    async def close(self) -> None:
        pass
