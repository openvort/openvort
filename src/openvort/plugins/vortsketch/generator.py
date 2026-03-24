"""SketchGenerator — LLM-powered UI prototype generation engine."""

import re
from collections.abc import AsyncGenerator
from pathlib import Path

from openvort.core.engine.llm import LLMClient
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortsketch.generator")

_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "sketch.md").read_text(encoding="utf-8")

_SECTION_START_RE = re.compile(r"<!--\s*section:\s*([\w-]+)\s*-->")
_SECTION_END_RE = re.compile(r"<!--\s*/section:\s*([\w-]+)\s*-->")

_ITERATE_SECTION_RULES = """
## Iteration Mode — Section-Level Output

The current page has the following sections:
{section_outline}

IMPORTANT — you must follow this output format exactly:
1. First line: `SUMMARY: <1-2 sentence description of what you changed>`
2. Then output ONLY the modified section(s). For each modified section:
   ```
   SECTION: section_name
   <... the full updated HTML for this section, NOT including the <!-- section --> comment markers ...>
   /SECTION: section_name
   ```
3. Do NOT output the full HTML page. Only output the sections you actually changed.
4. Do NOT output unchanged sections.
5. If modifying multiple sections, output them one after another.

Example (modifying only the content section):
```
SUMMARY: Changed the data table to a card grid layout
SECTION: content
<main class="flex-1 p-6">
  <div class="grid grid-cols-3 gap-4">...</div>
</main>
/SECTION: content
```
"""

_SECTION_PATCH_RE = re.compile(
    r"SECTION:\s*([\w-]+)\s*\n(.*?)\n\s*/SECTION:\s*\1",
    re.DOTALL,
)

_HTML_TAG_RE = re.compile(r"<(?:div|span|header|main|aside|section|nav|body|html|head|table|form|ul|ol|footer|article)\b", re.IGNORECASE)


def _looks_like_html(text: str) -> bool:
    """Check if text looks like actual HTML, not just plain text."""
    t = text.strip()
    if t.startswith("<!") or t.startswith("<html"):
        return True
    return bool(_HTML_TAG_RE.search(t[:500]))


def _build_system_prompt(requirement_context: str = "") -> str:
    ctx = requirement_context or "No specific requirement provided. Generate based on the user's description."
    return _PROMPT_TEMPLATE.replace("{requirement_context}", ctx)


def _extract_html(text: str) -> tuple[str, str]:
    """Extract HTML and optional SUMMARY from LLM response.

    Returns (html, summary).
    """
    summary = ""
    lines = text.strip().splitlines()
    content_lines = []
    for line in lines:
        if line.startswith("SUMMARY:"):
            summary = line[len("SUMMARY:"):].strip()
        else:
            content_lines.append(line)

    raw = "\n".join(content_lines).strip()

    fence_match = re.search(r"```(?:html)?\s*\n(.*?)```", raw, re.DOTALL)
    if fence_match:
        raw = fence_match.group(1).strip()

    if not raw.startswith("<!") and not raw.startswith("<html"):
        doctype_idx = raw.find("<!DOCTYPE")
        if doctype_idx == -1:
            doctype_idx = raw.find("<html")
        if doctype_idx > 0:
            raw = raw[doctype_idx:]

    return raw, summary


def _build_user_content(text: str, images: list[dict] | None = None) -> str | list[dict]:
    """Build user message content, optionally with images (Anthropic format)."""
    if not images:
        return text
    content: list[dict] = []
    for img in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img.get("media_type", "image/png"),
                "data": img["data"],
            },
        })
    content.append({"type": "text", "text": text})
    return content


# ---- Section parsing / patching utilities ----


def parse_sections(html: str) -> dict[str, str]:
    """Parse HTML into named sections based on paired comment markers.

    Returns dict mapping section name to inner content (between start/end markers).
    """
    sections: dict[str, str] = {}
    for m in _SECTION_START_RE.finditer(html):
        name = m.group(1)
        start_end = m.end()
        end_m = _SECTION_END_RE.search(html, start_end)
        if end_m and end_m.group(1) == name:
            sections[name] = html[start_end:end_m.start()].strip()
    return sections


def replace_sections(html: str, patches: dict[str, str]) -> str:
    """Replace section content in HTML with patched content."""
    result = html
    for name, new_content in patches.items():
        start_tag = f"<!-- section: {name} -->"
        end_tag = f"<!-- /section: {name} -->"
        s = result.find(start_tag)
        e = result.find(end_tag)
        if s >= 0 and e > s:
            before = result[: s + len(start_tag)]
            after = result[e:]
            result = before + "\n" + new_content.strip() + "\n" + after
    return result


def wrap_sections_for_preview(html: str) -> str:
    """Wrap each section's content in a <div data-vort-section> for DOM hot-patching.

    Uses display:contents so the wrapper doesn't affect layout.
    """
    def _start_repl(m: re.Match) -> str:
        name = m.group(1)
        return f'{m.group(0)}\n<div data-vort-section="{name}" style="display:contents">'

    def _end_repl(m: re.Match) -> str:
        return f"</div>\n{m.group(0)}"

    result = _SECTION_START_RE.sub(_start_repl, html)
    result = _SECTION_END_RE.sub(_end_repl, result)
    return result


def _extract_section_patches(text: str) -> tuple[str, dict[str, str]]:
    """Extract SUMMARY and section patches from LLM iterate output.

    Returns (summary, {section_name: html_content}).
    """
    summary = ""
    for line in text.strip().splitlines():
        if line.startswith("SUMMARY:"):
            summary = line[len("SUMMARY:"):].strip()
            break

    patches: dict[str, str] = {}
    for m in _SECTION_PATCH_RE.finditer(text):
        name = m.group(1)
        content = m.group(2).strip()
        fence = re.search(r"```(?:html)?\s*\n(.*?)```", content, re.DOTALL)
        if fence:
            content = fence.group(1).strip()
        patches[name] = content

    return summary, patches


class SketchGenerator:
    """Orchestrates LLM calls to generate/iterate UI prototypes."""

    def __init__(self, llm: LLMClient):
        self._llm = llm

    async def generate_stream(
        self,
        description: str,
        requirement_context: str = "",
        images: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream-generate a new HTML prototype.

        Yields dicts: {"type": "chunk", "text": "..."} during generation,
        then {"type": "done", "html": "...", "summary": "...", "tokens": N}.
        """
        system = _build_system_prompt(requirement_context)
        user_content = _build_user_content(description, images)
        messages = [{"role": "user", "content": user_content}]

        async for event in self._stream_llm(system, messages, "已根据描述生成原型"):
            yield event

    async def iterate_stream(
        self,
        instruction: str,
        previous_html: str,
        requirement_context: str = "",
        images: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream-iterate on an existing prototype using section-level patching.

        If the previous HTML has section markers, uses section-level output mode
        (LLM only outputs modified sections). Falls back to full-page mode otherwise.
        """
        sections = parse_sections(previous_html)
        use_sections = len(sections) >= 2

        system = _build_system_prompt(requirement_context)

        if use_sections:
            outline = "\n".join(f"- {name}" for name in sections)
            system += _ITERATE_SECTION_RULES.replace("{section_outline}", outline)

        user_content = _build_user_content(instruction, images)
        messages = [
            {
                "role": "user",
                "content": f"Here is the current HTML prototype:\n\n```html\n{previous_html}\n```",
            },
            {
                "role": "assistant",
                "content": "I see the current prototype. What changes would you like me to make?",
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

        full_text = ""
        tokens = 0

        async with self._llm.stream(system=system, messages=messages) as stream:
            async for event in stream:
                if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                    chunk = event.delta.text
                    full_text += chunk
                    yield {"type": "chunk", "text": chunk}

            try:
                final = await stream.get_final_message()
                tokens = final.usage.input_tokens + final.usage.output_tokens
            except Exception:
                pass

        if use_sections:
            summary, patches = _extract_section_patches(full_text)
            if patches:
                patched_html = replace_sections(previous_html, patches)
                log.info("Section-level iterate: patched %d section(s): %s", len(patches), list(patches.keys()))
                yield {
                    "type": "done",
                    "html": patched_html,
                    "summary": summary or "已根据指令修改原型",
                    "tokens": tokens,
                    "patches": patches,
                }
                return

        log.info("Full-page iterate fallback")
        html, summary = _extract_html(full_text)
        if not _looks_like_html(html):
            log.warning("LLM returned non-HTML text, keeping previous version")
            html = ""
        yield {
            "type": "done",
            "html": html or previous_html,
            "summary": summary or "已根据指令修改原型",
            "tokens": tokens,
        }

    async def _stream_llm(
        self, system: str, messages: list[dict], default_summary: str
    ) -> AsyncGenerator[dict, None]:
        full_text = ""
        tokens = 0

        async with self._llm.stream(system=system, messages=messages) as stream:
            async for event in stream:
                if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                    chunk = event.delta.text
                    full_text += chunk
                    yield {"type": "chunk", "text": chunk}

            try:
                final = await stream.get_final_message()
                tokens = final.usage.input_tokens + final.usage.output_tokens
            except Exception:
                pass

        html, summary = _extract_html(full_text)
        if not summary:
            summary = default_summary

        yield {"type": "done", "html": html, "summary": summary, "tokens": tokens}
