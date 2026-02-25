"""Agent Runtime 测试"""

import pytest

from openvort.core.session import SessionStore
from openvort.plugin.base import BaseTool, Message
from openvort.plugin.registry import PluginRegistry


class TestSessionStore:
    """SessionStore 测试"""

    def test_get_empty_session(self):
        store = SessionStore()
        msgs = store.get_messages("wecom", "user1")
        assert msgs == []

    def test_append_and_get(self):
        store = SessionStore()
        store.append("wecom", "user1", {"role": "user", "content": "你好"})
        store.append("wecom", "user1", {"role": "assistant", "content": "你好！"})
        msgs = store.get_messages("wecom", "user1")
        assert len(msgs) == 2
        assert msgs[0]["content"] == "你好"

    def test_session_isolation(self):
        store = SessionStore()
        store.append("wecom", "user1", {"role": "user", "content": "A"})
        store.append("wecom", "user2", {"role": "user", "content": "B"})
        assert len(store.get_messages("wecom", "user1")) == 1
        assert len(store.get_messages("wecom", "user2")) == 1

    def test_trim(self):
        store = SessionStore(max_messages=5)
        for i in range(10):
            store.append("wecom", "user1", {"role": "user", "content": f"msg{i}"})
        msgs = store.get_messages("wecom", "user1")
        assert len(msgs) == 5
        assert msgs[0]["content"] == "msg5"

    def test_clear(self):
        store = SessionStore()
        store.append("wecom", "user1", {"role": "user", "content": "test"})
        store.clear("wecom", "user1")
        assert store.get_messages("wecom", "user1") == []

    def test_save_messages(self):
        store = SessionStore()
        messages = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
        ]
        store.save_messages("wecom", "user1", messages)
        assert store.get_messages("wecom", "user1") == messages


class TestPluginRegistry:
    """PluginRegistry 测试"""

    def test_register_tool(self):
        registry = PluginRegistry()

        class MockTool(BaseTool):
            name = "mock.test"
            description = "测试工具"

            def input_schema(self):
                return {"type": "object", "properties": {"q": {"type": "string"}}}

            async def execute(self, params):
                return f"result: {params.get('q', '')}"

        tool = MockTool()
        registry.register_tool(tool)

        assert registry.get_tool("mock.test") is tool
        assert len(registry.list_tools()) == 1

    def test_to_claude_tools(self):
        registry = PluginRegistry()

        class MockTool(BaseTool):
            name = "test.tool"
            description = "A test tool"

            def input_schema(self):
                return {"type": "object", "properties": {"x": {"type": "integer"}}}

            async def execute(self, params):
                return "ok"

        registry.register_tool(MockTool())
        tools = registry.to_claude_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "test.tool"
        assert tools[0]["description"] == "A test tool"
        assert "input_schema" in tools[0]

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        registry = PluginRegistry()

        class EchoTool(BaseTool):
            name = "echo"
            description = "Echo tool"

            def input_schema(self):
                return {"type": "object", "properties": {"msg": {"type": "string"}}}

            async def execute(self, params):
                return params.get("msg", "")

        registry.register_tool(EchoTool())
        result = await registry.execute_tool("echo", {"msg": "hello"})
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        registry = PluginRegistry()
        result = await registry.execute_tool("nonexistent", {})
        assert "未找到" in result


class TestMessage:
    """Message 模型测试"""

    def test_create_message(self, sample_message):
        assert sample_message.content == "帮我查一下我的任务"
        assert sample_message.channel == "wecom"
        assert sample_message.msg_type == "text"

    def test_default_values(self):
        msg = Message(content="test", sender_id="u1")
        assert msg.channel == ""
        assert msg.msg_type == "text"
        assert msg.images == []
        assert msg.raw == {}
