"""master 节点命令黑名单——零 LLM 判据。

AI 员工绑定 autodev 的 master 节点后自带 node_shell / node_file_*；不拦的话它能绕过全部派发闸门
直接起 worker、读凭据文件。节点 config 里 `autodev_master: true` 时启用；其它节点不受影响。
黑名单是可扩展起点不是完备集——遇到新的绕法往这里加模式，别只在对话里绕过。
"""

from __future__ import annotations

import re

from openvort.utils.logging import get_logger

log = get_logger("core.node_guard")

# 命令面（node_shell）：整条命令任一处匹配即拒
SHELL_BLOCK = [
    (re.compile(r"worker\.sh"), "直接起 worker——派发只经自动交付闸门"),
    (re.compile(r"(^|[\s;&|(])docker(\s|$)"), "在 master 上操作 docker"),
    (re.compile(r"/home/autodev/\."), "访问 /home/autodev 下的隐藏目录（凭据落点）"),
    (re.compile(r"\.git-credentials|\.jira-cli|glab-cli|CodeBuddyExtension|\.opencodex/config\.json"), "访问凭据文件"),
    (re.compile(r"03_config/\.env"), "访问项目平台凭据文件"),
    (re.compile(r"/var/run/docker\.sock"), "访问 docker socket"),
]

# 路径面（node_file_read / node_file_write）
PATH_BLOCK = [
    (re.compile(r"/home/autodev/\."), "凭据落点目录"),
    (re.compile(r"\.git-credentials|\.jira-cli|glab-cli|CodeBuddyExtension|\.opencodex"), "凭据文件"),
    (re.compile(r"03_config/\.env"), "项目平台凭据文件"),
    (re.compile(r"worker\.sh|run-task\.sh|/data/autodev/build/"), "worker 脚本与镜像构建面"),
    (re.compile(r"/var/run/docker\.sock"), "docker socket"),
]


def is_master(node_config: dict | None) -> bool:
    return bool((node_config or {}).get("autodev_master"))


def check_shell(node_config: dict | None, command: str) -> str:
    """返回拒绝原因；空串 = 放行。"""
    if not is_master(node_config):
        return ""
    for pat, why in SHELL_BLOCK:
        if pat.search(command or ""):
            log.warning(f"master 节点命令被拒（{why}）: {command[:200]}")
            return f"该命令在 master 工作机上被拒绝：{why}。自动交付的派发与查询请用 autodev_* 工具或项目页。"
    return ""


def check_path(node_config: dict | None, path: str, *, write: bool) -> str:
    if not is_master(node_config):
        return ""
    for pat, why in PATH_BLOCK:
        if pat.search(path or ""):
            op = "写入" if write else "读取"
            log.warning(f"master 节点文件{op}被拒（{why}）: {path}")
            return f"该路径在 master 工作机上禁止{op}：{why}。"
    return ""
