import json
from datetime import datetime

from sqlalchemy import func, select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowBug,
    FlowEvent,
    FlowIteration,
    FlowIterationStory,
    FlowIterationTask,
    FlowProject,
    FlowStatus,
    FlowStory,
    FlowTag,
    FlowTask,
    FlowTestCase,
    FlowTestCaseWorkItem,
    FlowTestModule,
    FlowTestPlan,
    FlowTestPlanCase,
    FlowTestPlanExecution,
    FlowVersion,
    FlowVersionStory,
    FlowView,
)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    result: list[str] = []
    for item in data:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


# ---------------------------------------------------------------------------
# Serializer dicts
# ---------------------------------------------------------------------------

def _project_dict(r: FlowProject) -> dict:
    return {
        "id": r.id, "name": r.name, "code": r.code, "color": r.color,
        "description": r.description,
        "product": r.product, "iteration": r.iteration, "version": r.version,
        "owner_id": r.owner_id,
        "start_date": r.start_date.isoformat() if r.start_date else None,
        "end_date": r.end_date.isoformat() if r.end_date else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

def _story_dict(r: FlowStory) -> dict:
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "state": r.state, "priority": r.priority,
        "parent_id": r.parent_id,
        "project_id": r.project_id, "submitter_id": r.submitter_id,
        "pm_id": r.pm_id, "designer_id": r.designer_id, "reviewer_id": r.reviewer_id,
        "tags": _parse_json_list(r.tags_json),
        "collaborators": _parse_json_list(r.collaborators_json),
        "deadline": r.deadline.isoformat() if r.deadline else None,
        "start_at": r.start_at.isoformat() if getattr(r, "start_at", None) else None,
        "end_at": r.end_at.isoformat() if getattr(r, "end_at", None) else None,
        "repo_id": getattr(r, "repo_id", None) or "",
        "branch": getattr(r, "branch", None) or "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }

def _task_dict(r: FlowTask) -> dict:
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "state": r.state, "task_type": r.task_type,
        "project_id": r.project_id,
        "story_id": r.story_id, "parent_id": r.parent_id,
        "assignee_id": r.assignee_id, "creator_id": r.creator_id,
        "tags": _parse_json_list(r.tags_json),
        "collaborators": _parse_json_list(r.collaborators_json),
        "estimate_hours": r.estimate_hours, "actual_hours": r.actual_hours,
        "deadline": r.deadline.isoformat() if r.deadline else None,
        "start_at": r.start_at.isoformat() if getattr(r, "start_at", None) else None,
        "end_at": r.end_at.isoformat() if getattr(r, "end_at", None) else None,
        "repo_id": getattr(r, "repo_id", None) or "",
        "branch": getattr(r, "branch", None) or "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }

def _bug_dict(r: FlowBug) -> dict:
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "state": r.state, "severity": r.severity,
        "project_id": r.project_id,
        "story_id": r.story_id, "task_id": r.task_id,
        "reporter_id": r.reporter_id, "assignee_id": r.assignee_id,
        "developer_id": r.developer_id,
        "tags": _parse_json_list(r.tags_json),
        "collaborators": _parse_json_list(r.collaborators_json),
        "estimate_hours": getattr(r, "estimate_hours", None),
        "actual_hours": getattr(r, "actual_hours", None),
        "deadline": r.deadline.isoformat() if getattr(r, "deadline", None) else None,
        "start_at": r.start_at.isoformat() if getattr(r, "start_at", None) else None,
        "end_at": r.end_at.isoformat() if getattr(r, "end_at", None) else None,
        "repo_id": getattr(r, "repo_id", None) or "",
        "branch": getattr(r, "branch", None) or "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _iteration_dict(r: FlowIteration) -> dict:
    return {
        "id": r.id, "project_id": r.project_id, "name": r.name, "goal": r.goal,
        "owner_id": r.owner_id,
        "start_date": r.start_date.isoformat() if r.start_date else None,
        "end_date": r.end_date.isoformat() if r.end_date else None,
        "status": r.status,
        "estimate_hours": r.estimate_hours,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _version_dict(r: FlowVersion) -> dict:
    return {
        "id": r.id, "project_id": r.project_id, "name": r.name,
        "description": r.description,
        "owner_id": r.owner_id,
        "planned_release_at": r.planned_release_at.isoformat() if r.planned_release_at else None,
        "actual_release_at": r.actual_release_at.isoformat() if r.actual_release_at else None,
        "progress": r.progress,
        "release_date": r.release_date.isoformat() if r.release_date else None,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _view_dict(r: FlowView) -> dict:
    return {
        "id": r.id, "name": r.name,
        "work_item_type": r.work_item_type,
        "scope": r.scope, "owner_id": r.owner_id,
        "filters": json.loads(r.filters_json) if r.filters_json else {},
        "columns": json.loads(r.columns_json) if r.columns_json else [],
        "order": r.view_order,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _tag_dict(r: FlowTag) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "color": r.color,
        "sort_order": r.sort_order,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _status_dict(r: FlowStatus) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "icon": r.icon,
        "icon_color": r.icon_color,
        "command": r.command,
        "work_item_types": _parse_json_list(r.work_item_types_json),
        "sort_order": r.sort_order,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _test_module_dict(m: FlowTestModule) -> dict:
    return {
        "id": m.id,
        "project_id": m.project_id,
        "parent_id": m.parent_id,
        "name": m.name,
        "sort_order": m.sort_order,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _test_case_dict(tc: FlowTestCase, *, maintainer_name: str = "", module_name: str = "", module_path: str = "") -> dict:
    return {
        "id": tc.id,
        "project_id": tc.project_id,
        "module_id": tc.module_id,
        "module_name": module_name,
        "module_path": module_path,
        "title": tc.title,
        "precondition": tc.precondition,
        "notes": tc.notes,
        "case_type": tc.case_type,
        "priority": tc.priority,
        "maintainer_id": tc.maintainer_id,
        "maintainer_name": maintainer_name,
        "review_result": tc.review_result,
        "steps": json.loads(tc.steps_json) if tc.steps_json else [],
        "created_at": tc.created_at.isoformat() if tc.created_at else None,
        "updated_at": tc.updated_at.isoformat() if tc.updated_at else None,
    }


def _test_plan_dict(
    tp: FlowTestPlan,
    *,
    owner_name: str = "",
    iteration_name: str = "",
    version_name: str = "",
    total_cases: int = 0,
    executed_cases: int = 0,
    passed: int = 0,
    failed: int = 0,
    blocked: int = 0,
    skipped: int = 0,
) -> dict:
    return {
        "id": tp.id,
        "project_id": tp.project_id,
        "title": tp.title,
        "description": tp.description,
        "status": tp.status,
        "owner_id": tp.owner_id,
        "owner_name": owner_name,
        "iteration_id": tp.iteration_id,
        "iteration_name": iteration_name,
        "version_id": tp.version_id,
        "version_name": version_name,
        "start_date": tp.start_date,
        "end_date": tp.end_date,
        "total_cases": total_cases,
        "executed_cases": executed_cases,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "skipped": skipped,
        "created_at": tp.created_at.isoformat() if tp.created_at else None,
        "updated_at": tp.updated_at.isoformat() if tp.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Link-type mappings
# ---------------------------------------------------------------------------

_LINK_TYPE_MODEL = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
_LINK_TYPE_DICT = {"story": _story_dict, "task": _task_dict, "bug": _bug_dict}


# ---------------------------------------------------------------------------
# Attach iteration / version links to item lists
# ---------------------------------------------------------------------------

async def _attach_story_links(session, items: list[dict]) -> list[dict]:
    story_ids = [str(item.get("id") or "").strip() for item in items if item.get("id")]
    if not story_ids:
        return items

    iteration_rows = await session.execute(
        select(FlowIterationStory.story_id, FlowIteration.id, FlowIteration.name)
        .join(FlowIteration, FlowIteration.id == FlowIterationStory.iteration_id)
        .where(FlowIterationStory.story_id.in_(story_ids))
    )
    story_iteration_map: dict[str, tuple[str, str]] = {}
    for story_id, iteration_id, iteration_name in iteration_rows.all():
        sid = str(story_id or "")
        if sid and sid not in story_iteration_map:
            story_iteration_map[sid] = (str(iteration_id or ""), str(iteration_name or ""))

    version_rows = await session.execute(
        select(FlowVersionStory.story_id, FlowVersion.id, FlowVersion.name)
        .join(FlowVersion, FlowVersion.id == FlowVersionStory.version_id)
        .where(FlowVersionStory.story_id.in_(story_ids))
    )
    story_version_map: dict[str, tuple[str, str]] = {}
    for story_id, version_id, version_name in version_rows.all():
        sid = str(story_id or "")
        if sid and sid not in story_version_map:
            story_version_map[sid] = (str(version_id or ""), str(version_name or ""))

    for item in items:
        sid = str(item.get("id") or "").strip()
        iteration = story_iteration_map.get(sid)
        version = story_version_map.get(sid)
        item["iteration_id"] = iteration[0] if iteration else ""
        item["iteration_name"] = iteration[1] if iteration else ""
        item["version_id"] = version[0] if version else ""
        item["version_name"] = version[1] if version else ""
    return items


async def _attach_task_links(session, items: list[dict]) -> list[dict]:
    task_ids = [str(item.get("id") or "").strip() for item in items if item.get("id")]
    if not task_ids:
        return items

    iteration_rows = await session.execute(
        select(FlowIterationTask.task_id, FlowIteration.id, FlowIteration.name)
        .join(FlowIteration, FlowIteration.id == FlowIterationTask.iteration_id)
        .where(FlowIterationTask.task_id.in_(task_ids))
    )
    task_iteration_map: dict[str, tuple[str, str]] = {}
    for task_id, iteration_id, iteration_name in iteration_rows.all():
        tid = str(task_id or "")
        if tid and tid not in task_iteration_map:
            task_iteration_map[tid] = (str(iteration_id or ""), str(iteration_name or ""))

    for item in items:
        tid = str(item.get("id") or "").strip()
        iteration = task_iteration_map.get(tid)
        item["iteration_id"] = iteration[0] if iteration else ""
        item["iteration_name"] = iteration[1] if iteration else ""
    return items


async def _attach_bug_links(session, items: list[dict]) -> list[dict]:
    story_ids = [str(item.get("story_id") or "").strip() for item in items if item.get("story_id")]
    if not story_ids:
        return items

    story_items = [{"id": story_id} for story_id in story_ids]
    await _attach_story_links(session, story_items)
    story_map = {str(item["id"]): item for item in story_items}

    for item in items:
        linked_story = story_map.get(str(item.get("story_id") or "").strip())
        item["iteration_id"] = str((linked_story or {}).get("iteration_id") or "")
        item["iteration_name"] = str((linked_story or {}).get("iteration_name") or "")
        item["version_id"] = str((linked_story or {}).get("version_id") or "")
        item["version_name"] = str((linked_story or {}).get("version_name") or "")
    return items


# ---------------------------------------------------------------------------
# Event logging
# ---------------------------------------------------------------------------

async def _log_event(session, entity_type: str, entity_id: str, action: str, detail: dict | None = None):
    ev = FlowEvent(entity_type=entity_type, entity_id=entity_id, action=action,
                   detail=json.dumps(detail or {}, ensure_ascii=False))
    session.add(ev)


# ---------------------------------------------------------------------------
# Story / task tree validation
# ---------------------------------------------------------------------------

async def _validate_story_parent(
    session,
    *,
    project_id: str,
    parent_id: str | None,
    story_id: str | None = None,
) -> tuple[str | None, str | None]:
    normalized_parent_id = (parent_id or "").strip() or None
    if normalized_parent_id is None:
        return None, None
    if story_id and normalized_parent_id == story_id:
        return None, "父需求不能是自身"

    parent = await session.get(FlowStory, normalized_parent_id)
    if not parent:
        return None, "父需求不存在"
    if parent.project_id != project_id:
        return None, "父需求必须和当前需求属于同一个项目"

    if story_id:
        cursor = parent
        while cursor and cursor.parent_id:
            if cursor.parent_id == story_id:
                return None, "不能将需求移动到自己的子需求下"
            cursor = await session.get(FlowStory, cursor.parent_id)

    return normalized_parent_id, None


async def _collect_story_descendant_ids(session, story_ids: list[str]) -> list[str]:
    pending_ids = [story_id for story_id in story_ids if story_id]
    descendant_ids: list[str] = []
    seen: set[str] = set(pending_ids)
    while pending_ids:
        child_rows = (
            await session.execute(select(FlowStory.id).where(FlowStory.parent_id.in_(pending_ids)))
        ).scalars().all()
        next_ids = [child_id for child_id in child_rows if child_id not in seen]
        if not next_ids:
            break
        descendant_ids.extend(next_ids)
        seen.update(next_ids)
        pending_ids = next_ids
    return descendant_ids


async def _resolve_task_story_and_parent(
    session,
    *,
    story_id: str | None,
    parent_id: str | None,
) -> tuple[str | None, str | None, str | None]:
    normalized_story_id = (story_id or "").strip() or None
    normalized_parent_id = (parent_id or "").strip() or None

    parent_task: FlowTask | None = None
    if normalized_parent_id:
        parent_task = await session.get(FlowTask, normalized_parent_id)
        if not parent_task:
            return None, None, "父任务不存在"
        if parent_task.parent_id:
            return None, None, "父任务不能是子任务"

        if normalized_story_id and parent_task.story_id and normalized_story_id != parent_task.story_id:
            return None, None, "子任务必须和父任务属于同一个需求"
        normalized_story_id = normalized_story_id or parent_task.story_id

    if normalized_story_id:
        story = await session.get(FlowStory, normalized_story_id)
        if not story:
            return None, None, "关联需求不存在"

    return normalized_story_id, normalized_parent_id, None


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def _apply_sort(stmt, model, sort_by: str, sort_order: str, default_col=None):
    """Apply dynamic sorting to a SQLAlchemy select statement."""
    col = getattr(model, sort_by, None) if sort_by else None
    if col is not None:
        order_fn = col.asc() if sort_order == "asc" else col.desc()
        return stmt.order_by(order_fn, model.id.desc())
    if default_col is not None:
        return stmt.order_by(default_col.desc(), model.id.desc())
    return stmt.order_by(model.created_at.desc(), model.id.desc())


# ---------------------------------------------------------------------------
# Member name resolution
# ---------------------------------------------------------------------------

async def _resolve_member_name(session, member_id: str | None) -> str:
    if not member_id:
        return ""
    from openvort.contacts.models import Member
    member = await session.get(Member, member_id)
    return member.name if member else ""


# ---------------------------------------------------------------------------
# Tag helpers
# ---------------------------------------------------------------------------

async def _count_tag_usage(session, tag_name: str) -> int:
    """Count work items using the given tag name across stories/tasks/bugs."""
    total = 0
    for model in (FlowStory, FlowTask, FlowBug):
        result = await session.execute(
            select(func.count()).select_from(model).where(
                model.tags_json.contains(json.dumps(tag_name, ensure_ascii=False))
            )
        )
        total += result.scalar() or 0
    return total


async def _replace_tag_in_items(session, old_name: str, new_name: str | None):
    """Replace or remove a tag across all work item tables."""
    for model in (FlowStory, FlowTask, FlowBug):
        result = await session.execute(
            select(model).where(
                model.tags_json.contains(json.dumps(old_name, ensure_ascii=False))
            )
        )
        items = result.scalars().all()
        for item in items:
            tags = _parse_json_list(item.tags_json)
            tags = [t for t in tags if t != old_name]
            if new_name and new_name not in tags:
                tags.append(new_name)
            item.tags_json = json.dumps(tags, ensure_ascii=False)


async def _collect_used_tag_names(session) -> set[str]:
    """Collect all distinct tag names used across work items."""
    names: set[str] = set()
    for model in (FlowStory, FlowTask, FlowBug):
        result = await session.execute(
            select(model.tags_json).where(model.tags_json != "[]")
        )
        for (raw,) in result:
            for tag in _parse_json_list(raw):
                if tag:
                    names.add(tag)
    return names


_TAG_AUTO_COLORS = [
    "#ef4444", "#d946ef", "#eab308", "#22c55e",
    "#3b82f6", "#f97316", "#14b8a6", "#8b5cf6",
    "#6366f1", "#0ea5e9", "#ec4899", "#f43f5e",
]


async def _sync_missing_tags(session) -> bool:
    """Auto-create FlowTag rows for tags used in work items but not yet defined.
    Returns True if any tags were created."""
    used = await _collect_used_tag_names(session)
    if not used:
        return False
    result = await session.execute(select(FlowTag.name))
    existing = {row[0] for row in result}
    missing = used - existing

    if not missing:
        return False

    max_order_result = await session.execute(
        select(func.coalesce(func.max(FlowTag.sort_order), 0))
    )
    next_order = (max_order_result.scalar() or 0) + 1

    for idx, name in enumerate(sorted(missing)):
        color = _TAG_AUTO_COLORS[(next_order + idx) % len(_TAG_AUTO_COLORS)]
        session.add(FlowTag(name=name, color=color, sort_order=next_order + idx))
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

_STATUS_DEFAULTS: list[dict] = [
    {"name": "意向", "icon": "○", "icon_color": "#64748b", "work_item_types": ["需求"]},
    {"name": "已拒绝", "icon": "⊗", "icon_color": "#ef4444", "work_item_types": []},
    {"name": "设计中", "icon": "✎", "icon_color": "#6366f1", "work_item_types": ["需求"]},
    {"name": "开发中", "icon": "◔", "icon_color": "#3b82f6", "work_item_types": ["需求"]},
    {"name": "开发完成", "icon": "✓", "icon_color": "#22c55e", "work_item_types": ["需求"]},
    {"name": "测试中", "icon": "⊠", "icon_color": "#ef4444", "work_item_types": ["需求"]},
    {"name": "测试完成", "icon": "✓", "icon_color": "#7c3aed", "work_item_types": ["需求"]},
    {"name": "已测完回归中", "icon": "◔", "icon_color": "#3b82f6", "work_item_types": ["需求"]},
    {"name": "待发布", "icon": "◔", "icon_color": "#f59e0b", "work_item_types": ["需求"]},
    {"name": "发布完成", "icon": "✓", "icon_color": "#22c55e", "work_item_types": ["需求"]},
    {"name": "已完成", "icon": "✓", "icon_color": "#22c55e", "work_item_types": ["任务", "需求"]},
    {"name": "已取消", "icon": "⊗", "icon_color": "#ef4444", "work_item_types": ["任务", "需求"]},
    {"name": "暂搁置", "icon": "⊠", "icon_color": "#64748b", "work_item_types": ["需求", "缺陷"]},
    {"name": "待办的", "icon": "○", "icon_color": "#64748b", "work_item_types": ["任务"]},
    {"name": "进行中", "icon": "◔", "icon_color": "#3b82f6", "work_item_types": ["任务"]},
    {"name": "已验收", "icon": "✓", "icon_color": "#22c55e", "work_item_types": []},
    {"name": "待确认", "icon": "○", "icon_color": "#64748b", "work_item_types": ["缺陷"]},
    {"name": "已确认", "icon": "○", "icon_color": "#64748b", "work_item_types": []},
    {"name": "修复中", "icon": "◔", "icon_color": "#3b82f6", "work_item_types": ["缺陷"]},
    {"name": "已修复", "icon": "✓", "icon_color": "#3b82f6", "work_item_types": ["缺陷"]},
    {"name": "已关闭", "icon": "✓", "icon_color": "#64748b", "work_item_types": ["缺陷"]},
    {"name": "无法复现", "icon": "◔", "icon_color": "#f59e0b", "work_item_types": ["缺陷"]},
    {"name": "再次打开", "icon": "⊗", "icon_color": "#ef4444", "work_item_types": ["缺陷"]},
    {"name": "设计如此", "icon": "⊠", "icon_color": "#f59e0b", "work_item_types": ["缺陷"]},
    {"name": "延期修复", "icon": "▷", "icon_color": "#3b82f6", "work_item_types": ["缺陷"]},
]


async def _ensure_default_statuses(session):
    """Seed default statuses if table is empty."""
    count_result = await session.execute(
        select(func.count()).select_from(FlowStatus)
    )
    if (count_result.scalar() or 0) > 0:
        return
    for idx, s in enumerate(_STATUS_DEFAULTS):
        status = FlowStatus(
            name=s["name"],
            icon=s["icon"],
            icon_color=s["icon_color"],
            work_item_types_json=json.dumps(s["work_item_types"], ensure_ascii=False),
            sort_order=idx,
        )
        session.add(status)
    await session.flush()


# ---------------------------------------------------------------------------
# Test module helpers
# ---------------------------------------------------------------------------

async def _get_descendant_module_ids(session, parent_id: str) -> list[str]:
    """Recursively get all descendant module IDs."""
    result = await session.execute(
        select(FlowTestModule.id).where(FlowTestModule.parent_id == parent_id)
    )
    child_ids = [r[0] for r in result.all()]
    all_ids = list(child_ids)
    for cid in child_ids:
        all_ids.extend(await _get_descendant_module_ids(session, cid))
    return all_ids


async def _build_module_path(session, module: FlowTestModule) -> str:
    """Build full path like 'root/child/leaf'."""
    parts = [module.name]
    current = module
    while current.parent_id:
        parent = await session.get(FlowTestModule, current.parent_id)
        if not parent:
            break
        parts.insert(0, parent.name)
        current = parent
    return "/".join(parts)


# ---------------------------------------------------------------------------
# Test-case / work-item link resolver
# ---------------------------------------------------------------------------

async def _resolve_linked_entity(session, link: FlowTestCaseWorkItem) -> dict:
    """Resolve the full info for a link record."""
    from openvort.contacts.models import Member

    base = {
        "link_id": link.id,
        "test_case_id": link.test_case_id,
        "entity_type": link.entity_type,
        "entity_id": link.entity_id,
        "created_at": link.created_at.isoformat() if link.created_at else None,
    }

    tc = await session.get(FlowTestCase, link.test_case_id)
    if tc:
        base["test_case_title"] = tc.title
        base["test_case_priority"] = tc.priority
        base["test_case_case_type"] = tc.case_type
        base["test_case_review_result"] = tc.review_result
        if tc.maintainer_id:
            member = await session.get(Member, tc.maintainer_id)
            base["test_case_maintainer"] = member.name if member else ""
        else:
            base["test_case_maintainer"] = ""

    entity_model = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}.get(link.entity_type)
    if entity_model:
        entity = await session.get(entity_model, link.entity_id)
        if entity:
            base["entity_title"] = entity.title
            base["entity_state"] = entity.state

    return base
