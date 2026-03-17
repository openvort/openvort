"""LLM provider conversion tests."""

from openvort.core.engine.llm import OpenAICompatibleProvider


def _make_provider() -> OpenAICompatibleProvider:
    provider = object.__new__(OpenAICompatibleProvider)
    provider._convert_user_content_for_model = lambda content, model: content
    return provider


def test_openai_compatible_tool_call_message_uses_empty_string_content():
    provider = _make_provider()

    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_123",
                    "name": "node_shell",
                    "input": {"command": "pytest tests/"},
                }
            ],
        }
    ]

    converted = provider._convert_messages("system prompt", messages, "gpt-4o")

    assert converted[1]["role"] == "assistant"
    assert converted[1]["content"] == ""
    assert converted[1]["tool_calls"][0]["id"] == "call_123"


def test_openai_compatible_tool_call_message_keeps_text_content():
    provider = _make_provider()

    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "我来处理。"},
                {
                    "type": "tool_use",
                    "id": "call_456",
                    "name": "node_shell",
                    "input": {"command": "tail -100 /var/log/app.log"},
                },
            ],
        }
    ]

    converted = provider._convert_messages("system prompt", messages, "gpt-4o")

    assert converted[1]["content"] == "我来处理。"
    assert converted[1]["tool_calls"][0]["function"]["name"] == "node_shell"
