"""DingTalk channel tools."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy import select

from openvort.auth.service import AuthService
from openvort.contacts.models import PlatformIdentity
from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool, Message
from openvort.utils.logging import get_logger

log = get_logger("channels.dingtalk.tools")


async def _get_bound_dingtalk_user_id(member_id: str) -> str:
    if not member_id:
        return ""

    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = (
            select(PlatformIdentity.platform_user_id)
            .where(
                PlatformIdentity.member_id == member_id,
                PlatformIdentity.platform == "dingtalk",
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return (result.scalar_one_or_none() or "").strip()


async def _is_admin_member(member_id: str) -> bool:
    if not member_id:
        return False

    auth_service = AuthService(get_session_factory())
    permissions = await auth_service.get_member_permissions(member_id)
    return "*" in permissions


async def _mp3_to_amr(mp3_data: bytes) -> bytes:
    """Convert MP3 audio to AMR format using ffmpeg."""

    def _resolve_ffmpeg() -> str:
        env_path = (os.getenv("OPENVORT_FFMPEG") or "").strip()
        if env_path and Path(env_path).exists():
            return env_path

        path_cmd = shutil.which("ffmpeg")
        if path_cmd:
            return path_cmd

        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

        raise FileNotFoundError(
            "找不到 ffmpeg，可安装 ffmpeg，或在环境变量 OPENVORT_FFMPEG 中指定 ffmpeg.exe 路径。"
        )

    def _convert() -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f_in:
            f_in.write(mp3_data)
            in_path = f_in.name
        out_path = in_path.replace(".mp3", ".amr")
        try:
            ffmpeg_bin = _resolve_ffmpeg()
            subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    in_path,
                    "-c:a",
                    "libopencore_amrnb",
                    "-ar",
                    "8000",
                    "-ac",
                    "1",
                    "-b:a",
                    "12.2k",
                    out_path,
                ],
                capture_output=True,
                check=True,
                timeout=30,
            )
            return Path(out_path).read_bytes()
        finally:
            Path(in_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)

    return await asyncio.get_running_loop().run_in_executor(None, _convert)


def _estimate_voice_duration_seconds(text: str) -> int:
    # Keep it simple and deterministic; DingTalk only needs an approximate duration.
    return max(1, min(60, len(text.strip()) // 6 or 1))


class SendDingTalkMessageTool(BaseTool):
    """Send a proactive DingTalk text message."""

    name = "dingtalk_send_message"
    description = (
        "Send a message through DingTalk to a specific user. "
        "user_id is optional; when omitted it sends to the current caller's bound DingTalk account. "
        "Use contacts_search first if you need another member's DingTalk user_id."
    )
    required_permission = "dingtalk.send"

    def __init__(self, channel=None):
        self._channel = channel

    def set_channel(self, channel) -> None:
        self._channel = channel

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "DingTalk user ID; defaults to the caller's bound DingTalk account",
                },
                "content": {
                    "type": "string",
                    "description": "Message content to send",
                },
            },
            "required": ["content"],
        }

    async def execute(self, params: dict) -> str:
        return await _send_text(self._channel, params)


class SendDingTalkVoiceTool(BaseTool):
    """Send a proactive DingTalk voice message."""

    name = "dingtalk_send_voice"
    description = (
        "Send a voice message through DingTalk to a specific user. "
        "user_id is optional; when omitted it sends to the current caller's bound DingTalk account. "
        "The system converts text to speech before sending."
    )
    required_permission = "dingtalk.send"

    def __init__(self, channel=None, tts_service=None):
        self._channel = channel
        self._tts_service = tts_service

    def set_channel(self, channel) -> None:
        self._channel = channel

    def set_tts_service(self, tts_service) -> None:
        self._tts_service = tts_service

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "DingTalk user ID; defaults to the caller's bound DingTalk account",
                },
                "text": {
                    "type": "string",
                    "description": "Text to convert into voice, ideally under 200 characters",
                },
            },
            "required": ["text"],
        }

    async def execute(self, params: dict) -> str:
        user_id, err = await _resolve_target_user(self._channel, params)
        if err:
            return err
        if not self._tts_service or not self._tts_service.available:
            return json.dumps({"ok": False, "message": "TTS service is not configured"}, ensure_ascii=False)

        text = params.get("text", "").strip()
        if not text:
            return json.dumps({"ok": False, "message": "Missing text parameter"}, ensure_ascii=False)

        try:
            audio_bytes = await self._tts_service.synthesize(text)
            log.info("DingTalk TTS synthesized: %s bytes (mp3)", len(audio_bytes))

            amr_bytes = await _mp3_to_amr(audio_bytes)
            log.info("DingTalk voice converted to AMR: %s bytes", len(amr_bytes))

            media = await self._channel.upload_media("voice", amr_bytes, "voice.amr")
            media_id = str(media.get("media_id") or "").strip()
            if not media_id:
                return json.dumps({"ok": False, "message": "Failed to upload DingTalk voice media"}, ensure_ascii=False)

            duration = _estimate_voice_duration_seconds(text)
            await self._channel.send(
                user_id,
                Message(
                    content=text,
                    channel="dingtalk",
                    msg_type="voice",
                    raw={"voice_data": {"media_id": media_id, "duration": duration}},
                ),
            )
            log.info("DingTalk voice sent: %s <- %s", user_id, text[:50])
            return json.dumps({"ok": True, "message": f"Voice message sent to {user_id}"}, ensure_ascii=False)
        except Exception as exc:
            log.error("Failed to send DingTalk voice: %s", exc)
            return json.dumps({"ok": False, "message": f"Voice send failed: {exc}"}, ensure_ascii=False)


async def _send_text(channel, params: dict) -> str:
    user_id, err = await _resolve_target_user(channel, params)
    if err:
        return err

    content = params.get("content", "").strip()
    if not content:
        return json.dumps({"ok": False, "message": "Missing content parameter"}, ensure_ascii=False)

    try:
        msg_type = "markdown" if "\n" in content else "text"
        await channel.send(user_id, Message(content=content, channel="dingtalk", msg_type=msg_type))
        log.info("DingTalk message sent: %s <- %s", user_id, content[:50])
        return json.dumps({"ok": True, "message": f"Message sent to {user_id}"}, ensure_ascii=False)
    except Exception as exc:
        log.error("Failed to send DingTalk message: %s", exc)
        return json.dumps({"ok": False, "message": f"Send failed: {exc}"}, ensure_ascii=False)


async def _resolve_target_user(channel, params: dict) -> tuple[str, str | None]:
    if not channel:
        return "", json.dumps({"ok": False, "message": "DingTalk channel is not initialized"}, ensure_ascii=False)
    if not channel.is_configured():
        return "", json.dumps({"ok": False, "message": "DingTalk channel is not configured"}, ensure_ascii=False)

    user_id = params.get("user_id", "").strip()
    caller_member_id = (params.get("_member_id") or params.get("_caller_member_id") or "").strip()

    bound_user_id = await _get_bound_dingtalk_user_id(caller_member_id)
    is_admin = await _is_admin_member(caller_member_id)

    if not user_id:
        if not bound_user_id:
            return "", json.dumps(
                {
                    "ok": False,
                    "message": "Current account is not bound to DingTalk; sync/bind first or provide user_id explicitly.",
                },
                ensure_ascii=False,
            )
        return bound_user_id, None

    if caller_member_id and not is_admin and bound_user_id and user_id != bound_user_id:
        return "", json.dumps(
            {
                "ok": False,
                "message": "Non-admin members can only send to their own bound DingTalk account.",
            },
            ensure_ascii=False,
        )

    if caller_member_id and not is_admin and not bound_user_id:
        return "", json.dumps(
            {
                "ok": False,
                "message": "Current account is not bound to DingTalk; non-admin members cannot target another DingTalk account directly.",
            },
            ensure_ascii=False,
        )

    return user_id, None
