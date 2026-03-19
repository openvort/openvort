"""
Think-tag parser for streaming LLM output.

Separates visible content from thinking content enclosed in
<think>/<thinking>/<thought> tags.  Handles streaming (unclosed tags),
ignores tags inside code blocks.

Ported from @sunnoy/wecom OpenClaw plugin think-parser.js.
"""

from __future__ import annotations

import re

_OPEN_TAGS = ("think", "thinking", "thought")
_OPEN_PATTERN = re.compile(
    r"<(" + "|".join(_OPEN_TAGS) + r")>", re.IGNORECASE
)
_CLOSE_PATTERN = re.compile(
    r"</(" + "|".join(_OPEN_TAGS) + r")>", re.IGNORECASE
)
_CODE_BLOCK = re.compile(r"```")


def parse_thinking_content(text: str) -> tuple[str, str, bool]:
    """Parse text to separate visible content from thinking content.

    Returns:
        (visible, thinking, is_thinking)
        - visible: text with thinking blocks removed
        - thinking: accumulated thinking content
        - is_thinking: True if currently inside an unclosed think tag
    """
    if not text:
        return ("", "", False)

    visible_parts: list[str] = []
    thinking_parts: list[str] = []
    in_code_block = False
    in_think = False
    pos = 0

    while pos < len(text):
        code_match = _CODE_BLOCK.search(text, pos)
        if in_code_block:
            if code_match:
                end = code_match.end()
                if in_think:
                    thinking_parts.append(text[pos:end])
                else:
                    visible_parts.append(text[pos:end])
                pos = end
                in_code_block = False
            else:
                if in_think:
                    thinking_parts.append(text[pos:])
                else:
                    visible_parts.append(text[pos:])
                break

        elif in_think:
            close_match = _CLOSE_PATTERN.search(text, pos)
            code_first = code_match and (not close_match or code_match.start() < close_match.start())
            if code_first:
                thinking_parts.append(text[pos:code_match.end()])
                pos = code_match.end()
                in_code_block = True
            elif close_match:
                thinking_parts.append(text[pos:close_match.start()])
                pos = close_match.end()
                in_think = False
            else:
                thinking_parts.append(text[pos:])
                break

        else:
            open_match = _OPEN_PATTERN.search(text, pos)
            code_first = code_match and (not open_match or code_match.start() < open_match.start())
            if code_first:
                visible_parts.append(text[pos:code_match.end()])
                pos = code_match.end()
                in_code_block = True
            elif open_match:
                visible_parts.append(text[pos:open_match.start()])
                pos = open_match.end()
                in_think = True
            else:
                visible_parts.append(text[pos:])
                break

    visible = "".join(visible_parts).strip()
    thinking = "".join(thinking_parts).strip()
    return (visible, thinking, in_think)
