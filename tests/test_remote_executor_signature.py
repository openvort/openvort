"""RemoteNodeExecutor 协议与各实现的签名对等。

RemoteNodeService.send_instruction 把 extra_system_prompt 原样透传给 executor；
实现少一个关键字参数就是运行期 TypeError，而不是启动期报错。
"""

import inspect

import pytest

from openvort.core.execution.docker_executor import DockerExecutor
from openvort.core.execution.remote_executor import RemoteNodeExecutor

IMPLEMENTATIONS = [DockerExecutor]


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_send_instruction_accepts_every_protocol_keyword(impl):
    proto = inspect.signature(RemoteNodeExecutor.send_instruction).parameters
    actual = inspect.signature(impl.send_instruction).parameters
    missing = [
        name for name, p in proto.items()
        if p.kind is inspect.Parameter.KEYWORD_ONLY and name not in actual
    ]
    assert not missing, f"{impl.__name__}.send_instruction 缺协议关键字参数: {missing}"


async def test_docker_send_instruction_tolerates_extra_system_prompt():
    # container_id 为空时在任何 docker 调用之前就返回，测试不依赖本机 docker
    result = await DockerExecutor().send_instruction(
        "", "", "echo hi", extra_system_prompt="ignored for shell nodes",
    )
    assert result == {
        "ok": False, "error": "node_not_configured", "message": "容器 ID 未设置",
    }
