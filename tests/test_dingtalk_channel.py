import asyncio
import json

import httpx
from sqlalchemy import delete

from openvort.channels.dingtalk import DingTalkChannel
from openvort.channels.dingtalk.tools import SendDingTalkMessageTool, SendDingTalkVoiceTool
from openvort.config.settings import DingTalkSettings
from openvort.contacts.models import Member, PlatformIdentity
from openvort.db.engine import get_session_factory
from openvort.plugin.registry import PluginRegistry


def _build_channel(**overrides) -> DingTalkChannel:
    settings = DingTalkSettings(
        app_key=overrides.get("app_key", "app-key"),
        app_secret=overrides.get("app_secret", "app-secret"),
        robot_code=overrides.get("robot_code", "robot-code"),
        api_base=overrides.get("api_base", "https://api.dingtalk.com"),
    )
    return DingTalkChannel(settings=settings)


def test_dingtalk_current_config_masks_secret():
    channel = _build_channel(app_secret="secret-1234")

    current = channel.get_current_config()

    assert current["app_key"] == "app-key"
    assert current["robot_code"] == "robot-code"
    assert current["app_secret"] == "****1234"
    assert current["message_type"] == "markdown"
    assert channel.get_connection_info() == {"mode": "未启动"}


def test_dingtalk_card_streaming_flag():
    channel = _build_channel()
    assert channel._use_card_streaming() is False

    channel.apply_config(
        {
            "message_type": "card",
            "card_template_id": "tpl-1",
            "card_template_key": "content",
        }
    )

    assert channel._use_card_streaming() is True
    current = channel.get_current_config()
    assert current["card_template_id"] == "tpl-1"
    assert current["card_template_key"] == "content"


def test_dingtalk_build_text_message():
    channel = _build_channel()

    msg = channel._build_message(
        {
            "msgId": "msg-1",
            "msgtype": "text",
            "senderStaffId": "user-1",
            "conversationType": "1",
            "conversationId": "conv-1",
            "text": {"content": "你好，OpenVort"},
        }
    )

    assert msg is not None
    assert msg.content == "你好，OpenVort"
    assert msg.sender_id == "user-1"
    assert msg.raw["conversation_id"] == "conv-1"
    assert msg.raw["is_group"] is False


def test_dingtalk_build_rich_text_group_requires_at():
    channel = _build_channel(robot_code="robot-code")

    ignored = channel._build_message(
        {
            "msgId": "msg-group-1",
            "msgtype": "richText",
            "senderStaffId": "user-1",
            "conversationType": "2",
            "conversationId": "cid-group-1",
            "content": {"richText": [{"text": "群消息"}]},
        }
    )
    assert ignored is None

    accepted = channel._build_message(
        {
            "msgId": "msg-group-2",
            "msgtype": "richText",
            "senderStaffId": "user-1",
            "conversationType": "2",
            "conversationId": "cid-group-1",
            "atUsers": ["robot-code"],
            "content": {"richText": [{"text": "@"}, {"text": "机器人"}]},
        }
    )

    assert accepted is not None
    assert accepted.content == "@机器人"
    assert accepted.raw["is_group"] is True
    assert accepted.raw["at_users"] == ["robot-code"]


def test_dingtalk_build_audio_message_with_recognition():
    channel = _build_channel()

    msg = channel._build_message(
        {
            "msgId": "audio-1",
            "msgtype": "audio",
            "senderStaffId": "user-1",
            "conversationType": "1",
            "conversationId": "conv-1",
            "content": {"recognition": "帮我看看今天的任务"},
        }
    )

    assert msg is not None
    assert msg.content == "[语音消息]\n帮我看看今天的任务"
    assert msg.msg_type == "audio"


def test_dingtalk_build_audio_message_without_recognition():
    channel = _build_channel()

    msg = channel._build_message(
        {
            "msgId": "audio-2",
            "msgtype": "voice",
            "senderStaffId": "user-1",
            "conversationType": "1",
            "conversationId": "conv-1",
            "content": {},
        }
    )

    assert msg is not None
    assert msg.content == "[语音消息]"
    assert msg.msg_type == "voice"


def test_dingtalk_duplicate_message_is_ignored():
    channel = _build_channel()
    first = channel._build_message(
        {
            "msgId": "dup-1",
            "msgtype": "text",
            "senderStaffId": "user-1",
            "conversationType": "1",
            "text": {"content": "第一次"},
        }
    )
    second = channel._build_message(
        {
            "msgId": "dup-1",
            "msgtype": "text",
            "senderStaffId": "user-1",
            "conversationType": "1",
            "text": {"content": "第二次"},
        }
    )

    assert first is not None
    assert second is None


def test_dingtalk_access_token_cache_and_test_connection():
    channel = _build_channel()
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.url.path == "/v1.0/oauth2/accessToken"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["appKey"] == "app-key"
        assert payload["appSecret"] == "app-secret"
        return httpx.Response(200, json={"accessToken": "token-123", "expireIn": 7200})

    channel._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def _run():
        token1 = await channel._get_access_token()
        token2 = await channel._get_access_token()
        result = await channel.test_connection()
        await channel.stop()
        return token1, token2, result

    token1, token2, result = asyncio.run(_run())

    assert token1 == "token-123"
    assert token2 == "token-123"
    assert calls["count"] == 1
    assert result["ok"] is True


def test_dingtalk_handle_callback_dispatches_handler():
    channel = _build_channel()
    seen = {}

    async def handler(msg):
        seen["content"] = msg.content
        seen["sender_id"] = msg.sender_id
        return "已收到"

    channel.on_message(handler)

    async def _run():
        return await channel.handle_callback(
            {
                "msgId": "cb-1",
                "msgtype": "text",
                "senderStaffId": "staff-1",
                "conversationType": "1",
                "text": {"content": "回调消息"},
            }
        )

    reply = asyncio.run(_run())

    assert reply == "已收到"
    assert seen == {"content": "回调消息", "sender_id": "staff-1"}


def test_registry_can_register_dingtalk_channel():
    registry = PluginRegistry()
    channel = _build_channel()

    registry.register_channel(channel)

    assert registry.get_channel("dingtalk") is channel
    assert [item.name for item in registry.list_channels()] == ["dingtalk"]


def test_dingtalk_channel_exposes_contact_sync_provider():
    channel = _build_channel()

    provider = channel.get_sync_provider()

    assert provider is not None
    assert provider.platform == "dingtalk"


def test_dingtalk_contact_sync_provider_fetches_departments_and_members():
    channel = _build_channel()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "token-123", "expireIn": 7200})

        if request.url.path == "/topapi/v2/department/listsub":
            payload = json.loads(request.content.decode("utf-8"))
            dept_id = payload["dept_id"]
            if dept_id == 1:
                return httpx.Response(
                    200,
                    json={"errcode": 0, "result": [{"dept_id": 2, "name": "研发", "parent_id": 1}]},
                )
            return httpx.Response(200, json={"errcode": 0, "result": []})

        if request.url.path == "/topapi/user/listsimple":
            payload = json.loads(request.content.decode("utf-8"))
            dept_id = payload["dept_id"]
            if dept_id == 2:
                return httpx.Response(
                    200,
                    json={
                        "errcode": 0,
                        "result": {
                            "list": [{"userid": "user-1", "name": "张三"}],
                            "has_more": False,
                            "next_cursor": 0,
                        },
                    },
                )
            return httpx.Response(
                200,
                json={"errcode": 0, "result": {"list": [], "has_more": False, "next_cursor": 0}},
            )

        if request.url.path == "/topapi/v2/user/get":
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "result": {
                        "userid": "user-1",
                        "name": "张三",
                        "email": "zhangsan@example.com",
                        "mobile": "13800000000",
                        "title": "工程师",
                        "dept_id_list": [2],
                    },
                },
            )

        raise AssertionError(f"unexpected path: {request.url.path}")

    channel._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.dingtalk.com")
    provider = channel.get_sync_provider()

    async def _run():
        departments = await provider.fetch_departments()
        members = await provider.fetch_members()
        await channel.stop()
        return departments, members

    departments, members = asyncio.run(_run())

    assert [dept.dept_id for dept in departments] == ["1", "2"]
    assert len(members) == 1
    assert members[0].user_id == "user-1"
    assert members[0].department == "2"
    assert members[0].email == "zhangsan@example.com"


def test_dingtalk_send_message_tool_uses_bound_identity():
    session_factory = get_session_factory()

    async def _prepare():
        async with session_factory() as session:
            await session.execute(delete(PlatformIdentity).where(PlatformIdentity.platform == "dingtalk"))
            await session.execute(delete(Member).where(Member.id == "member-dingtalk-tool"))
            session.add(Member(id="member-dingtalk-tool", name="测试成员", status="active"))
            session.add(
                PlatformIdentity(
                    member_id="member-dingtalk-tool",
                    platform="dingtalk",
                    platform_user_id="ding-user-1",
                    platform_username="ding-user-1",
                    platform_display_name="测试成员",
                )
            )
            await session.commit()

    asyncio.run(_prepare())

    channel = _build_channel()
    seen = {}

    async def fake_send(target, message):
        seen["target"] = target
        seen["content"] = message.content
        seen["msg_type"] = message.msg_type

    channel.send = fake_send  # type: ignore[method-assign]
    tool = SendDingTalkMessageTool(channel=channel)

    result = asyncio.run(
        tool.execute(
            {
                "content": "你好，钉钉",
                "_member_id": "member-dingtalk-tool",
                "_caller_member_id": "member-dingtalk-tool",
            }
        )
    )

    payload = json.loads(result)
    assert payload["ok"] is True
    assert seen["target"] == "ding-user-1"
    assert seen["content"] == "你好，钉钉"
    assert seen["msg_type"] == "text"


def test_dingtalk_upload_media():
    channel = _build_channel()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "token-123", "expireIn": 7200})
        if request.url.path == "/media/upload":
            assert request.url.params.get("type") == "voice"
            assert request.url.params.get("access_token") == "token-123"
            return httpx.Response(200, json={"errcode": 0, "media_id": "media-1"})
        raise AssertionError(f"unexpected path: {request.url.path}")

    channel._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://oapi.dingtalk.com")

    async def _run():
        data = await channel.upload_media("voice", b"voice-bytes", "voice.amr")
        await channel.stop()
        return data

    result = asyncio.run(_run())

    assert result["media_id"] == "media-1"


def test_dingtalk_send_raises_on_business_error():
    channel = _build_channel()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "token-123", "expireIn": 7200})
        if request.url.path == "/v1.0/robot/oToMessages/batchSend":
            return httpx.Response(200, json={"errcode": 40035, "errmsg": "invalid user"})
        raise AssertionError(f"unexpected path: {request.url.path}")

    channel._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.dingtalk.com")

    async def _run():
        try:
            await channel.send("ding-user-1", Message(content="hello", channel="dingtalk"))
        finally:
            await channel.stop()

    with pytest.raises(RuntimeError, match="errcode=40035"):
        asyncio.run(_run())


def test_dingtalk_send_voice_tool_uses_tts_and_media_upload():
    session_factory = get_session_factory()

    async def _prepare():
        async with session_factory() as session:
            await session.execute(delete(PlatformIdentity).where(PlatformIdentity.platform == "dingtalk"))
            await session.execute(delete(Member).where(Member.id == "member-dingtalk-voice"))
            session.add(Member(id="member-dingtalk-voice", name="测试成员", status="active"))
            session.add(
                PlatformIdentity(
                    member_id="member-dingtalk-voice",
                    platform="dingtalk",
                    platform_user_id="ding-user-voice",
                    platform_username="ding-user-voice",
                    platform_display_name="测试成员",
                )
            )
            await session.commit()

    asyncio.run(_prepare())

    class _FakeTTS:
        available = True

        async def synthesize(self, text: str, **kwargs):
            assert text
            return b"mp3-bytes"

    channel = _build_channel()
    seen = {}

    async def fake_upload_media(media_type, file_content, file_name):
        seen["media_type"] = media_type
        seen["file_name"] = file_name
        seen["file_content"] = file_content
        return {"media_id": "media-voice-1"}

    async def fake_send(target, message):
        seen["target"] = target
        seen["msg_type"] = message.msg_type
        seen["media_id"] = message.raw["voice_data"]["media_id"]

    channel.upload_media = fake_upload_media  # type: ignore[method-assign]
    channel.send = fake_send  # type: ignore[method-assign]
    tool = SendDingTalkVoiceTool(channel=channel, tts_service=_FakeTTS())

    original_converter = SendDingTalkVoiceTool.execute.__globals__["_mp3_to_amr"]
    SendDingTalkVoiceTool.execute.__globals__["_mp3_to_amr"] = lambda _data: asyncio.sleep(0, result=b"amr-bytes")
    try:
        result = asyncio.run(
            tool.execute(
                {
                    "text": "你好，这是一条钉钉语音",
                    "_member_id": "member-dingtalk-voice",
                    "_caller_member_id": "member-dingtalk-voice",
                }
            )
        )
    finally:
        SendDingTalkVoiceTool.execute.__globals__["_mp3_to_amr"] = original_converter

    payload = json.loads(result)
    assert payload["ok"] is True
    assert seen["media_type"] == "voice"
    assert seen["file_name"] == "voice.amr"
    assert seen["file_content"] == b"amr-bytes"
    assert seen["target"] == "ding-user-voice"
    assert seen["msg_type"] == "voice"
    assert seen["media_id"] == "media-voice-1"


def test_dingtalk_send_message_tool_returns_error_when_channel_send_fails():
    channel = _build_channel()
    tool = SendDingTalkMessageTool(channel=channel)

    async def fake_send(_target, _message):
        raise RuntimeError("boom")

    channel.send = fake_send  # type: ignore[method-assign]

    result = asyncio.run(
        tool.execute(
            {
                "content": "hello",
                "user_id": "ding-user-1",
                "_member_id": "",
                "_caller_member_id": "",
            }
        )
    )

    payload = json.loads(result)
    assert payload["ok"] is False
    assert "boom" in payload["message"]


def test_dingtalk_stream_register_includes_card_callback_topic():
    channel = _build_channel()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={"endpoint": "wss://example.dingtalk.test/connect", "ticket": "ticket-1"},
        )

    channel._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def _run():
        endpoint, ticket = await channel._stream_register()
        await channel.stop()
        return endpoint, ticket

    endpoint, ticket = asyncio.run(_run())

    assert endpoint == "wss://example.dingtalk.test/connect"
    assert ticket == "ticket-1"
    subscriptions = seen["payload"]["subscriptions"]
    assert {"type": "CALLBACK", "topic": "/v1.0/card/instances/callback"} in subscriptions


def test_dingtalk_create_ai_card_uses_stringified_card_param_map():
    channel = _build_channel()
    channel.apply_config(
        {
            "message_type": "card",
            "card_template_id": "tpl-1.schema",
            "card_template_key": "content",
        }
    )
    calls = {"count": 0}
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "token-123", "expireIn": 7200})
        if request.url.path == "/v1.0/card/instances/createAndDeliver":
            seen["payload"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"success": True})
        raise AssertionError(f"unexpected path: {request.url.path}")

    channel._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def _run():
        card_id = await channel._create_ai_card("conv-1", False)
        await channel.stop()
        return card_id

    card_id = asyncio.run(_run())

    assert card_id.startswith("card_")
    card_param_map = seen["payload"]["cardData"]["cardParamMap"]
    assert card_param_map["content"] == ""
    assert json.loads(card_param_map["config"]) == {"autoLayout": True, "enableForward": True}
    assert seen["payload"]["imRobotOpenSpaceModel"] == {"supportForward": True}
    assert calls["count"] == 2


def test_dingtalk_private_card_uses_sender_id_as_target():
    channel = _build_channel()
    channel.apply_config(
        {
            "message_type": "card",
            "card_template_id": "tpl-1.schema",
            "card_template_key": "content",
        }
    )
    msg = channel._build_message(
        {
            "msgId": "private-1",
            "msgtype": "text",
            "senderStaffId": "user-1",
            "conversationType": "1",
            "conversationId": "conv-private-1",
            "text": {"content": "你好"},
        }
    )
    seen = {}

    async def fake_stream_handler(_msg):
        yield {"type": "text_delta", "text": "回"}
        yield {"type": "text", "text": "回复内容"}

    async def fake_create_ai_card(conversation_id: str, is_group: bool):
        seen["conversation_id"] = conversation_id
        seen["is_group"] = is_group
        return "card-1"

    async def fake_stream_ai_card(card_instance_id: str, content: str, finalize: bool = False, failed: bool = False):
        return True

    channel.set_stream_handler(fake_stream_handler)
    channel._create_ai_card = fake_create_ai_card  # type: ignore[method-assign]
    channel._stream_ai_card = fake_stream_ai_card  # type: ignore[method-assign]

    asyncio.run(channel._handle_stream_message(msg))

    assert seen["conversation_id"] == "user-1"
    assert seen["is_group"] is False
