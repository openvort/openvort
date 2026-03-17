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
        "在 AI 员工绑定的工作节点上执行工作任务。"
        "通过工作节点（Docker 容器或远程机器）发送指令，适用于编码、文件操作、命令执行等场景。"
        "需要 AI 员工已绑定工作节点。"
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
        log.info(f"remote_work called: target_member_id={target_member_id!r}")
        if not target_member_id:
            return (
                "当前不在 AI 员工聊天上下文中，无法使用工作节点。\n"
                "请先与一个已绑定工作节点的 AI 员工对话。"
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

        log.info(f"remote_work lookup: member={member_name!r}, node_id={node_id!r}")
        if not node_id:
            return (
                "该 AI 员工未配置工作节点，无法执行任务。\n"
                "请管理员在后台「工作节点」中添加节点，"
                "并在「AI 员工」页面为该员工绑定节点。"
            )

        node = await _service.get_node(node_id)
        if not node:
            return (
                f"绑定的工作节点（{node_id[:8]}...）不存在，请管理员重新配置。\n"
                "[FALLBACK] 节点不可用，请使用你的内置工具完成本次任务。"
            )

        node_status = node.get("status", "unknown")
        if node_status not in ("online", "running"):
            return (
                f"工作节点「{node['name']}」当前不可用（状态: {node_status}）。\n"
                "[FALLBACK] 请使用你的内置工具（如 browser_navigate、git_code_task 等）完成本次任务，"
                "简短告知用户节点暂时离线即可，不要反复提及。"
            )

        context = {
            "employee_name": member_name,
            "employee_post": member_post,
        }

        extra_sp = _build_node_system_prompt(node, member_name, member_post)

        import asyncio

        output_queue: asyncio.Queue | None = params.get("_output_queue")
        _prev_text = ""

        def _on_text(text: str) -> None:
            nonlocal _prev_text
            if output_queue is None:
                return
            delta = text[len(_prev_text):]
            _prev_text = text
            if delta:
                try:
                    output_queue.put_nowait(delta)
                except Exception:
                    pass

        result = await _service.send_instruction(
            node_id, instruction, context=context, timeout=timeout,
            on_text=_on_text, extra_system_prompt=extra_sp,
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
                return (
                    f"无法连接到远程节点「{node['name']}」: {message}\n"
                    "[FALLBACK] 节点连接失败，请使用你的内置工具完成本次任务，"
                    "简短告知用户节点暂时不可用即可。"
                )
            else:
                return f"远程执行失败：{message}"


def _build_node_system_prompt(node: dict, member_name: str, member_post: str) -> str:
    """Build the extra system prompt injected into the node AI.

    This makes the node AI an extension of the AI employee rather than
    an independent agent — it knows who it is, what environment it has,
    and how much autonomy it has.
    """
    node_type = node.get("node_type", "")
    config = node.get("config") or {}
    image = config.get("image", "")

    # Identity
    identity = f"你是「{member_name}」"
    if member_post:
        identity += f"（{member_post}）"
    identity += "，正在使用这台工作电脑完成同事交办的任务。"

    # Environment capabilities based on node type
    if node_type == "docker":
        env_section = """## 工作环境

你在一台 Docker 容器中工作，拥有 root 权限。
已预装：git, curl, python3, node/npm。
你可以自由使用 apt-get, npm, pip 安装任何需要的工具和依赖。"""
    else:
        env_section = """## 工作环境

你在一台远程工作机器上运行，可以执行命令和操作文件。"""

    autonomy_section = """## 自主权准则

你对这台工作电脑有完全的自主权，像一个真人员工使用自己的工作电脑一样。

### 遇到缺少工具时的处理原则
- **小依赖**（pip/npm 包、命令行工具等）：直接安装，不需要说明，装完继续执行任务
- **中等依赖**（Chromium/Playwright 等 100-500MB 级别）：在执行结果中简要说明"正在安装 XX，可能需要 1-2 分钟"，然后直接安装并继续执行
- **大型软件**（数 GB 级别的 SDK、数据库等）：在结果中说明需要安装什么、大约多大、需要多久，等待下一条指令确认后再装

### 禁止行为
- 不要因为缺少某个工具就放弃任务或降级处理（如用 curl 代替浏览器）
- 不要说"容器中没有 XX，无法完成"——你可以自己安装
- 不要每次都列出环境限制清单，专注于完成任务"""

    return f"""{identity}

{env_section}

{autonomy_section}"""


def get_remote_work_tools() -> list[BaseTool]:
    """Return all remote work tools."""
    return [RemoteWorkTool()]
