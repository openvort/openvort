"""
OpenVort CLI

参考 OpenClaw 风格，提供项目初始化、服务启动、插件管理等命令。
"""

import asyncio
import os
import signal
from pathlib import Path

import click

from openvort import __version__

PID_FILE = Path.home() / ".openvort" / "openvort.pid"


def _is_process_alive(pid: int) -> bool:
    """检查进程是否存活"""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _graceful_kill(pid: int, timeout: float = 5.0) -> bool:
    """SIGTERM first, wait, then SIGKILL if needed. Returns True if process was stopped."""
    import time

    if not _is_process_alive(pid):
        return True

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return True

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_process_alive(pid):
            return True
        time.sleep(0.3)

    # Still alive — force kill
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
    except OSError:
        pass
    return not _is_process_alive(pid)


def _check_and_kill_existing():
    """检查并杀掉已有的 openvort 进程，写入当前 PID"""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if old_pid != os.getpid() and _is_process_alive(old_pid):
                click.echo(f"发现已有进程 (PID={old_pid})，正在终止...")
                killed = _graceful_kill(old_pid)
                click.echo(f"已终止旧进程 (PID={old_pid})" if killed else f"警告: 旧进程 {old_pid} 未能完全退出")
        except (ValueError, OSError):
            pass

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _cleanup_pid():
    """清理 PID 文件"""
    try:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            if pid == os.getpid():
                PID_FILE.unlink()
    except (ValueError, OSError):
        pass


def _run_async(coro):
    """在同步 CLI 中运行异步函数"""
    return asyncio.run(coro)


@click.group()
@click.version_option(__version__, prog_name="openvort")
def main():
    """OpenVort — 开源 AI 研发工作流引擎"""
    pass


# ---------------------------------------------------------------------------
# Register sub-commands
# ---------------------------------------------------------------------------
from openvort.cli.service import init_cmd, start_cmd, stop_cmd, restart_cmd  # noqa: E402
from openvort.cli.channels import channels  # noqa: E402
from openvort.cli.inspect import tools, plugins  # noqa: E402
from openvort.cli.agent import agent  # noqa: E402
from openvort.cli.contacts import contacts  # noqa: E402
from openvort.cli.marketplace import marketplace  # noqa: E402
from openvort.cli.skills import skills  # noqa: E402
from openvort.cli.pairing import pairing  # noqa: E402
from openvort.cli.coding import coding  # noqa: E402
from openvort.cli.doctor import doctor_cmd  # noqa: E402

main.add_command(init_cmd, "init")
main.add_command(start_cmd, "start")
main.add_command(stop_cmd, "stop")
main.add_command(restart_cmd, "restart")
main.add_command(channels)
main.add_command(tools)
main.add_command(plugins)
main.add_command(agent)
main.add_command(contacts)
main.add_command(marketplace)
main.add_command(skills)
main.add_command(pairing)
main.add_command(coding)
main.add_command(doctor_cmd, "doctor")

if __name__ == "__main__":
    main()
