"""Backward compatibility — re-exports from remote_work_tool."""
from openvort.core.remote_work_tool import (  # noqa: F401
    RemoteWorkTool as OpenClawWorkTool,
    RemoteWorkTool,
    get_remote_work_tools as get_openclaw_tools,
    get_remote_work_tools,
    set_remote_work_runtime as set_openclaw_tool_runtime,
    set_remote_work_runtime,
)
