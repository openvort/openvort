"""Remote work tool tests."""

from types import SimpleNamespace

import pytest

from openvort.core import remote_work_tool
from openvort.core.remote_work_tool import RemoteWorkTool


class _FakeResult:
    def __init__(self, member):
        self._member = member

    def scalar_one_or_none(self):
        return self._member


class _FakeDbSession:
    def __init__(self, member):
        self._member = member

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _stmt):
        return _FakeResult(self._member)


class _FakeRemoteNodeService:
    def __init__(self):
        self.send_called = False

    async def get_node(self, node_id: str):
        return {
            "id": node_id,
            "name": "macmini",
            "gateway_url": "http://example.test",
            "status": "offline",
        }

    async def send_instruction(self, node_id: str, instruction: str, *, context=None, timeout=300):
        self.send_called = True
        return {
            "ok": True,
            "data": {
                "text": f"done: {instruction}",
                "status": "ok",
            },
        }


@pytest.mark.asyncio
async def test_remote_work_does_not_short_circuit_on_stale_offline_status(monkeypatch):
    member = SimpleNamespace(
        id="member-1",
        remote_node_id="node-1",
        name="测试员工",
        post="developer",
    )
    service = _FakeRemoteNodeService()

    monkeypatch.setattr(remote_work_tool, "_service", service)
    monkeypatch.setattr(remote_work_tool, "_session_factory", lambda: _FakeDbSession(member))

    result = await RemoteWorkTool().execute({
        "instruction": "run tests",
        "_target_member_id": member.id,
    })

    assert service.send_called is True
    assert "远程节点「macmini」执行结果" in result
    assert "done: run tests" in result
