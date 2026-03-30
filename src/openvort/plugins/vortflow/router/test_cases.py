import json

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, func, select

from openvort.contacts.models import Member
from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowBug, FlowStory, FlowTask,
    FlowTestCase, FlowTestCaseWorkItem, FlowTestModule,
)
from openvort.web.app import require_auth

from .helpers import (
    _build_module_path, _get_descendant_module_ids, _resolve_linked_entity,
    _resolve_member_name, _test_case_dict, _test_module_dict,
)

sub_router = APIRouter()


class TestModuleCreate(BaseModel):
    project_id: str
    parent_id: str | None = None
    name: str


class TestModuleUpdate(BaseModel):
    name: str | None = None
    parent_id: str | None = None
    sort_order: int | None = None


class TestModuleReorder(BaseModel):
    module_id: str
    parent_id: str | None = None
    target_index: int = 0


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


# ============ Test Modules ============

@sub_router.get("/test-modules")
async def list_test_modules(project_id: str = Query("", alias="project_id")):
    sf = get_session_factory()
    async with sf() as session:
        query = select(FlowTestModule).order_by(FlowTestModule.sort_order, FlowTestModule.created_at)
        if project_id:
            query = query.where(FlowTestModule.project_id == project_id)
        result = await session.execute(query)
        modules = result.scalars().all()

        module_ids = [m.id for m in modules]
        counts: dict[str, int] = {}
        if module_ids:
            count_q = (
                select(FlowTestCase.module_id, func.count())
                .where(FlowTestCase.module_id.in_(module_ids))
                .group_by(FlowTestCase.module_id)
            )
            count_result = await session.execute(count_q)
            counts = dict(count_result.all())

    items = []
    for m in modules:
        d = _test_module_dict(m)
        d["case_count"] = counts.get(m.id, 0)
        items.append(d)
    return {"items": items}


@sub_router.post("/test-modules")
async def create_test_module(body: TestModuleCreate, request: Request = None):
    sf = get_session_factory()
    async with sf() as session:
        max_order = await session.execute(
            select(func.coalesce(func.max(FlowTestModule.sort_order), 0))
            .where(FlowTestModule.project_id == body.project_id)
            .where(FlowTestModule.parent_id == body.parent_id)
        )
        next_order = (max_order.scalar() or 0) + 1
        module = FlowTestModule(
            project_id=body.project_id,
            parent_id=body.parent_id,
            name=body.name,
            sort_order=next_order,
        )
        session.add(module)
        await session.commit()
        await session.refresh(module)
    return _test_module_dict(module)


@sub_router.put("/test-modules/{module_id}")
async def update_test_module(module_id: str, body: TestModuleUpdate):
    sf = get_session_factory()
    async with sf() as session:
        module = await session.get(FlowTestModule, module_id)
        if not module:
            return {"error": "模块不存在"}
        if body.name is not None:
            module.name = body.name
        if body.parent_id is not None:
            module.parent_id = body.parent_id if body.parent_id else None
        if body.sort_order is not None:
            module.sort_order = body.sort_order
        await session.commit()
        await session.refresh(module)
    return _test_module_dict(module)


@sub_router.delete("/test-modules/{module_id}")
async def delete_test_module(module_id: str):
    sf = get_session_factory()
    async with sf() as session:
        module = await session.get(FlowTestModule, module_id)
        if not module:
            return {"error": "模块不存在"}
        children = await session.execute(
            select(FlowTestModule).where(FlowTestModule.parent_id == module_id)
        )
        if children.scalars().first():
            return {"error": "请先删除子模块"}
        await session.execute(
            select(FlowTestCase).where(FlowTestCase.module_id == module_id)
        )
        update_cases = await session.execute(
            select(FlowTestCase).where(FlowTestCase.module_id == module_id)
        )
        for tc in update_cases.scalars().all():
            tc.module_id = None
        await session.delete(module)
        await session.commit()
    return {"ok": True}


@sub_router.post("/test-modules/reorder")
async def reorder_test_module(body: TestModuleReorder):
    sf = get_session_factory()
    async with sf() as session:
        module = await session.get(FlowTestModule, body.module_id)
        if not module:
            return {"error": "模块不存在"}

        new_parent_id = body.parent_id if body.parent_id else None

        if new_parent_id:
            descendant_ids = await _get_descendant_module_ids(session, body.module_id)
            if new_parent_id in descendant_ids:
                return {"error": "不能将模块移动到其子模块下"}

        module.parent_id = new_parent_id

        if new_parent_id:
            siblings_q = select(FlowTestModule).where(
                FlowTestModule.project_id == module.project_id,
                FlowTestModule.parent_id == new_parent_id,
                FlowTestModule.id != body.module_id,
            )
        else:
            siblings_q = select(FlowTestModule).where(
                FlowTestModule.project_id == module.project_id,
                FlowTestModule.parent_id.is_(None),
                FlowTestModule.id != body.module_id,
            )
        siblings_q = siblings_q.order_by(FlowTestModule.sort_order, FlowTestModule.created_at)
        result = await session.execute(siblings_q)
        siblings = list(result.scalars().all())

        idx = min(body.target_index, len(siblings))
        siblings.insert(idx, module)
        for i, s in enumerate(siblings):
            s.sort_order = i

        await session.commit()
    return {"ok": True}


# ============ Test Cases ============

@sub_router.get("/test-cases")
async def list_test_cases(
    project_id: str = Query("", alias="project_id"),
    module_id: str = Query("", alias="module_id"),
    keyword: str = Query("", alias="keyword"),
    case_type: str = Query("", alias="case_type"),
    priority: int | None = Query(None, alias="priority"),
    review_result: str = Query("", alias="review_result"),
    maintainer_id: str = Query("", alias="maintainer_id"),
    page: int = Query(1, alias="page"),
    page_size: int = Query(20, alias="page_size"),
):
    sf = get_session_factory()

    async with sf() as session:
        query = select(FlowTestCase)

        if project_id:
            query = query.where(FlowTestCase.project_id == project_id)
        if module_id:
            all_module_ids = await _get_descendant_module_ids(session, module_id)
            all_module_ids.append(module_id)
            query = query.where(FlowTestCase.module_id.in_(all_module_ids))
        if keyword.strip():
            query = query.where(FlowTestCase.title.contains(keyword.strip()))
        if case_type:
            query = query.where(FlowTestCase.case_type == case_type)
        if priority is not None:
            query = query.where(FlowTestCase.priority == priority)
        if review_result:
            query = query.where(FlowTestCase.review_result == review_result)
        if maintainer_id:
            query = query.where(FlowTestCase.maintainer_id == maintainer_id)

        count_q = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        query = query.order_by(FlowTestCase.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(query)
        cases = result.scalars().all()

        member_ids = list({tc.maintainer_id for tc in cases if tc.maintainer_id})
        members_map: dict[str, str] = {}
        if member_ids:
            mr = await session.execute(select(Member).where(Member.id.in_(member_ids)))
            for m in mr.scalars().all():
                members_map[m.id] = m.name

        module_ids = list({tc.module_id for tc in cases if tc.module_id})
        modules_map: dict[str, FlowTestModule] = {}
        if module_ids:
            mr = await session.execute(select(FlowTestModule).where(FlowTestModule.id.in_(module_ids)))
            for mod in mr.scalars().all():
                modules_map[mod.id] = mod

    items = []
    for tc in cases:
        mod = modules_map.get(tc.module_id) if tc.module_id else None
        items.append(_test_case_dict(
            tc,
            maintainer_name=members_map.get(tc.maintainer_id, "") if tc.maintainer_id else "",
            module_name=mod.name if mod else "",
        ))
    return {"items": items, "total": total}


@sub_router.get("/test-cases/{case_id}")
async def get_test_case(case_id: str):
    sf = get_session_factory()

    async with sf() as session:
        tc = await session.get(FlowTestCase, case_id)
        if not tc:
            return {"error": "用例不存在"}
        maintainer_name = ""
        if tc.maintainer_id:
            member = await session.get(Member, tc.maintainer_id)
            maintainer_name = member.name if member else ""
        module_name = ""
        module_path = ""
        if tc.module_id:
            mod = await session.get(FlowTestModule, tc.module_id)
            if mod:
                module_name = mod.name
                module_path = await _build_module_path(session, mod)

        link_count = await session.execute(
            select(func.count()).select_from(FlowTestCaseWorkItem)
            .where(FlowTestCaseWorkItem.test_case_id == case_id)
        )

    d = _test_case_dict(tc, maintainer_name=maintainer_name, module_name=module_name, module_path=module_path)
    d["linked_work_item_count"] = link_count.scalar() or 0
    return d


@sub_router.post("/test-cases")
async def create_test_case(body: TestCaseCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        tc = FlowTestCase(
            project_id=body.project_id,
            module_id=body.module_id,
            title=body.title,
            precondition=body.precondition,
            notes=body.notes,
            case_type=body.case_type,
            priority=body.priority,
            maintainer_id=body.maintainer_id or member_id,
            steps_json=json.dumps(body.steps, ensure_ascii=False),
        )
        session.add(tc)
        await session.commit()
        await session.refresh(tc)
    return _test_case_dict(tc)


@sub_router.put("/test-cases/{case_id}")
async def update_test_case(case_id: str, body: TestCaseUpdate):
    sf = get_session_factory()
    async with sf() as session:
        tc = await session.get(FlowTestCase, case_id)
        if not tc:
            return {"error": "用例不存在"}
        if body.module_id is not None:
            tc.module_id = body.module_id if body.module_id else None
        if body.title is not None:
            tc.title = body.title
        if body.precondition is not None:
            tc.precondition = body.precondition
        if body.notes is not None:
            tc.notes = body.notes
        if body.case_type is not None:
            tc.case_type = body.case_type
        if body.priority is not None:
            tc.priority = body.priority
        if body.maintainer_id is not None:
            tc.maintainer_id = body.maintainer_id if body.maintainer_id else None
        if body.review_result is not None:
            tc.review_result = body.review_result
        if body.steps is not None:
            tc.steps_json = json.dumps(body.steps, ensure_ascii=False)
        await session.commit()
        await session.refresh(tc)
    return _test_case_dict(tc)


@sub_router.delete("/test-cases/{case_id}")
async def delete_test_case(case_id: str):
    sf = get_session_factory()
    async with sf() as session:
        tc = await session.get(FlowTestCase, case_id)
        if not tc:
            return {"error": "用例不存在"}
        await session.execute(
            sa_delete(FlowTestCaseWorkItem).where(FlowTestCaseWorkItem.test_case_id == case_id)
        )
        await session.delete(tc)
        await session.commit()
    return {"ok": True}


# ============ Test Case - Work Item Links ============

@sub_router.get("/test-case-links")
async def list_test_case_links(
    test_case_id: str = Query("", alias="test_case_id"),
    entity_type: str = Query("", alias="entity_type"),
    entity_id: str = Query("", alias="entity_id"),
):
    """Query links. Supports two directions:
    1. By test_case_id: get all work items linked to a test case
    2. By entity_type+entity_id: get all test cases linked to a work item
    """
    sf = get_session_factory()

    async with sf() as session:
        query = select(FlowTestCaseWorkItem)
        if test_case_id:
            query = query.where(FlowTestCaseWorkItem.test_case_id == test_case_id)
        if entity_type and entity_id:
            query = query.where(
                FlowTestCaseWorkItem.entity_type == entity_type,
                FlowTestCaseWorkItem.entity_id == entity_id,
            )
        result = await session.execute(query)
        links = result.scalars().all()

        items = []
        for link in links:
            item_data = await _resolve_linked_entity(session, link)
            items.append(item_data)

    return {"items": items}


@sub_router.post("/test-case-links")
async def create_test_case_link(body: TestCaseWorkItemBody, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.execute(
            select(FlowTestCaseWorkItem).where(
                FlowTestCaseWorkItem.test_case_id == body.test_case_id,
                FlowTestCaseWorkItem.entity_type == body.entity_type,
                FlowTestCaseWorkItem.entity_id == body.entity_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "已存在相同关联"}
        link = FlowTestCaseWorkItem(
            test_case_id=body.test_case_id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            created_by=member_id,
        )
        session.add(link)
        await session.commit()
        await session.refresh(link)
    return {"id": link.id, "ok": True}


@sub_router.delete("/test-case-links/{link_id}")
async def delete_test_case_link(link_id: str):
    sf = get_session_factory()
    async with sf() as session:
        link = await session.get(FlowTestCaseWorkItem, link_id)
        if not link:
            return {"error": "关联不存在"}
        await session.delete(link)
        await session.commit()
    return {"ok": True}
