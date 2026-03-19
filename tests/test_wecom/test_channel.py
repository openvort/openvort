"""企微 Channel 测试"""

import pytest

from openvort.channels.wecom.channel import WeComChannel
from openvort.config.settings import WeComSettings


class TestWeComChannel:
    """WeComChannel 测试"""

    def test_not_configured(self):
        settings = WeComSettings(corp_id="", app_secret="")
        ch = WeComChannel(settings=settings)
        assert not ch.is_configured()

    def test_configured(self):
        settings = WeComSettings(corp_id="test_corp", app_secret="test_secret")
        ch = WeComChannel(settings=settings)
        assert ch.is_configured()

    def test_name(self):
        ch = WeComChannel()
        assert ch.name == "wecom"
        assert ch.display_name == "企业微信"

    def test_lazy_api_init(self):
        settings = WeComSettings(corp_id="corp", app_secret="secret", agent_id="1000")
        ch = WeComChannel(settings=settings)
        # api 应该是延迟初始化的
        assert ch._api is None
        api = ch.api
        assert api is not None
        assert ch._api is api  # 第二次访问应该返回同一个实例

    def test_on_message(self):
        ch = WeComChannel()

        async def handler(msg):
            return "ok"

        ch.on_message(handler)
        assert ch._handler is handler

    def test_aggregate_single(self):
        messages = [
            {"from_user": "u1", "msg_id": "1", "content": "hello", "msg_type": "text", "raw": {}},
        ]
        result = WeComChannel._aggregate(messages)
        assert len(result) == 1
        assert result[0].content == "hello"

    def test_aggregate_multiple(self):
        messages = [
            {"from_user": "u1", "msg_id": "1", "content": "line1", "msg_type": "text", "raw": {}},
            {"from_user": "u1", "msg_id": "2", "content": "line2", "msg_type": "text", "raw": {}},
            {"from_user": "u2", "msg_id": "3", "content": "other", "msg_type": "text", "raw": {}},
        ]
        result = WeComChannel._aggregate(messages)
        assert len(result) == 2

        # u1 的消息应该被聚合
        u1_msg = next(m for m in result if m.sender_id == "u1")
        assert "line1" in u1_msg.content
        assert "line2" in u1_msg.content

        # u2 的消息独立
        u2_msg = next(m for m in result if m.sender_id == "u2")
        assert u2_msg.content == "other"


class TestWeComCrypto:
    """加解密基础测试"""

    def test_import(self):
        from openvort.channels.wecom.crypto import WeComCrypto
        assert WeComCrypto is not None

    def test_verify_signature(self):
        from openvort.channels.wecom.crypto import WeComCrypto

        crypto = WeComCrypto(token="test_token", encoding_aes_key="a" * 43, corp_id="test_corp")
        # 签名验证是确定性的
        import hashlib
        items = sorted(["test_token", "123", "456", ""])
        expected = hashlib.sha1("".join(items).encode()).hexdigest()
        assert crypto.verify_signature(expected, "123", "456", "")
