from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    product: str = ""
    iteration: str = ""
    version: str = ""
    start_date: str | None = None
    end_date: str | None = None

class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    product: str | None = None
    iteration: str | None = None
    version: str | None = None
    start_date: str | None = None
    end_date: str | None = None

class StoryCreate(BaseModel):
    project_id: str
    title: str
    description: str = ""
    priority: int = 3
    parent_id: str | None = None
    tags: list[str] = []
    collaborators: list[str] = []
    deadline: str | None = None

class StoryUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    state: str | None = None
    priority: int | None = None
    parent_id: str | None = None
    tags: list[str] | None = None
    collaborators: list[str] | None = None
    deadline: str | None = None
    pm_id: str | None = None
    project_id: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    repo_id: str | None = None
    branch: str | None = None

class TaskCreate(BaseModel):
    project_id: str | None = None
    story_id: str | None = None
    parent_id: str | None = None
    title: str
    description: str = ""
    task_type: str = "fullstack"
    assignee_id: str | None = None
    creator_id: str | None = None
    tags: list[str] = []
    collaborators: list[str] = []
    estimate_hours: float | None = None
    deadline: str | None = None

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    task_type: str | None = None
    state: str | None = None
    assignee_id: str | None = None
    tags: list[str] | None = None
    collaborators: list[str] | None = None
    estimate_hours: float | None = None
    actual_hours: float | None = None
    deadline: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    repo_id: str | None = None
    branch: str | None = None

class BugCreate(BaseModel):
    project_id: str | None = None
    story_id: str | None = None
    task_id: str | None = None
    title: str
    description: str = ""
    severity: int = 3
    tags: list[str] = []
    collaborators: list[str] = []
    assignee_id: str | None = None

class BugUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: int | None = None
    state: str | None = None
    assignee_id: str | None = None
    tags: list[str] | None = None
    collaborators: list[str] | None = None
    estimate_hours: float | None = None
    actual_hours: float | None = None
    deadline: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    repo_id: str | None = None
    branch: str | None = None

class MilestoneCreate(BaseModel):
    project_id: str
    name: str
    description: str = ""
    due_date: str | None = None
    story_id: str | None = None

class MilestoneUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    due_date: str | None = None
    completed_at: str | None = None

class TransitionBody(BaseModel):
    target_state: str

class ProjectMemberBody(BaseModel):
    member_id: str
    role: str = "member"


class IterationCreate(BaseModel):
    project_id: str
    name: str
    goal: str = ""
    owner_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str = "planning"
    estimate_hours: float | None = None


class IterationUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    owner_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str | None = None
    estimate_hours: float | None = None


class VersionCreate(BaseModel):
    project_id: str
    name: str
    description: str = ""
    owner_id: str | None = None
    planned_release_at: str | None = None
    actual_release_at: str | None = None
    progress: int = 0
    release_date: str | None = None  # backward compatibility
    status: str = "planning"


class VersionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    owner_id: str | None = None
    planned_release_at: str | None = None
    actual_release_at: str | None = None
    progress: int | None = None
    release_date: str | None = None  # backward compatibility
    status: str | None = None


class IterationStoryBody(BaseModel):
    story_id: str
    story_order: int = 0


class IterationTaskBody(BaseModel):
    task_id: str
    task_order: int = 0


class IterationBugBody(BaseModel):
    bug_id: str
    bug_order: int = 0

class VersionStoryBody(BaseModel):
    story_id: str
    added_reason: str = ""
    story_order: int = 0

class VersionBugBody(BaseModel):
    bug_id: str
    bug_order: int = 0


class ViewCreate(BaseModel):
    name: str
    work_item_type: str  # 需求/任务/缺陷
    scope: str = "personal"  # personal/shared
    filters: dict = {}
    columns: list = []

class ViewUpdate(BaseModel):
    name: str | None = None
    filters: dict | None = None
    columns: list | None = None
    view_order: int | None = None


class ColumnSettingBody(BaseModel):
    work_item_type: str  # 需求/任务/缺陷
    columns: list  # [{"key":"workNo","visible":true}, ...]


class CommentCreate(BaseModel):
    content: str
    mentions: list[str] = []


class WorkItemLinkCreate(BaseModel):
    source_type: str  # story/task/bug
    source_id: str
    target_type: str  # story/task/bug
    target_id: str


class TagCreate(BaseModel):
    name: str
    color: str = "#3b82f6"

class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None

class TagReorder(BaseModel):
    ids: list[str]

class TagMigrate(BaseModel):
    target_tag_id: str | None = None


class StatusCreate(BaseModel):
    name: str
    icon: str = "○"
    icon_color: str = "#3b82f6"
    command: str = ""
    work_item_types: list[str] = []

class StatusUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    icon_color: str | None = None
    command: str | None = None
    work_item_types: list[str] | None = None


class TestModuleCreate(BaseModel):
    project_id: str
    parent_id: str | None = None
    name: str

class TestModuleUpdate(BaseModel):
    name: str | None = None
    parent_id: str | None = None
    sort_order: int | None = None

class TestCaseCreate(BaseModel):
    project_id: str
    module_id: str | None = None
    title: str
    precondition: str = ""
    notes: str = ""
    case_type: str = "functional"
    priority: int = 2
    maintainer_id: str | None = None
    steps: list[dict] = []

class TestCaseUpdate(BaseModel):
    module_id: str | None = None
    title: str | None = None
    precondition: str | None = None
    notes: str | None = None
    case_type: str | None = None
    priority: int | None = None
    maintainer_id: str | None = None
    review_result: str | None = None
    steps: list[dict] | None = None

class TestCaseWorkItemBody(BaseModel):
    test_case_id: str
    entity_type: str  # story/task/bug
    entity_id: str
