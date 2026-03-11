"""
Remote work AI Tool.

Allows AI employees to delegate work to their bound
remote node on a remote machine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from openvort.core.remote_node import RemoteNodeService
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

log = get_logger("core.remote_work_tool")

_service: RemoteNodeService | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_remote_work_runtime(
    service: RemoteNodeService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Inject runtime dependencies at startup."""
    global _service, _session_factory
    _service = service
    _session_factory = session_factory


class RemoteWorkTool(BaseTool):
    """Delegate work to a remote node bound to the current AI employee."""

    name = "remote_work"
    description = (
        "在 AI 员工绑定的远程电脑上执行工作任务。"
        "通过远程工作节点向远程机器发送指令，适用于编码、文件操作、命令执行等场景。"
        "需要 AI 员工已绑定远程工作节点。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "要在远程电脑上执行的工作指令（自然语言描述）",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数（默认 300，最大 600）",
                    "default": 300,
                },
            },
            "required": ["instruction"],
        }

    async def execute(self, params: dict) -> str:
        if not _service or not _session_factory:
            return "远程节点服务未初始化"

        instruction = params.get("instruction", "").strip()
        if not instruction:
            return "请提供工作指令"

        timeout = min(params.get("timeout", 300), 600)

        target_member_id = params.get("_target_member_id", "")
        if not target_member_id:
            return (
                "当前不在 AI 员工聊天上下文中，无法使用远程工作节点。\n"
                "请先与一个已绑定远程工作节点的 AI 员工对话。"
            )

        from sqlalchemy import select
        from openvort.contacts.models import Member

        node_id = ""
        member_name = ""
        member_post = ""
        async with _session_factory() as db:
            result = await db.execute(select(Member).where(Member.id == target_member_id))
            member = result.scalar_one_or_none()
            if member:
                node_id = member.remote_node_id or ""
                member_name = member.name
                member_post = member.post or ""

        if not node_id:
            return (
                "该 AI 员工未配置远程工作节点，无法执行远程任务。\n"
                "请管理员在后台「远程工作节点」中添加节点，"
                "并在「AI 员工」页面为该员工绑定节点。"
            )

        node = await _service.get_node(node_id)
        if not node:
            return f"绑定的远程工作节点（{node_id[:8]}...）不存在，请管理员重新配置。"

        if node.get("status") == "offline":
            return (
                f"远程节点「{node['name']}」当前离线（{node['gateway_url']}），"
                "请检查远程电脑是否开机且节点服务正在运行。"
            )

        context = {
            "employee_name": member_name,
            "employee_post": member_post,
        }

        result = await _service.send_instruction(
            node_id, instruction, context=context, timeout=timeout,
        )

        if result["ok"]:
            text = result.get("data", {}).get("text", "")
            if not text:
                text = "(远程节点执行完成，但未返回文本输出)"
            return f"远程节点「{node['name']}」执行结果：\n\n{text}"
        else:
            error = result.get("error", "unknown")
            message = result.get("message", "未知错误")
            partial_text = result.get("data", {}).get("text", "")
            if error == "timeout":
                hint = f"远程执行超时（{timeout}s），任务可能仍在运行。节点：{node['name']}"
                if partial_text:
                    hint += f"\n\n已收到的部分输出：\n{partial_text}"
                return hint
            elif error == "connect_error":
                return f"无法连接到远程节点「{node['name']}」: {message}"
            else:
                return f"远程执行失败：{message}"


def get_remote_work_tools() -> list[BaseTool]:
    """Return all remote work tools."""
    return [RemoteWorkTool()]
