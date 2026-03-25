"""VortFlow ORM 模型"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class FlowProject(Base):
    """项目"""

    __tablename__ = "flow_projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(64), default="")
    color: Mapped[str] = mapped_column(String(32), default="#3b82f6")
    description: Mapped[str] = mapped_column(Text, default="")
    product: Mapped[str] = mapped_column(String(200), default="")
    iteration: Mapped[str] = mapped_column(String(200), default="")
    version: Mapped[str] = mapped_column(String(64), default="")
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowStory(Base):
    """需求"""

    __tablename__ = "flow_stories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(32), default="submitted", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1=紧急 2=高 3=中 4=低
    parent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("flow_stories.id"), nullable=True, index=True
    )
    submitter_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    pm_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    designer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    collaborators_json: Mapped[str] = mapped_column(Text, default="[]")
    attachments_json: Mapped[str] = mapped_column(Text, default="[]")
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    repo_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    branch: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowTask(Base):
    """子任务"""

    __tablename__ = "flow_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("flow_projects.id"), nullable=True, index=True)
    story_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("flow_stories.id"), nullable=True, index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("flow_tasks.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(String(32), default="fullstack")  # frontend/backend/fullstack/test
    state: Mapped[str] = mapped_column(String(32), default="todo", index=True)
    assignee_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    creator_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    collaborators_json: Mapped[str] = mapped_column(Text, default="[]")
    attachments_json: Mapped[str] = mapped_column(Text, default="[]")
    estimate_hours: Mapped[float | None] = mapped_column(nullable=True)
    actual_hours: Mapped[float | None] = mapped_column(nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    repo_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    branch: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowBug(Base):
    """缺陷"""

    __tablename__ = "flow_bugs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("flow_projects.id"), nullable=True, index=True)
    story_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("flow_stories.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("flow_tasks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[int] = mapped_column(Integer, default=3)  # 1=致命 2=严重 3=一般 4=轻微
    state: Mapped[str] = mapped_column(String(32), default="open", index=True)
    reporter_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    developer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    collaborators_json: Mapped[str] = mapped_column(Text, default="[]")
    attachments_json: Mapped[str] = mapped_column(Text, default="[]")
    estimate_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    repo_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    branch: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())



class FlowEvent(Base):
    """事件日志（审计追踪）"""

    __tablename__ = "flow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)  # project/story/task/bug
    entity_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(64))  # created/state_changed/assigned/...
    actor_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")  # JSON 补充信息
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowProjectMember(Base):
    """项目成员 — 记录成员在项目中的角色"""

    __tablename__ = "flow_project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "member_id", name="uq_flow_project_member"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="member")  # owner/pm/dev/tester/viewer
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowExternalMapping(Base):
    """外部系统映射（双向同步用）"""

    __tablename__ = "flow_external_mappings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    local_type: Mapped[str] = mapped_column(String(32), index=True)  # story/task/bug
    local_id: Mapped[str] = mapped_column(String(32), index=True)
    adapter: Mapped[str] = mapped_column(String(32), index=True)  # zentao/jira
    external_id: Mapped[str] = mapped_column(String(128))
    sync_cursor: Mapped[str] = mapped_column(String(128), default="")
    conflict_state: Mapped[str] = mapped_column(String(16), default="ok")  # ok/conflict/pending
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FlowIteration(Base):
    """迭代（Sprint）"""

    __tablename__ = "flow_iterations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))  # Sprint 1, Sprint 2
    goal: Mapped[str] = mapped_column(Text, default="")  # 迭代目标
    owner_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True, index=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planning")  # planning/active/completed
    estimate_hours: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowVersion(Base):
    """版本"""

    __tablename__ = "flow_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))  # v1.0.0
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True, index=True)
    planned_release_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_release_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    release_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planning")  # planning/released/archived
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowVersionStory(Base):
    """版本-需求关联（多对多）"""

    __tablename__ = "flow_version_stories"
    __table_args__ = (
        UniqueConstraint("version_id", "story_id", name="uq_version_story"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_versions.id"), index=True)
    story_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_stories.id"), index=True)
    added_reason: Mapped[str] = mapped_column(Text, default="")  # 需求纳入版本的原因
    story_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowIterationStory(Base):
    """迭代-需求关联（多对多）"""

    __tablename__ = "flow_iteration_stories"
    __table_args__ = (
        UniqueConstraint("iteration_id", "story_id", name="uq_iteration_story"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    iteration_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_iterations.id"), index=True)
    story_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_stories.id"), index=True)
    story_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowIterationTask(Base):
    """迭代-任务关联（多对多）"""

    __tablename__ = "flow_iteration_tasks"
    __table_args__ = (
        UniqueConstraint("iteration_id", "task_id", name="uq_iteration_task"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    iteration_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_iterations.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_tasks.id"), index=True)
    task_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowIterationBug(Base):
    """迭代-缺陷关联（多对多）"""

    __tablename__ = "flow_iteration_bugs"
    __table_args__ = (
        UniqueConstraint("iteration_id", "bug_id", name="uq_iteration_bug"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    iteration_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_iterations.id"), index=True)
    bug_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_bugs.id"), index=True)
    bug_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowVersionBug(Base):
    """版本-缺陷关联（多对多）"""

    __tablename__ = "flow_version_bugs"
    __table_args__ = (
        UniqueConstraint("version_id", "bug_id", name="uq_version_bug"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_versions.id"), index=True)
    bug_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_bugs.id"), index=True)
    bug_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowView(Base):
    """自定义视图（个人/公共）"""

    __tablename__ = "flow_views"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100))
    work_item_type: Mapped[str] = mapped_column(String(16), index=True)  # 需求/任务/缺陷
    scope: Mapped[str] = mapped_column(String(16), default="personal")  # personal/shared
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    filters_json: Mapped[str] = mapped_column(Text, default="{}")
    columns_json: Mapped[str] = mapped_column(Text, default="[]")  # [{"key":"..","visible":true}, ...]
    view_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowColumnSetting(Base):
    """用户列设置偏好（per user per work_item_type）"""

    __tablename__ = "flow_column_settings"
    __table_args__ = (
        UniqueConstraint("member_id", "work_item_type", name="uq_column_setting"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    work_item_type: Mapped[str] = mapped_column(String(16))  # 需求/任务/缺陷
    columns_json: Mapped[str] = mapped_column(Text, default="[]")  # [{"key":"..","visible":true}, ...]
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowWorkItemLink(Base):
    """Work item relation (generic many-to-many between story/task/bug)"""

    __tablename__ = "flow_work_item_links"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "target_type", "target_id", name="uq_work_item_link"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_type: Mapped[str] = mapped_column(String(16), index=True)  # story/task/bug
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    target_type: Mapped[str] = mapped_column(String(16), index=True)  # story/task/bug
    target_id: Mapped[str] = mapped_column(String(32), index=True)
    created_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowTag(Base):
    """Work item tag definition"""

    __tablename__ = "flow_tags"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    color: Mapped[str] = mapped_column(String(20), default="#3b82f6")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowStatus(Base):
    """Work item status definition"""

    __tablename__ = "flow_statuses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    icon: Mapped[str] = mapped_column(String(50), default="○")
    icon_color: Mapped[str] = mapped_column(String(20), default="#3b82f6")
    command: Mapped[str] = mapped_column(String(200), default="")
    work_item_types_json: Mapped[str] = mapped_column(Text, default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowDescriptionTemplate(Base):
    """Work item description template (per work_item_type)"""

    __tablename__ = "flow_description_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    work_item_type: Mapped[str] = mapped_column(String(16), unique=True)  # 需求/任务/缺陷
    content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowTestModule(Base):
    """Test case module (tree structure for organizing test cases)"""

    __tablename__ = "flow_test_modules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("flow_test_modules.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowTestCase(Base):
    """Test case"""

    __tablename__ = "flow_test_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    module_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("flow_test_modules.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    precondition: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    case_type: Mapped[str] = mapped_column(String(32), default="functional")  # functional/performance/api/ui/security
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 0=P0 1=P1 2=P2 3=P3
    maintainer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    review_result: Mapped[str] = mapped_column(String(32), default="pending")  # pending/passed/rejected
    steps_json: Mapped[str] = mapped_column(Text, default="[]")  # [{order, description, expected_result}]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowTestCaseWorkItem(Base):
    """Test case - work item association"""

    __tablename__ = "flow_test_case_work_items"
    __table_args__ = (
        UniqueConstraint("test_case_id", "entity_type", "entity_id", name="uq_testcase_workitem"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    test_case_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_test_cases.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(16), index=True)  # story/task/bug
    entity_id: Mapped[str] = mapped_column(String(32), index=True)
    created_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowTestPlan(Base):
    """Test plan"""

    __tablename__ = "flow_test_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="in_progress")  # planning/in_progress/completed/suspended
    owner_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    iteration_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("flow_iterations.id"), nullable=True
    )
    version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("flow_versions.id"), nullable=True
    )
    start_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowTestPlanCase(Base):
    """Test plan - test case association"""

    __tablename__ = "flow_test_plan_cases"
    __table_args__ = (
        UniqueConstraint("plan_id", "test_case_id", name="uq_testplan_case"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    plan_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_test_plans.id"), index=True)
    test_case_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_test_cases.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowTestPlanExecution(Base):
    """Test plan execution result"""

    __tablename__ = "flow_test_plan_executions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    plan_case_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_test_plan_cases.id"), index=True)
    result: Mapped[str] = mapped_column(String(32))  # passed/blocked/failed/skipped
    executor_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    bug_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowTestPlanReview(Base):
    """Test plan code review item (linked to a Git PR)"""

    __tablename__ = "flow_test_plan_reviews"
    __table_args__ = (
        UniqueConstraint("plan_id", "repo_id", "pr_number", name="uq_plan_review"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    plan_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_test_plans.id"), index=True)
    repo_id: Mapped[str] = mapped_column(String(32), index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    pr_url: Mapped[str] = mapped_column(String(512), default="")
    pr_title: Mapped[str] = mapped_column(String(500), default="")
    head_branch: Mapped[str] = mapped_column(String(128), default="")
    base_branch: Mapped[str] = mapped_column(String(128), default="")
    reviewer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/approved/rejected/changes_requested
    review_notes: Mapped[str] = mapped_column(Text, default="")
    added_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowTestPlanReviewHistory(Base):
    """Code review status change history"""

    __tablename__ = "flow_test_plan_review_histories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    review_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_test_plan_reviews.id"), index=True)
    action: Mapped[str] = mapped_column(String(32))  # status_changed/reviewer_assigned
    old_status: Mapped[str] = mapped_column(String(32), default="")
    new_status: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    actor_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowTestReport(Base):
    """Test report (point-in-time snapshot of a test plan)"""

    __tablename__ = "flow_test_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    plan_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_test_plans.id"), index=True)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    creator_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowComment(Base):
    """Work item comment"""

    __tablename__ = "flow_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)  # story/task/bug
    entity_id: Mapped[str] = mapped_column(String(32), index=True)
    author_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    mentions_json: Mapped[str] = mapped_column(Text, default="[]")  # member_ids mentioned via @
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
