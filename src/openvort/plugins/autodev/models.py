"""AutoDev models — 项目级派发配置 + 每次 worker 运行的记录。

两张表都挂在 VortFlow 项目上：一个项目 = 一份派发配置 = 一条 Jira 投影队列 = 一个交付仓。
worker 本身不是节点（它是 `docker run --rm` 的一次运行），只有 master 是 RemoteNode——
master 不按项目绑定，它是全局 AI 员工绑定的工作机（Member.remote_node_id）。
slot 上限不在这里——它是 master 节点 config 里的 `max_slots`，同机资源按节点共享。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class AutodevProject(Base):
    """项目级派发配置。通用密钥（Jira / GitLab / CodeBuddy / ocx）不在这里，仍是 master 上的只读文件。"""

    __tablename__ = "autodev_projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("flow_projects.id"), unique=True, index=True
    )
    # 交付仓在宿主上的绝对路径（主仓，不是 worktree）；kit 仓须在同父目录
    repo_path: Mapped[str] = mapped_column(String(512), default="")
    jira_project_key: Mapped[str] = mapped_column(String(64), default="")
    # 同步：追加在 project = <key> 之后的 JQL；空则用 contract.DEFAULT_SYNC_JQL
    sync_jql: Mapped[str] = mapped_column(Text, default="")
    sync_max_results: Mapped[int] = mapped_column(Integer, default=200)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 项目级开关（镜像 / 模型 / 超时 / 日上限 / 熔断 / 单价 / 状态映射都是 contract 里的固定常量）
    deliver: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 每项目平台系统用户（派发前写进 <仓>/03_config/.env 三行；密码 Fernet）
    hcm_base_url: Mapped[str] = mapped_column(String(512), default="")
    hcm_username: Mapped[str] = mapped_column(String(128), default="")
    hcm_password_enc: Mapped[str] = mapped_column(Text, default="")

    # 非密环境变量（JSON 对象），以 env 传给 worker.sh；密钥禁止放这里
    env_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AutodevRun(Base):
    """一次 worker 运行 = 一张单的一次尝试。exit_code 契约见 contract.EXIT_CODES。"""

    __tablename__ = "autodev_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("autodev_projects.id"), index=True
    )
    issue_key: Mapped[str] = mapped_column(String(64), index=True)
    story_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)  # running/finished/lost
    trigger: Mapped[str] = mapped_column(String(16), default="manual")  # manual/schedule

    dispatch_dir: Mapped[str] = mapped_column(String(512), default="")  # master 上本次派发目录
    run_dir: Mapped[str] = mapped_column(String(512), default="")  # worker.sh 的 $RUN
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), default="")  # delivered/verified/no_change/failed
    verdict: Mapped[str] = mapped_column(Text, default="")
    branch: Mapped[str] = mapped_column(String(256), default="")
    worktree: Mapped[str] = mapped_column(String(512), default="")
    mr_url: Mapped[str] = mapped_column(String(512), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    image_id: Mapped[str] = mapped_column(String(128), default="")

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)

    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
