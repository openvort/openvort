"""VortFlow 状态机引擎"""

from enum import Enum
from typing import Any, Callable, Coroutine

from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.engine")


# ============ 状态枚举 ============


class StoryState(str, Enum):
    SUBMITTED = "submitted"
    INTAKE = "intake"
    REVIEW = "review"
    REJECTED = "rejected"
    PM_REFINE = "pm_refine"
    DESIGN = "design"
    DESIGN_DONE = "design_done"
    BREAKDOWN = "breakdown"
    DEV_ASSIGN = "dev_assign"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    BUGFIX = "bugfix"
    DONE = "done"


class TaskState(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CLOSED = "closed"


class BugState(str, Enum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    FIXING = "fixing"
    RESOLVED = "resolved"
    VERIFIED = "verified"
    CLOSED = "closed"
    NOT_REPRODUCIBLE = "not_reproducible"
    REOPENED = "reopened"
    BY_DESIGN = "by_design"
    DEFERRED = "deferred"
    SUSPENDED = "suspended"


# ============ 统计用完成态集合 ============

STORY_DONE_STATES: set[str] = {StoryState.DONE.value}
TASK_DONE_STATES: set[str] = {TaskState.DONE.value, TaskState.CLOSED.value}
BUG_CLOSED_STATES: set[str] = {
    BugState.RESOLVED.value, BugState.VERIFIED.value, BugState.CLOSED.value,
    BugState.NOT_REPRODUCIBLE.value, BugState.BY_DESIGN.value,
}


# ============ 合法转换表 ============

STORY_TRANSITIONS: dict[StoryState, list[StoryState]] = {
    StoryState.SUBMITTED: [StoryState.INTAKE, StoryState.REJECTED],
    StoryState.INTAKE: [StoryState.REVIEW],
    StoryState.REVIEW: [StoryState.PM_REFINE, StoryState.REJECTED],
    StoryState.REJECTED: [StoryState.SUBMITTED],
    StoryState.PM_REFINE: [StoryState.DESIGN],
    StoryState.DESIGN: [StoryState.DESIGN_DONE],
    StoryState.DESIGN_DONE: [StoryState.BREAKDOWN],
    StoryState.BREAKDOWN: [StoryState.DEV_ASSIGN],
    StoryState.DEV_ASSIGN: [StoryState.IN_PROGRESS],
    StoryState.IN_PROGRESS: [StoryState.TESTING],
    StoryState.TESTING: [StoryState.BUGFIX, StoryState.DONE],
    StoryState.BUGFIX: [StoryState.TESTING],
    StoryState.DONE: [],
}

TASK_TRANSITIONS: dict[TaskState, list[TaskState]] = {
    TaskState.TODO: [TaskState.IN_PROGRESS],
    TaskState.IN_PROGRESS: [TaskState.DONE],
    TaskState.DONE: [TaskState.CLOSED, TaskState.IN_PROGRESS],
    TaskState.CLOSED: [],
}

BUG_TRANSITIONS: dict[BugState, list[BugState]] = {
    BugState.OPEN: [BugState.CONFIRMED, BugState.CLOSED, BugState.NOT_REPRODUCIBLE, BugState.BY_DESIGN, BugState.DEFERRED, BugState.SUSPENDED],
    BugState.CONFIRMED: [BugState.FIXING, BugState.NOT_REPRODUCIBLE, BugState.BY_DESIGN, BugState.DEFERRED, BugState.SUSPENDED],
    BugState.FIXING: [BugState.RESOLVED, BugState.DEFERRED],
    BugState.RESOLVED: [BugState.VERIFIED, BugState.FIXING],
    BugState.VERIFIED: [BugState.CLOSED, BugState.REOPENED],
    BugState.CLOSED: [BugState.REOPENED],
    BugState.NOT_REPRODUCIBLE: [BugState.REOPENED, BugState.CLOSED],
    BugState.REOPENED: [BugState.CONFIRMED, BugState.FIXING],
    BugState.BY_DESIGN: [BugState.REOPENED, BugState.CLOSED],
    BugState.DEFERRED: [BugState.FIXING, BugState.REOPENED],
    BugState.SUSPENDED: [BugState.REOPENED, BugState.OPEN],
}


# ============ Transition Hook 类型 ============

TransitionHook = Callable[[str, str, str, dict], Coroutine[Any, Any, None]]
# (entity_type, entity_id, new_state, context) -> None


# ============ FlowEngine ============


class FlowEngine:
    """状态机核心 — 校验转换合法性 + 触发 hooks"""

    def __init__(self):
        self._hooks: list[TransitionHook] = []

    def add_hook(self, hook: TransitionHook) -> None:
        self._hooks.append(hook)

    async def transition_story(self, story_id: str, current: StoryState, target: StoryState, context: dict | None = None) -> bool:
        """推进需求状态"""
        if target not in STORY_TRANSITIONS.get(current, []):
            log.warning(f"Story {story_id}: 非法转换 {current.value} -> {target.value}")
            return False
        await self._fire_hooks("story", story_id, target.value, context or {})
        return True

    async def transition_task(self, task_id: str, current: TaskState, target: TaskState, context: dict | None = None) -> bool:
        """推进任务状态"""
        if target not in TASK_TRANSITIONS.get(current, []):
            log.warning(f"Task {task_id}: 非法转换 {current.value} -> {target.value}")
            return False
        await self._fire_hooks("task", task_id, target.value, context or {})
        return True

    async def transition_bug(self, bug_id: str, current: BugState, target: BugState, context: dict | None = None) -> bool:
        """推进缺陷状态"""
        if target not in BUG_TRANSITIONS.get(current, []):
            log.warning(f"Bug {bug_id}: 非法转换 {current.value} -> {target.value}")
            return False
        await self._fire_hooks("bug", bug_id, target.value, context or {})
        return True

    async def _fire_hooks(self, entity_type: str, entity_id: str, new_state: str, context: dict) -> None:
        for hook in self._hooks:
            try:
                await hook(entity_type, entity_id, new_state, context)
            except Exception as e:
                log.error(f"Transition hook 执行失败: {e}")
