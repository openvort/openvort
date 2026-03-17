"""
Node tools for AI employees.

Provides atomic tools (shell, file read, file write) that let
AI employees directly operate their Docker work computers via
``docker exec``, replacing the old remote_work + OpenClaw approach.
"""

from __future__ import annotations

import asyncio
import json
import shlex
from typing import TYPE_CHECKING

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from openvort.core.execution.remote_node import RemoteNodeService
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = get_logger("core.node_tools")

_service: RemoteNodeService | None = None
_session_factory: "async_sessionmaker[AsyncSession] | None" = None


def set_node_tools_runtime(
    service: "RemoteNodeService",
    session_factory: "async_sessionmaker[AsyncSession]",
) -> None:
    """Inject runtime dependencies at startup."""
    global _service, _session_factory
    _service = service
    _session_factory = session_factory


def get_node_tools() -> list[BaseTool]:
    """Return all node tools for registration."""
    return [NodeShellTool(), NodeFileReadTool(), NodeFileWriteTool(), NodeBrowseTool(), NodeManageTool()]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate_output(output: str, max_lines: int = 50) -> str:
    """Truncate tool output, keeping the last *max_lines* lines."""
    lines = output.splitlines()
    if len(lines) <= max_lines:
        return output
    return (
        f"[输出共 {len(lines)} 行，显示最后 {max_lines} 行]\n"
        + "\n".join(lines[-max_lines:])
    )


async def _update_workspace_state(container_id: str, tool_name: str, params: dict) -> None:
    """Best-effort update of /workspace/.workspace_state.json after tool execution."""
    try:
        from openvort.core.execution.docker_executor import DockerExecutor

        update_script = """
import json, os, time
SF = "/workspace/.workspace_state.json"
try:
    st = json.load(open(SF)) if os.path.exists(SF) else {}
except Exception:
    st = {}
st.setdefault("repos", [])
st.setdefault("recent_files", [])
st.setdefault("installed_tools", [])
tool = os.environ.get("_TOOL", "")
cmd = os.environ.get("_CMD", "")
path = os.environ.get("_PATH", "")
if tool == "node_shell" and cmd:
    if "git clone" in cmd:
        parts = cmd.split()
        for i, p in enumerate(parts):
            if p == "clone" and i + 1 < len(parts):
                url = parts[i + 1]
                repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
                entry = {"path": f"/workspace/{repo_name}", "remote": url, "cloned_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                if not any(r.get("path") == entry["path"] for r in st["repos"]):
                    st["repos"].append(entry)
                break
    for kw in ["pip install", "npm install -g", "apt-get install"]:
        if kw in cmd:
            pkg = cmd.split(kw, 1)[1].strip().split()[0] if kw in cmd else ""
            if pkg and pkg not in st["installed_tools"]:
                st["installed_tools"].append(pkg)
elif tool == "node_file_write" and path:
    entry = {"path": path, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    st["recent_files"] = [f for f in st["recent_files"] if f.get("path") != path]
    st["recent_files"].append(entry)
    st["recent_files"] = st["recent_files"][-20:]
st["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
with open(SF, "w") as f:
    json.dump(st, f, ensure_ascii=False, indent=2)
"""
        env_cmd = params.get("command", "")
        env_path = params.get("path", "")
        full_cmd = (
            f'_TOOL={shlex.quote(tool_name)} '
            f'_CMD={shlex.quote(env_cmd)} '
            f'_PATH={shlex.quote(env_path)} '
            f'python3 -c {shlex.quote(update_script)}'
        )
        await DockerExecutor._exec_streaming(container_id, full_cmd, timeout=5)
    except Exception:
        pass


async def _resolve_container(params: dict) -> tuple[str, str]:
    """Look up the Docker container bound to the calling AI employee.

    Returns ``(container_id, error_message)``.  *error_message* is empty
    on success.
    """
    if not _service or not _session_factory:
        return "", "节点工具服务未初始化"

    target_member_id = params.get("_target_member_id", "")
    if not target_member_id:
        return "", (
            "当前不在 AI 员工聊天上下文中，无法使用工作电脑。\n"
            "请先与一个已绑定工作节点的 AI 员工对话。"
        )

    from sqlalchemy import select
    from openvort.contacts.models import Member

    node_id = ""
    async with _session_factory() as db:
        result = await db.execute(
            select(Member).where(Member.id == target_member_id)
        )
        member = result.scalar_one_or_none()
        if member:
            node_id = member.remote_node_id or ""

    if not node_id:
        return "", (
            "当前没有工作电脑，无法执行此操作。"
            "请先使用 node_manage 工具查询空闲工作电脑或创建一台新的，然后再重试。"
        )

    node = await _service.get_node(node_id)
    if not node:
        return "", (
            f"绑定的工作节点（{node_id[:8]}...）不存在，请管理员重新配置。"
        )

    config = node.get("config") or {}
    container_id = config.get("container_id", "")
    if not container_id:
        return "", "工作节点未关联 Docker 容器，请管理员检查节点配置。"

    node_status = node.get("status", "unknown")
    if node_status not in ("online", "running"):
        # Attempt auto-restart for stopped containers
        from openvort.core.execution.docker_executor import DockerExecutor

        executor = DockerExecutor()
        status_info = await executor.get_container_status(container_id)
        real_status = status_info.get("status", "unknown")

        if real_status in ("exited", "stopped"):
            restart_result = await executor.start_container(container_id)
            if restart_result.get("ok"):
                await asyncio.sleep(2)
                log.info(f"Auto-restarted container {container_id[:12]}")
                return container_id, ""
            return "", f"工作电脑重启失败: {restart_result.get('message', '')}"

        return "", (
            f"工作电脑「{node['name']}」当前不可用（状态: {node_status}）。\n"
            "请管理员检查工作节点状态。"
        )

    return container_id, ""


# ---------------------------------------------------------------------------
# NodeShellTool
# ---------------------------------------------------------------------------

class NodeShellTool(BaseTool):
    """Execute shell commands on the AI employee's work computer."""

    name = "node_shell"
    description = (
        "在你的工作电脑终端执行命令。"
        "适用于运行脚本、安装软件、git 操作、查看日志等一切终端操作。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                },
                "working_dir": {
                    "type": "string",
                    "description": "工作目录（默认 /workspace）",
                    "default": "/workspace",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数（默认 120，最大 600）",
                    "default": 120,
                },
            },
            "required": ["command"],
        }

    async def execute(self, params: dict) -> str:
        container_id, err = await _resolve_container(params)
        if err:
            return err

        command = params.get("command", "").strip()
        if not command:
            return "请提供要执行的命令"

        working_dir = params.get("working_dir", "/workspace").strip() or "/workspace"
        timeout = min(max(params.get("timeout", 120), 5), 600)

        full_cmd = f"cd {shlex.quote(working_dir)} && {command}"

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

        from openvort.core.execution.docker_executor import DockerExecutor

        try:
            result = await DockerExecutor._exec_streaming(
                container_id, full_cmd, timeout=timeout, on_text=_on_text,
            )
        except asyncio.TimeoutError:
            return f"命令执行超时（{timeout}s）。命令可能仍在容器中运行。"
        except asyncio.CancelledError:
            raise

        combined = result["stdout"]
        if result["stderr"]:
            combined = (combined + "\n" + result["stderr"]) if combined else result["stderr"]

        truncated = _truncate_output(combined.strip(), max_lines=50)

        asyncio.ensure_future(_update_workspace_state(container_id, "node_shell", params))

        return f"[exit_code={result['exit_code']}]\n{truncated}" if truncated else f"[exit_code={result['exit_code']}]"


# ---------------------------------------------------------------------------
# NodeFileReadTool
# ---------------------------------------------------------------------------

class NodeFileReadTool(BaseTool):
    """Read file contents from the AI employee's work computer."""

    name = "node_file_read"
    description = (
        "读取你工作电脑上的文件内容。"
        "支持指定行范围，适用于查看代码、配置文件、日志等。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "offset": {
                    "type": "integer",
                    "description": "起始行号（从 1 开始，可选）",
                },
                "limit": {
                    "type": "integer",
                    "description": "读取行数（默认 200）",
                    "default": 200,
                },
            },
            "required": ["path"],
        }

    async def execute(self, params: dict) -> str:
        container_id, err = await _resolve_container(params)
        if err:
            return err

        path = params.get("path", "").strip()
        if not path:
            return "请提供文件路径"

        offset = params.get("offset")
        limit = params.get("limit", 200) or 200
        limit = min(max(limit, 1), 2000)

        from openvort.core.execution.docker_executor import DockerExecutor

        # Check if file exists
        check_cmd = f"test -f {shlex.quote(path)} && echo EXISTS || echo NOTFOUND"
        try:
            check = await DockerExecutor._exec_streaming(
                container_id, check_cmd, timeout=5,
            )
            if "NOTFOUND" in check["stdout"]:
                return f"文件不存在: {path}"
        except Exception:
            pass

        if offset and offset > 0:
            end_line = offset + limit - 1
            cmd = f"sed -n '{offset},{end_line}p' {shlex.quote(path)}"
        else:
            offset = 1
            cmd = f"head -n {limit} {shlex.quote(path)}"

        try:
            result = await DockerExecutor._exec_streaming(
                container_id, cmd, timeout=15,
            )
        except asyncio.TimeoutError:
            return f"读取文件超时: {path}"
        except asyncio.CancelledError:
            raise

        if result["exit_code"] != 0:
            err_msg = result["stderr"].strip() or result["stdout"].strip()
            return f"读取文件失败: {err_msg or '未知错误'}"

        content = result["stdout"]
        if not content:
            return f"文件为空: {path}"

        # Add line numbers
        lines = content.splitlines()
        numbered = []
        for i, line in enumerate(lines, start=offset):
            numbered.append(f"{i:>6}|{line}")

        output = "\n".join(numbered)

        # Check if file has more lines
        total_cmd = f"wc -l < {shlex.quote(path)}"
        try:
            total_result = await DockerExecutor._exec_streaming(
                container_id, total_cmd, timeout=5,
            )
            total_lines = int(total_result["stdout"].strip())
            shown_end = offset + len(lines) - 1
            if shown_end < total_lines:
                output += f"\n\n[文件共 {total_lines} 行，已显示 {offset}-{shown_end}]"
        except Exception:
            pass

        return output


# ---------------------------------------------------------------------------
# NodeFileWriteTool
# ---------------------------------------------------------------------------

class NodeFileWriteTool(BaseTool):
    """Create or modify files on the AI employee's work computer."""

    name = "node_file_write"
    description = (
        "在你的工作电脑上创建或修改文件。"
        "自动创建父目录。适用于写代码、修改配置等。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "content": {
                    "type": "string",
                    "description": "文件内容",
                },
                "append": {
                    "type": "boolean",
                    "description": "是否追加（默认覆盖写入）",
                    "default": False,
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, params: dict) -> str:
        container_id, err = await _resolve_container(params)
        if err:
            return err

        path = params.get("path", "").strip()
        content = params.get("content", "")
        append = params.get("append", False)

        if not path:
            return "请提供文件路径"

        from openvort.core.execution.docker_executor import DockerExecutor

        # Ensure parent directory exists
        parent_dir = "/".join(path.rsplit("/", 1)[:-1])
        if parent_dir:
            try:
                await DockerExecutor._exec_streaming(
                    container_id, f"mkdir -p {shlex.quote(parent_dir)}", timeout=10,
                )
            except Exception:
                pass

        # Write file via stdin to avoid shell escaping issues
        tee_flag = "-a" if append else ""
        tee_cmd = f"tee {tee_flag} {shlex.quote(path)}"

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", "-i", container_id, "sh", "-c", tee_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(
                proc.communicate(input=content.encode("utf-8")),
                timeout=30,
            )
            if proc.returncode != 0:
                err_msg = stderr.decode(errors="replace").strip()
                return f"写入文件失败: {err_msg or '未知错误'}"
        except asyncio.TimeoutError:
            return f"写入文件超时: {path}"
        except asyncio.CancelledError:
            raise

        line_count = len(content.splitlines()) or 1
        action = "追加" if append else "写入"

        asyncio.ensure_future(_update_workspace_state(container_id, "node_file_write", params))

        return f"文件已{action}: {path} ({line_count} 行)"


# ---------------------------------------------------------------------------
# NodeBrowseTool
# ---------------------------------------------------------------------------

_BROWSER_SCRIPT = r'''
import asyncio, json, sys, base64

async def main():
    params = json.loads(sys.argv[1])
    action = params.get("action", "")
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(json.dumps({"ok": False, "error": "Playwright is not installed. Install it with: pip install playwright && playwright install chromium"}))
        return

    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Cannot connect to browser CDP on port 9222: {e}"}))
        await pw.stop()
        return

    contexts = browser.contexts
    if contexts and contexts[0].pages:
        page = contexts[0].pages[0]
    else:
        ctx = await browser.new_context() if not contexts else contexts[0]
        page = await ctx.new_page()

    try:
        if action == "navigate":
            url = params.get("url", "")
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = await page.title()
            status = resp.status if resp else 0
            print(json.dumps({"ok": True, "title": title, "status": status, "url": url}))
        elif action == "screenshot":
            full_page = params.get("full_page", False)
            data = await page.screenshot(full_page=full_page)
            print("[screenshot]" + base64.b64encode(data).decode())
        elif action == "click":
            selector = params.get("selector", "")
            await page.click(selector, timeout=5000)
            await page.wait_for_timeout(500)
            title = await page.title()
            print(json.dumps({"ok": True, "clicked": selector, "title": title}))
        elif action == "type":
            selector = params.get("selector", "")
            text = params.get("text", "")
            await page.fill(selector, text, timeout=5000)
            print(json.dumps({"ok": True, "typed": len(text), "selector": selector}))
        elif action == "get_text":
            selector = params.get("selector", "body")
            text = await page.inner_text(selector)
            print(text[:5000])
        else:
            print(json.dumps({"ok": False, "error": f"Unknown action: {action}"}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
    finally:
        await pw.stop()

asyncio.run(main())
'''


class NodeBrowseTool(BaseTool):
    """Operate the browser on the AI employee's work computer."""

    name = "node_browse"
    description = (
        "在你的工作电脑上使用浏览器。"
        "支持导航到网页、截图、点击元素、输入文本、提取页面文字。"
        "需要工作电脑安装了浏览器（browser-sandbox 镜像）。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型: navigate(导航) / screenshot(截图) / click(点击) / type(输入) / get_text(提取文字)",
                    "enum": ["navigate", "screenshot", "click", "type", "get_text"],
                },
                "url": {
                    "type": "string",
                    "description": "navigate 时必填: 要访问的 URL",
                },
                "selector": {
                    "type": "string",
                    "description": "click/type 时必填: CSS 选择器",
                },
                "text": {
                    "type": "string",
                    "description": "type 时必填: 要输入的文本",
                },
                "full_page": {
                    "type": "boolean",
                    "description": "screenshot 时可选: 是否截取整个页面",
                    "default": False,
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        container_id, err = await _resolve_container(params)
        if err:
            return err

        action = params.get("action", "").strip()
        if not action:
            return "请指定操作类型 (navigate/screenshot/click/type/get_text)"

        script_params = {
            "action": action,
            "url": params.get("url", ""),
            "selector": params.get("selector", ""),
            "text": params.get("text", ""),
            "full_page": params.get("full_page", False),
        }

        from openvort.core.execution.docker_executor import DockerExecutor

        escaped_params = json.dumps(script_params, ensure_ascii=False).replace("'", "'\\''")
        cmd = f"python3 -c '{_BROWSER_SCRIPT}' '{escaped_params}'"

        try:
            result = await DockerExecutor._exec_streaming(
                container_id, cmd, timeout=60,
            )
        except asyncio.TimeoutError:
            return "浏览器操作超时 (60s)"
        except asyncio.CancelledError:
            raise

        output = result["stdout"].strip()
        if result["exit_code"] != 0:
            stderr = result["stderr"].strip()
            if "playwright" in stderr.lower() or "chromium" in stderr.lower():
                return (
                    "工作电脑未安装浏览器环境。\n"
                    "需要使用浏览器镜像（openvort/browser-sandbox）或手动安装: "
                    "pip install playwright && playwright install chromium"
                )
            return f"浏览器操作失败: {stderr or output}"

        if not output:
            return "浏览器操作完成，但未返回输出"

        return output


# ---------------------------------------------------------------------------
# NodeManageTool
# ---------------------------------------------------------------------------

class NodeManageTool(BaseTool):
    """Manage work computer (node) for the AI employee: list, create, bind."""

    name = "node_manage"
    description = (
        "管理你的工作电脑。可以查看空闲可用的工作电脑、创建新电脑并绑定、"
        "或绑定一台已有的空闲电脑。当你发现没有工作电脑时应主动使用此工具。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "操作类型:\n"
                        "- list_available: 查询当前空闲（未被任何 AI 员工使用）的工作电脑\n"
                        "- create_and_bind: 创建一台新工作电脑并自动绑定给你\n"
                        "- bind_existing: 将一台已有的空闲工作电脑绑定给你"
                    ),
                    "enum": ["list_available", "create_and_bind", "bind_existing"],
                },
                "name": {
                    "type": "string",
                    "description": "create_and_bind 时必填: 工作电脑名称",
                },
                "image": {
                    "type": "string",
                    "description": "create_and_bind 时可选: Docker 镜像（默认 python:3.11-slim）",
                    "default": "python:3.11-slim",
                },
                "node_id": {
                    "type": "string",
                    "description": "bind_existing 时必填: 要绑定的工作电脑 ID",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        if not _service or not _session_factory:
            return "节点工具服务未初始化"

        target_member_id = params.get("_target_member_id", "")
        if not target_member_id:
            return "当前不在 AI 员工聊天上下文中，无法管理工作电脑。"

        action = params.get("action", "").strip()

        if action == "list_available":
            return await self._list_available(target_member_id)
        elif action == "create_and_bind":
            name = params.get("name", "").strip()
            image = params.get("image", "python:3.11-slim").strip() or "python:3.11-slim"
            if not name:
                return "请提供工作电脑名称（name 参数）"
            return await self._create_and_bind(target_member_id, name, image)
        elif action == "bind_existing":
            node_id = params.get("node_id", "").strip()
            if not node_id:
                return "请提供要绑定的工作电脑 ID（node_id 参数）"
            return await self._bind_existing(target_member_id, node_id)
        else:
            return f"未知操作: {action}，支持: list_available / create_and_bind / bind_existing"

    async def _list_available(self, member_id: str) -> str:
        """List nodes not bound to any AI employee."""
        from sqlalchemy import select, not_
        from openvort.db.models import RemoteNode
        from openvort.contacts.models import Member

        async with _session_factory() as db:
            bound_ids_q = select(Member.remote_node_id).where(
                Member.remote_node_id.isnot(None),
                Member.remote_node_id != "",
            )
            bound_result = await db.execute(bound_ids_q)
            bound_ids = {row[0] for row in bound_result.fetchall()}

            all_nodes_q = select(RemoteNode).order_by(RemoteNode.created_at.desc())
            nodes_result = await db.execute(all_nodes_q)
            all_nodes = nodes_result.scalars().all()

        available = []
        for n in all_nodes:
            if n.id in bound_ids:
                continue
            config = {}
            try:
                config = json.loads(n.config) if n.config else {}
            except Exception:
                pass
            available.append({
                "id": n.id,
                "name": n.name,
                "status": n.status,
                "image": config.get("image", ""),
            })

        if not available:
            return json.dumps({
                "available_count": 0,
                "nodes": [],
                "hint": "没有空闲工作电脑，可以用 create_and_bind 创建一台新的。",
            }, ensure_ascii=False)

        return json.dumps({
            "available_count": len(available),
            "nodes": available,
            "hint": "可以用 bind_existing 绑定其中一台，或用 create_and_bind 新建。",
        }, ensure_ascii=False)

    async def _create_and_bind(self, member_id: str, name: str, image: str) -> str:
        """Create a new Docker node and bind it to the AI employee."""
        try:
            node = await _service.create_docker_node(name=name, image=image)
        except Exception as e:
            return f"创建工作电脑失败: {e}"

        create_result = node.pop("_create_result", {})
        if not create_result.get("ok"):
            return f"创建工作电脑失败: {create_result.get('message', '未知错误')}"

        node_id = node.get("id", "")
        if not node_id:
            return "创建工作电脑失败: 未获取到节点 ID"

        from openvort.contacts.models import Member

        try:
            async with _session_factory() as db:
                m = await db.get(Member, member_id)
                if m:
                    m.remote_node_id = node_id
                    await db.commit()
                    log.info(f"Node {node_id} created and bound to member {member_id}")
                else:
                    return f"工作电脑已创建（{name}），但未找到 AI 员工记录，绑定失败。"
        except Exception as e:
            return f"工作电脑已创建（{name}），但绑定失败: {e}"

        return json.dumps({
            "ok": True,
            "message": f"工作电脑「{name}」已创建并绑定成功，现在可以使用 node_shell 等工具了。",
            "node_id": node_id,
            "node_name": name,
            "image": image,
        }, ensure_ascii=False)

    async def _bind_existing(self, member_id: str, node_id: str) -> str:
        """Bind an existing unoccupied node to the AI employee."""
        from sqlalchemy import select
        from openvort.contacts.models import Member
        from openvort.db.models import RemoteNode

        async with _session_factory() as db:
            node = await db.get(RemoteNode, node_id)
            if not node:
                return f"工作电脑 {node_id} 不存在"

            occupied_q = select(Member).where(
                Member.remote_node_id == node_id,
                Member.remote_node_id != "",
            )
            occupied_result = await db.execute(occupied_q)
            occupier = occupied_result.scalar_one_or_none()
            if occupier:
                return f"工作电脑「{node.name}」已被 {occupier.name} 使用，请选择其他节点或新建。"

            m = await db.get(Member, member_id)
            if not m:
                return "未找到 AI 员工记录，绑定失败。"

            m.remote_node_id = node_id
            await db.commit()
            log.info(f"Node {node_id} bound to member {member_id}")

        return json.dumps({
            "ok": True,
            "message": f"已绑定工作电脑「{node.name}」，现在可以使用 node_shell 等工具了。",
            "node_id": node_id,
            "node_name": node.name,
        }, ensure_ascii=False)
