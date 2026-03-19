"""飞书通道工具。"""

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
from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("channels.feishu.tools")


async def _get_bound_feishu_user_id(member_id: str) -> str:
    if not member_id:
        return ""

    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = (
            select(PlatformIdentity.platform_user_id)
            .where(
                PlatformIdentity.member_id == member_id,
                PlatformIdentity.platform == "feishu",
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


async def _mp3_to_opus(mp3_data: bytes) -> bytes:
    """Convert MP3 audio to OGG/OPUS using ffmpeg for Feishu audio messages."""

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
            "未找到 ffmpeg，可安装 ffmpeg 或在环境变量 OPENVORT_FFMPEG 中指定 ffmpeg.exe 路径。"
        )

    def _convert():
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f_in:
            f_in.write(mp3_data)
            in_path = f_in.name
        out_path = in_path.replace(".mp3", ".opus")
        try:
            ffmpeg_bin = _resolve_ffmpeg()
            subprocess.run(
                [
                    ffmpeg_bin, "-y", "-i", in_path,
                    "-c:a", "libopus", "-b:a", "24k", "-ar", "48000", "-ac", "1",
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


class SendFeishuMessageTool(BaseTool):
    """通过飞书主动发送消息。"""

    name = "feishu_send_message"
    description = (
        "通过飞书给指定用户发送消息。"
        "user_id 可选；不传时默认发送给当前对话者已绑定的飞书账号。"
        "如需指定其他人，需要提供用户的飞书 open_id。"
        "可先使用 contacts_search 搜索成员，再使用其飞书身份 open_id。"
    )
    required_permission = "feishu.send"

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
                    "description": "飞书用户 open_id；留空时默认发送给当前对话者已绑定的飞书账号",
                },
                "content": {
                    "type": "string",
                    "description": "要发送的消息内容",
                },
            },
            "required": ["content"],
        }

    async def execute(self, params: dict) -> str:
        user_id = params.get("user_id", "").strip()
        content = params.get("content", "").strip()
        caller_member_id = (params.get("_member_id") or params.get("_caller_member_id") or "").strip()

        if not content:
            return json.dumps({"ok": False, "message": "缺少 content 参数"}, ensure_ascii=False)
        if not self._channel:
            return json.dumps({"ok": False, "message": "飞书通道未初始化"}, ensure_ascii=False)
        if not self._channel.is_configured():
            return json.dumps({"ok": False, "message": "飞书通道未配置"}, ensure_ascii=False)

        bound_user_id = await _get_bound_feishu_user_id(caller_member_id)
        is_admin = await _is_admin_member(caller_member_id)

        if not user_id:
            if not bound_user_id:
                return json.dumps(
                    {
                        "ok": False,
                        "message": "当前账号未绑定飞书身份，无法确定“我的飞书用户”；请先同步/绑定，或明确提供 open_id。",
                    },
                    ensure_ascii=False,
                )
            user_id = bound_user_id
        elif caller_member_id and not is_admin and bound_user_id and user_id != bound_user_id:
            return json.dumps(
                {
                    "ok": False,
                    "message": "普通成员只能给自己已绑定的飞书账号发消息；如需给其他成员发消息，请使用管理员账号。",
                },
                ensure_ascii=False,
            )
        elif caller_member_id and not is_admin and not bound_user_id:
            return json.dumps(
                {
                    "ok": False,
                    "message": "当前账号尚未绑定飞书身份，普通成员不能直接指定其他飞书账号发送消息。",
                },
                ensure_ascii=False,
            )

        try:
            from openvort.plugin.base import Message

            await self._channel.send(user_id, Message(content=content, channel="feishu"))
            log.info(f"已发送飞书消息: {user_id} <- {content[:50]}")
            return json.dumps({"ok": True, "message": f"已成功发送消息给 {user_id}"}, ensure_ascii=False)
        except Exception as e:
            log.error(f"发送飞书消息失败: {e}")
            return json.dumps({"ok": False, "message": f"发送失败: {e}"}, ensure_ascii=False)


class SendFeishuVoiceTool(BaseTool):
    """通过飞书主动发送语音。"""

    name = "feishu_send_voice"
    description = (
        "通过飞书给指定用户发送语音消息。"
        "user_id 可选；不传时默认发送给当前对话者已绑定的飞书账号。"
        "如需指定其他人，需要提供用户的飞书 open_id。"
        "系统会自动将文字转为语音后发送，适合简短提醒和问候。"
    )
    required_permission = "feishu.send"

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
                    "description": "飞书用户 open_id；留空时默认发送给当前对话者已绑定的飞书账号",
                },
                "text": {
                    "type": "string",
                    "description": "要转为语音发送的文字内容（建议不超过200字）",
                },
            },
            "required": ["text"],
        }

    async def execute(self, params: dict) -> str:
        user_id = params.get("user_id", "").strip()
        text = params.get("text", "").strip()
        caller_member_id = (params.get("_member_id") or params.get("_caller_member_id") or "").strip()

        if not text:
            return json.dumps({"ok": False, "message": "缺少 text 参数"}, ensure_ascii=False)
        if not self._channel:
            return json.dumps({"ok": False, "message": "飞书通道未初始化"}, ensure_ascii=False)
        if not self._channel.is_configured():
            return json.dumps({"ok": False, "message": "飞书通道未配置"}, ensure_ascii=False)
        if not self._tts_service or not self._tts_service.available:
            return json.dumps({"ok": False, "message": "TTS 服务未配置"}, ensure_ascii=False)

        bound_user_id = await _get_bound_feishu_user_id(caller_member_id)
        is_admin = await _is_admin_member(caller_member_id)

        if not user_id:
            if not bound_user_id:
                return json.dumps(
                    {
                        "ok": False,
                        "message": "当前账号未绑定飞书身份，无法确定“我的飞书用户”；请先同步/绑定，或明确提供 open_id。",
                    },
                    ensure_ascii=False,
                )
            user_id = bound_user_id
        elif caller_member_id and not is_admin and bound_user_id and user_id != bound_user_id:
            return json.dumps(
                {
                    "ok": False,
                    "message": "普通成员只能给自己已绑定的飞书账号发语音；如需给其他成员发消息，请使用管理员账号。",
                },
                ensure_ascii=False,
            )
        elif caller_member_id and not is_admin and not bound_user_id:
            return json.dumps(
                {
                    "ok": False,
                    "message": "当前账号尚未绑定飞书身份，普通成员不能直接指定其他飞书账号发送语音。",
                },
                ensure_ascii=False,
            )

        try:
            audio_bytes = await self._tts_service.synthesize(text)
            log.info(f"TTS 合成完成: {len(audio_bytes)} bytes (mp3)")

            audio_bytes = await _mp3_to_opus(audio_bytes)
            log.info(f"转换为 OPUS: {len(audio_bytes)} bytes")

            file_key = await self._channel.api.upload_file(
                audio_bytes,
                filename="voice.opus",
                file_type="opus",
            )
            if not file_key:
                return json.dumps({"ok": False, "message": "上传语音文件失败"}, ensure_ascii=False)

            from openvort.plugin.base import Message

            message = Message(
                content=text,
                channel="feishu",
                msg_type="voice",
                raw={"voice_data": {"file_key": file_key, "format": "opus"}},
            )
            await self._channel.send(user_id, message)
            log.info(f"已发送飞书语音: {user_id} <- {text[:50]}")
            return json.dumps({"ok": True, "message": f"已成功发送语音消息给 {user_id}"}, ensure_ascii=False)
        except Exception as e:
            log.error(f"发送飞书语音失败: {e}")
            return json.dumps({"ok": False, "message": f"发送语音失败: {e}"}, ensure_ascii=False)
