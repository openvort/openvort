"""
MCP Server — expose OpenVort tools to Cursor / Claude Desktop via Streamable HTTP.

All registered tools (from core modules and plugins) are automatically available
as MCP tools. Internal tools (session management, IM channel tools) are excluded.
"""

from __future__ import annotations

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

EXCLUDED_TOOLS = {
    "setup_complete",
}

_mcp_instance: FastMCP | None = None


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
