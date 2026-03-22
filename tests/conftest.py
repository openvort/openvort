"""测试公共 fixtures"""

import pytest


@pytest.fixture
def sample_message():
    """示例企微消息"""
    from openvort.plugin.base import Message

    return Message(
        content="帮我查一下我的任务",
        sender_id="ZhangSan",
        sender_name="张三",
        channel="wecom",
        msg_type="text",
    )
