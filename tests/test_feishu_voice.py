from openvort.channels.feishu.channel import FeishuChannel
from openvort.channels.feishu.tools import SendFeishuVoiceTool
from openvort.core.agent import AgentRuntime


class _FakeFeishuAPI:
    def __init__(self):
        self.uploaded = []

    async def download_message_resource(self, message_id: str, file_key: str, resource_type: str) -> bytes:
        assert message_id == "msg-audio"
        assert file_key == "file-audio"
        assert resource_type == "file"
        return b"opus-bytes"

    async def upload_file(self, data: bytes, filename: str, file_type: str = "stream", duration: int | None = None) -> str:
        self.uploaded.append((data, filename, file_type, duration))
        return "uploaded-file-key"


class _FakeASRService:
    async def recognize(self, audio_data: bytes, format: str = "amr") -> str:
        assert audio_data == b"opus-bytes"
        assert format == "opus"
        return "转写文本"


class _FakeTTSService:
    available = True

    async def synthesize(self, text: str) -> bytes:
        return f"mp3:{text}".encode("utf-8")


class _FakeFeishuChannel:
    def __init__(self):
        self.api = _FakeFeishuAPI()
        self.sent = []

    def is_configured(self) -> bool:
        return True

    async def send(self, user_id, message):
        self.sent.append((user_id, message))


def test_build_audio_message_from_event():
    channel = FeishuChannel()
    channel._api = _FakeFeishuAPI()
    channel.set_asr_service(_FakeASRService())

    event = {
        "sender": {"sender_id": {"open_id": "ou_test"}},
        "message": {
            "message_id": "msg-audio",
            "message_type": "audio",
            "chat_type": "p2p",
            "chat_id": "chat-1",
            "content": '{"file_key":"file-audio"}',
            "mentions": [],
        },
    }

    import asyncio

    msg = asyncio.run(channel._build_message_from_event(event))
    assert msg is not None
    assert msg.msg_type == "audio"
    assert msg.content == "[语音消息]\n转写文本"
    assert msg.voice_media_ids == ["file-audio"]
    assert msg.raw["voice_data"]["format"] == "opus"


def test_feishu_send_voice_tool_execute():
    channel = _FakeFeishuChannel()
    tool = SendFeishuVoiceTool(channel=channel, tts_service=_FakeTTSService())

    import openvort.channels.feishu.tools as feishu_tools
    import asyncio

    original_get_bound = feishu_tools._get_bound_feishu_user_id
    original_is_admin = feishu_tools._is_admin_member
    original_convert = feishu_tools._mp3_to_opus
    feishu_tools._get_bound_feishu_user_id = lambda member_id: asyncio.sleep(0, result="ou_bound")
    feishu_tools._is_admin_member = lambda member_id: asyncio.sleep(0, result=False)
    feishu_tools._mp3_to_opus = lambda data: asyncio.sleep(0, result=b"opus-bytes")
    try:
        result = asyncio.run(tool.execute({"text": "提醒一下", "_member_id": "member-1"}))
    finally:
        feishu_tools._get_bound_feishu_user_id = original_get_bound
        feishu_tools._is_admin_member = original_is_admin
        feishu_tools._mp3_to_opus = original_convert

    assert '"ok": true' in result.lower()
    assert channel.api.uploaded[0][1] == "voice.opus"
    assert channel.api.uploaded[0][2] == "opus"
    sent_user, sent_message = channel.sent[0]
    assert sent_user == "ou_bound"
    assert sent_message.msg_type == "voice"
    assert sent_message.raw["voice_data"]["file_key"] == "uploaded-file-key"


def test_agent_prioritizes_feishu_voice_tool():
    tools = [
        {"name": "feishu_send_message"},
        {"name": "feishu_send_voice"},
        {"name": "contacts_search"},
    ]
    prioritized = AgentRuntime._prioritize_tools_for_intent("给我的飞书发语音提醒明天开会", tools)
    assert [tool["name"] for tool in prioritized] == [
        "feishu_send_voice",
        "feishu_send_message",
        "contacts_search",
    ]
