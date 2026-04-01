"""
MCP Server — expose OpenVort tools to Cursor / Claude Desktop via Streamable HTTP.

All registered tools (from core modules and plugins) are automatically available
as MCP tools. Internal tools (session management, IM channel tools) are excluded.
"""

from __future__ import annotations

import json as _json

from mcp.server.fastmcp import FastMCP
from mcp import types

from openvort.plugin.registry import PluginRegistry
from openvort.utils.logging import get_logger

log = get_logger("web.mcp")

EXCLUDED_TOOL_PREFIXES = (
    "sessions_",
    "send_wecom_",
    "send_feishu_",
    "send_dingtalk_",
)

EXCLUDED_TOOLS: set[str] = set()

_mcp_instance: FastMCP | None = None


_LOCAL_PATH_INDICATORS = ("C:", "D:", "E:", "/Users/", "/home/", "\\Users\\", "file://")


def _warn_local_paths(name: str, arguments: dict) -> None:
    """Log a warning if image_urls contain what look like local file paths."""
    urls = arguments.get("image_urls")
    if not urls or not isinstance(urls, list):
        return
    for url in urls:
        if not isinstance(url, str):
            continue
        decoded = url.replace("%5C", "\\").replace("%3A", ":")
        if any(decoded.startswith(p) for p in _LOCAL_PATH_INDICATORS):
            log.warning(
                f"MCP tool '{name}' received local path in image_urls "
                f"(will be filtered by tool): {url[:150]}"
            )
            break


def _should_expose(tool_name: str) -> bool:
    if tool_name in EXCLUDED_TOOLS:
        return False
    for prefix in EXCLUDED_TOOL_PREFIXES:
        if tool_name.startswith(prefix):
            return False
    return True


def create_mcp_server(registry: PluginRegistry) -> FastMCP:
    """Create MCP server that bridges OpenVort tools to MCP protocol."""
    global _mcp_instance

    mcp = FastMCP(
        "OpenVort",
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        host="0.0.0.0",
    )

    low = mcp._mcp_server

    @low.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        tools = []
        for t in registry.list_tools():
            if not _should_expose(t.name):
                continue
            tools.append(types.Tool(
                name=t.name,
                description=t.description or "",
                inputSchema=t.input_schema(),
            ))
        log.debug(f"MCP list_tools: {len(tools)} tools exposed")
        return tools

    @low.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        tool = registry.get_tool(name)
        if not tool:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
        if not _should_expose(name):
            return [types.TextContent(type="text", text=f"Tool not available via MCP: {name}")]
        _warn_local_paths(name, arguments)

        try:
            result = await tool.execute(arguments)
            return [types.TextContent(type="text", text=result)]
        except Exception as e:
            log.error(f"MCP tool '{name}' execution failed: {e}")
            return [types.TextContent(type="text", text=f"Tool execution failed: {e}")]

    _mcp_instance = mcp
    exposed = sum(1 for t in registry.list_tools() if _should_expose(t.name))
    log.info(f"MCP Server created: {exposed} tools exposed")
    return mcp


def get_mcp_instance() -> FastMCP | None:
    return _mcp_instance


class McpAuthMiddleware:
    """ASGI middleware that resolves MCP caller identity and injects _member_id
    directly into tools/call arguments.

    The MCP library processes tool calls in a background anyio task (via memory
    streams), so contextvars set here are NOT visible to the call_tool handler.
    We therefore patch the JSON-RPC request body before it reaches the MCP app.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_value = headers.get(b"authorization", b"").decode()
        client = scope.get("client")
        client_host = client[0] if client else None

        from openvort.web.mcp_auth import resolve_mcp_identity
        member_info = await resolve_mcp_identity(auth_value or None, client_host)

        if not member_info:
            await self.app(scope, receive, send)
            return

        member_id = member_info["member_id"]

        body_chunks: list[bytes] = []
        body_complete = False

        async def patched_receive():
            nonlocal body_complete
            message = await receive()
            if message["type"] != "http.request" or body_complete:
                return message

            body_chunks.append(message.get("body", b""))

            if message.get("more_body", False):
                return message

            body_complete = True
            raw = b"".join(body_chunks)
            try:
                data = _json.loads(raw)
                if isinstance(data, dict) and data.get("method") == "tools/call":
                    params = data.get("params")
                    if isinstance(params, dict):
                        if "arguments" not in params:
                            params["arguments"] = {}
                        params["arguments"]["_member_id"] = member_id
                        raw = _json.dumps(data).encode()
            except Exception:
                pass

            return {**message, "body": raw}

        await self.app(scope, patched_receive, send)
