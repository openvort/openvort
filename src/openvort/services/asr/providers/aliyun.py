"""Aliyun ASR provider.

Current implementation keeps the interface stable and can be extended
to call the real ASR endpoint later.
"""

from openvort.services.asr.providers.base import BaseASRProvider
from openvort.utils.logging import get_logger

log = get_logger("services.asr.aliyun")


class AliyunASRProvider(BaseASRProvider):
    """Aliyun ASR provider placeholder implementation."""

    def __init__(self, api_key: str, config: dict):
        self._api_key = api_key or ""
        self._config = config or {}

    async def recognize(self, audio_data: bytes, *, audio_format: str = "amr") -> str:
        if not audio_data:
            return ""
        if not self._api_key:
            raise RuntimeError("Aliyun ASR provider missing api_key.")
        # Keep the service available even when ASR runtime is not wired yet.
        log.warning("Aliyun ASR runtime is not fully implemented yet; returning empty transcript.")
        return ""

"""阿里云百炼 ASR Provider - 语音识别"""

import asyncio
import base64
import json
import os
import tempfile
from typing import List

import httpx

from openvort.services.asr.providers.base import ASRProviderBase
from openvort.utils.logging import get_logger

log = get_logger("services.asr.aliyun")

# DashScope OpenAI 兼容 API 地址
DASHSCOPE_API_CN = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_API_INTL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


class AliyunASRProvider(ASRProviderBase):
    """阿里云百炼 ASR Provider - 语音识别"""

    platform = "aliyun"

    def __init__(self, api_key: str, config: dict):
        """
        初始化阿里云 ASR Provider

        Args:
            api_key: API 密钥
            config: 配置字典，包含:
                - model: 模型名称，默认 qwen3-asr-flash
                - language: 语言，默认 auto (自动检测)
                - region: 地域，cn 或 intl，默认 cn
        """
        self.api_key = api_key
        self.model = config.get("model", "qwen3-asr-flash")
        self.language = config.get("language", "auto")
        self.region = config.get("region", "cn")
        self._api_base = DASHSCOPE_API_CN if self.region == "cn" else DASHSCOPE_API_INTL
        self._http = httpx.AsyncClient(timeout=120)

        # 设置 DashScope API Key（全局）
        import dashscope
        dashscope.api_key = api_key

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
        model = options.get("model", self.model)

        log.info(f"调用阿里云 ASR 识别: model={model}, format={format}, audio_size={len(audio_data)} bytes")

        # 上传音频到 OSS 获取 URL
        audio_url = await self._upload_to_oss(audio_data, format)
        log.info(f"音频已上传到 OSS: {audio_url}")

        # 使用 OpenAI 兼容 API
        url = f"{self._api_base}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 构造请求（使用 OpenAI 格式）
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": [{"text": ""}]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_url
                            }
                        }
                    ]
                }
            ],
            "stream": False,
        }

        try:
            resp = await self._http.post(url, json=payload, headers=headers)
            log.info(f"ASR 响应状态: {resp.status_code}")
            log.info(f"ASR 响应内容: {resp.text[:500]}")

            if resp.status_code != 200:
                raise RuntimeError(f"ASR 请求失败: {resp.status_code} - {resp.text[:200]}")

            data = resp.json()

            # 解析转写结果
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            log.info(f"ASR 识别成功: {text[:100]}...")
            return text

        except Exception as e:
            log.error(f"ASR 识别异常: {e}")
            raise

    async def _upload_to_oss(self, audio_data: bytes, format: str) -> str:
        """上传音频到 OSS 并返回 URL"""
        # OpenAI 兼容 ASR 接口要求可直接访问的 URL；
        # DashScope Files.upload 返回 file://<id> 在该接口下会被判定为无效 URL。
        # 这里统一走 data URL，避免 file:// 兼容问题导致 400 InvalidParameter。
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")
        return f"data:audio/{format};base64,{audio_base64}"

    async def _upload_to_dashscope(self, audio_data: bytes, format: str) -> str:
        """使用 DashScope Files API 上传音频"""
        from dashscope import Files

        # 创建临时文件
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            # 传入 api_key
            response = Files.upload(
                file_path=tmp_path,
                purpose="inference",
                api_key=self.api_key,
            )

            if response.status_code == 200:
                output = response.output
                if isinstance(output, dict):
                    uploaded_files = output.get("uploaded_files", [])
                    if uploaded_files:
                        file_id = uploaded_files[0].get("file_id")
                        return f"file://{file_id}"

            raise RuntimeError(f"文件上传失败: {response.code} - {response.message}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def health_check(self) -> bool:
        """检查服务可用性"""
        try:
            url = f"{self._api_base}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = await self._http.get(url, headers=headers)
            return resp.status_code == 200
        except Exception as e:
            log.error(f"阿里云 ASR 健康检查失败: {e}")
            return False

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        await self._http.aclose()
