"""master 节点黑名单：零 LLM 判据，只对 config.autodev_master=true 的节点生效。"""

import pytest

from openvort.core.execution import node_guard, node_tools

MASTER = {"container_id": "cid", "autodev_master": True}
PLAIN = {"container_id": "cid"}


@pytest.mark.parametrize("cmd", [
    "bash /data/autodev/build/v4/worker.sh TPYBX-1 --repo /data/autodev/repos/cpic",
    "docker run --rm autodev-worker:current",
    "cd /tmp && docker ps",
    "cat /home/autodev/.jira-cli/config.json",
    "cat ~/.git-credentials",
    "cat /data/autodev/repos/cpic/03_config/.env",
    "ls /var/run/docker.sock",
])
def test_master_shell_blocks_worker_docker_and_credentials(cmd):
    assert node_guard.check_shell(MASTER, cmd)


@pytest.mark.parametrize("cmd", [
    "python3 /data/autodev/bin/usage-report.py --json",
    "ls /data/autodev/state/runs",
    "git -C /data/autodev/repos/cpic log --oneline -3",
    "jira --json issue list -p TPYBX --max 5",
])
def test_master_shell_allows_data_processing(cmd):
    assert node_guard.check_shell(MASTER, cmd) == ""


def test_plain_node_is_untouched():
    assert node_guard.check_shell(PLAIN, "bash worker.sh X-1 --repo /r") == ""
    assert node_guard.check_shell(None, "docker ps") == ""
    assert node_guard.check_path(PLAIN, "/home/autodev/.jira-cli/config.json", write=False) == ""


@pytest.mark.parametrize("path", [
    "/home/autodev/.jira-cli/config.json", "/home/autodev/.git-credentials",
    "/data/autodev/repos/cpic/03_config/.env", "/data/autodev/build/v4/worker.sh",
])
def test_master_path_blocks(path):
    assert node_guard.check_path(MASTER, path, write=False)
    assert node_guard.check_path(MASTER, path, write=True)


def test_master_path_allows_logs():
    assert node_guard.check_path(MASTER, "/data/autodev/state/runs/X-1-20260907-1/logs/finish.log", write=False) == ""


async def test_node_shell_tool_refuses_before_exec(monkeypatch):
    async def fake_resolve(params):
        params["_node_config"] = MASTER
        return "cid", ""

    calls = []

    async def fake_exec(cid, cmd, timeout=120, on_text=None):
        calls.append(cmd)
        return {"stdout": "", "stderr": "", "exit_code": 0}

    monkeypatch.setattr(node_tools, "_resolve_container", fake_resolve)
    from openvort.core.execution.docker_executor import DockerExecutor
    monkeypatch.setattr(DockerExecutor, "_exec_streaming", staticmethod(fake_exec))

    tool = node_tools.NodeShellTool()
    out = await tool.execute({"command": "bash /data/autodev/build/v4/worker.sh TPYBX-1 --repo /x",
                              "_target_member_id": "m1"})
    assert "被拒绝" in out and calls == []

    out2 = await tool.execute({"command": "ls /data/autodev/state/runs", "_target_member_id": "m1"})
    assert out2.startswith("[exit_code=0]") and len(calls) == 1
