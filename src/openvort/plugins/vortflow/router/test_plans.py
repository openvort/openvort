"""Test Plan CRUD, Plan Cases & Executions."""

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, func, select

from openvort.contacts.models import Member
from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowIteration,
    FlowTestCase,
    FlowTestModule,
    FlowTestPlan,
    FlowTestPlanCase,
    FlowTestPlanExecution,
    FlowVersion,
)
from openvort.web.app import require_auth

from .helpers import (
    _build_module_path,
    _get_descendant_module_ids,
    _resolve_member_name,
    _test_plan_dict,
)

sub_router = APIRouter()


# ============ Pydantic Schemas ============

class TestPlanCreate(BaseModel):
    project_id: str
    title: str
    description: str = ""
    status: str = "in_progress"
    owner_id: str | None = None
    iteration_id: str | None = None
    version_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class TestPlanUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    owner_id: str | None = None
    iteration_id: str | None = None
    version_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class TestPlanAddCasesBody(BaseModel):
    test_case_ids: list[str]


class TestPlanExecutionBody(BaseModel):
    result: str  # passed/blocked/failed/skipped
    executor_id: str | None = None
    notes: str = ""
    bug_id: str | None = None


# ============ Helpers ============

async def _plan_stats(session, plan_id: str) -> dict:
    """Compute execution stats for a single plan."""
    total = (await session.execute(
        select(func.count()).select_from(FlowTestPlanCase)
        .where(FlowTestPlanCase.plan_id == plan_id)
    )).scalar_one()

    # Subquery: latest execution per plan_case
    latest_sq = (
        select(
            FlowTestPlanExecution.plan_case_id,
            func.max(FlowTestPlanExecution.created_at).label("max_ts"),
        )
        .join(FlowTestPlanCase, FlowTestPlanExecution.plan_case_id == FlowTestPlanCase.id)
        .where(FlowTestPlanCase.plan_id == plan_id)
        .group_by(FlowTestPlanExecution.plan_case_id)
        .subquery()
    )
    latest_results = (await session.execute(
        select(FlowTestPlanExecution.result, func.count())
        .join(latest_sq, (FlowTestPlanExecution.plan_case_id == latest_sq.c.plan_case_id)
              & (FlowTestPlanExecution.created_at == latest_sq.c.max_ts))
        .group_by(FlowTestPlanExecution.result)
    )).all()

    passed = failed = blocked = skipped = 0
    for result, cnt in latest_results:
        if result == "passed":
            passed = cnt
        elif result == "failed":
            failed = cnt
        elif result == "blocked":
            blocked = cnt
        elif result == "skipped":
            skipped = cnt
    executed = passed + failed + blocked + skipped

    return {
        "total_cases": total,
        "executed_cases": executed,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "skipped": skipped,
    }


async def _enrich_plan(session, plan: FlowTestPlan) -> dict:
    """Build a full dict for a plan including stats and resolved names."""
    owner_name = await _resolve_member_name(session, plan.owner_id)
    iteration_name = ""
    if plan.iteration_id:
        it = await session.get(FlowIteration, plan.iteration_id)
        iteration_name = it.name if it else ""
    version_name = ""
    if plan.version_id:
        v = await session.get(FlowVersion, plan.version_id)
        version_name = v.name if v else ""
    stats = await _plan_stats(session, plan.id)
    return _test_plan_dict(
        plan,
        owner_name=owner_name,
        iteration_name=iteration_name,
        version_name=version_name,
        **stats,
    )


# ============ Test Plan CRUD ============

@sub_router.get("/test-plans")
async def list_test_plans(
    project_id: str = Query(""),
    status: str = Query(""),
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowTestPlan).order_by(FlowTestPlan.created_at.desc())
        count_stmt = select(func.count()).select_from(FlowTestPlan)
        if project_id:
            stmt = stmt.where(FlowTestPlan.project_id == project_id)
            count_stmt = count_stmt.where(FlowTestPlan.project_id == project_id)
        if status:
            stmt = stmt.where(FlowTestPlan.status == status)
            count_stmt = count_stmt.where(FlowTestPlan.status == status)
        if keyword:
            like = f"%{keyword}%"
            cond = FlowTestPlan.title.ilike(like) | FlowTestPlan.description.ilike(like)
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()

        items = []
        for plan in rows:
            items.append(await _enrich_plan(session, plan))
    return {"total": total, "items": items}


@sub_router.get("/test-plans/{plan_id}")
async def get_test_plan(plan_id: str):
    sf = get_session_factory()
    async with sf() as session:
        plan = await session.get(FlowTestPlan, plan_id)
        if not plan:
            return {"error": "测试计划不存在"}
        return await _enrich_plan(session, plan)


@sub_router.post("/test-plans")
async def create_test_plan(body: TestPlanCreate, request: Request):
    require_auth(request)
    sf = get_session_factory()
    async with sf() as session:
        plan = FlowTestPlan(
            project_id=body.project_id,
            title=body.title,
            description=body.description,
            status=body.status,
            owner_id=body.owner_id,
            iteration_id=body.iteration_id or None,
            version_id=body.version_id or None,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        session.add(plan)
        await session.commit()
        await session.refresh(plan)
        return await _enrich_plan(session, plan)


@sub_router.put("/test-plans/{plan_id}")
async def update_test_plan(plan_id: str, body: TestPlanUpdate):
    sf = get_session_factory()
    async with sf() as session:
        plan = await session.get(FlowTestPlan, plan_id)
        if not plan:
            return {"error": "测试计划不存在"}
        for field in ["title", "description", "status", "owner_id", "start_date", "end_date"]:
            val = getattr(body, field)
            if val is not None:
                setattr(plan, field, val)
        if body.iteration_id is not None:
            plan.iteration_id = body.iteration_id or None
        if body.version_id is not None:
            plan.version_id = body.version_id or None
        await session.commit()
        await session.refresh(plan)
        return await _enrich_plan(session, plan)


@sub_router.delete("/test-plans/{plan_id}")
async def delete_test_plan(plan_id: str):
    sf = get_session_factory()
    async with sf() as session:
        plan = await session.get(FlowTestPlan, plan_id)
        if not plan:
            return {"error": "测试计划不存在"}
        # Cascade: executions -> plan_cases -> plan
        case_ids_result = await session.execute(
            select(FlowTestPlanCase.id).where(FlowTestPlanCase.plan_id == plan_id)
        )
        case_ids = [r[0] for r in case_ids_result.all()]
        if case_ids:
            await session.execute(
                sa_delete(FlowTestPlanExecution)
                .where(FlowTestPlanExecution.plan_case_id.in_(case_ids))
            )
        await session.execute(
            sa_delete(FlowTestPlanCase).where(FlowTestPlanCase.plan_id == plan_id)
        )
        await session.delete(plan)
        await session.commit()
    return {"ok": True}


@sub_router.post("/test-plans/{plan_id}/copy")
async def copy_test_plan(plan_id: str, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        src = await session.get(FlowTestPlan, plan_id)
        if not src:
            return {"error": "测试计划不存在"}
        new_plan = FlowTestPlan(
            project_id=src.project_id,
            title=f"{src.title} (副本)",
            description=src.description,
            status="in_progress",
            owner_id=src.owner_id,
            iteration_id=src.iteration_id,
            version_id=src.version_id,
            start_date=src.start_date,
            end_date=src.end_date,
        )
        session.add(new_plan)
        await session.flush()

        case_rows = (await session.execute(
            select(FlowTestPlanCase)
            .where(FlowTestPlanCase.plan_id == plan_id)
            .order_by(FlowTestPlanCase.sort_order)
        )).scalars().all()
        for pc in case_rows:
            session.add(FlowTestPlanCase(
                plan_id=new_plan.id,
                test_case_id=pc.test_case_id,
                sort_order=pc.sort_order,
                created_by=member_id or None,
            ))
        await session.commit()
        await session.refresh(new_plan)
        return await _enrich_plan(session, new_plan)


# ============ Plan Cases ============

@sub_router.get("/test-plans/{plan_id}/cases")
async def list_plan_cases(
    plan_id: str,
    module_id: str = Query(""),
    keyword: str = Query(""),
    case_type: str = Query(""),
    priority: str = Query(""),
    latest_result: str = Query(""),
    sort_by: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowTestPlanCase, FlowTestCase)
            .join(FlowTestCase, FlowTestPlanCase.test_case_id == FlowTestCase.id)
            .where(FlowTestPlanCase.plan_id == plan_id)
        )
        count_stmt = (
            select(func.count()).select_from(FlowTestPlanCase)
            .join(FlowTestCase, FlowTestPlanCase.test_case_id == FlowTestCase.id)
            .where(FlowTestPlanCase.plan_id == plan_id)
        )
        if module_id:
            descendant_ids = await _get_descendant_module_ids(session, module_id)
            all_module_ids = [module_id] + descendant_ids
            stmt = stmt.where(FlowTestCase.module_id.in_(all_module_ids))
            count_stmt = count_stmt.where(FlowTestCase.module_id.in_(all_module_ids))
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(FlowTestCase.title.ilike(like))
            count_stmt = count_stmt.where(FlowTestCase.title.ilike(like))
        if case_type:
            stmt = stmt.where(FlowTestCase.case_type == case_type)
            count_stmt = count_stmt.where(FlowTestCase.case_type == case_type)
        if priority:
            stmt = stmt.where(FlowTestCase.priority == int(priority))
            count_stmt = count_stmt.where(FlowTestCase.priority == int(priority))

        total = (await session.execute(count_stmt)).scalar_one()

        if sort_by == "priority":
            stmt = stmt.order_by(FlowTestCase.priority.asc())
        else:
            stmt = stmt.order_by(FlowTestPlanCase.sort_order.asc(), FlowTestPlanCase.created_at.asc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).all()

        # Batch-load modules, members, executions
        all_module_ids_set: set[str] = set()
        all_member_ids_set: set[str] = set()
        plan_case_ids: list[str] = []
        for pc, tc in rows:
            plan_case_ids.append(pc.id)
            if tc.module_id:
                all_module_ids_set.add(tc.module_id)
            if tc.maintainer_id:
                all_member_ids_set.add(tc.maintainer_id)

        module_map: dict[str, FlowTestModule] = {}
        if all_module_ids_set:
            mods = (await session.execute(
                select(FlowTestModule).where(FlowTestModule.id.in_(list(all_module_ids_set)))
            )).scalars().all()
            module_map = {m.id: m for m in mods}

        member_map: dict[str, str] = {}
        if all_member_ids_set:
            members = (await session.execute(
                select(Member).where(Member.id.in_(list(all_member_ids_set)))
            )).scalars().all()
            member_map = {m.id: m.name for m in members}

        # Latest execution per plan_case
        exec_map: dict[str, list[dict]] = {}
        latest_exec_map: dict[str, str] = {}
        if plan_case_ids:
            latest_sq = (
                select(
                    FlowTestPlanExecution.plan_case_id,
                    func.max(FlowTestPlanExecution.created_at).label("max_ts"),
                )
                .where(FlowTestPlanExecution.plan_case_id.in_(plan_case_ids))
                .group_by(FlowTestPlanExecution.plan_case_id)
                .subquery()
            )
            latest_execs = (await session.execute(
                select(FlowTestPlanExecution)
                .join(latest_sq, (FlowTestPlanExecution.plan_case_id == latest_sq.c.plan_case_id)
                      & (FlowTestPlanExecution.created_at == latest_sq.c.max_ts))
            )).scalars().all()
            for ex in latest_execs:
                latest_exec_map[ex.plan_case_id] = ex.result

            # All executions grouped by plan_case_id (for distribution)
            all_execs = (await session.execute(
                select(FlowTestPlanExecution)
                .where(FlowTestPlanExecution.plan_case_id.in_(plan_case_ids))
                .order_by(FlowTestPlanExecution.created_at.desc())
            )).scalars().all()
            for ex in all_execs:
                exec_map.setdefault(ex.plan_case_id, []).append({
                    "id": ex.id,
                    "result": ex.result,
                    "executor_id": ex.executor_id,
                    "notes": ex.notes,
                    "bug_id": ex.bug_id,
                    "created_at": ex.created_at.isoformat() if ex.created_at else None,
                })

        # Filter by latest_result after computing
        items = []
        for pc, tc in rows:
            lr = latest_exec_map.get(pc.id, "")
            if latest_result and lr != latest_result:
                continue
            module = module_map.get(tc.module_id) if tc.module_id else None
            module_name = module.name if module else ""
            module_path = await _build_module_path(session, module) if module else ""
            execs = exec_map.get(pc.id, [])
            exec_dist = {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0}
            for e in execs:
                if e["result"] in exec_dist:
                    exec_dist[e["result"]] += 1

            items.append({
                "plan_case_id": pc.id,
                "test_case_id": tc.id,
                "sort_order": pc.sort_order,
                "title": tc.title,
                "case_type": tc.case_type,
                "priority": tc.priority,
                "module_id": tc.module_id,
                "module_name": module_name,
                "module_path": module_path,
                "maintainer_id": tc.maintainer_id,
                "maintainer_name": member_map.get(tc.maintainer_id, "") if tc.maintainer_id else "",
                "latest_result": lr,
                "execution_count": len(execs),
                "execution_distribution": exec_dist,
            })

        if latest_result:
            total = len(items)

    return {"total": total, "items": items}


@sub_router.post("/test-plans/{plan_id}/cases")
async def add_plan_cases(plan_id: str, body: TestPlanAddCasesBody, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        plan = await session.get(FlowTestPlan, plan_id)
        if not plan:
            return {"error": "测试计划不存在"}

        existing = (await session.execute(
            select(FlowTestPlanCase.test_case_id)
            .where(FlowTestPlanCase.plan_id == plan_id)
        )).scalars().all()
        existing_set = set(existing)

        max_order = (await session.execute(
            select(func.coalesce(func.max(FlowTestPlanCase.sort_order), 0))
            .where(FlowTestPlanCase.plan_id == plan_id)
        )).scalar_one()

        added = 0
        for tc_id in body.test_case_ids:
            if tc_id in existing_set:
                continue
            max_order += 1
            session.add(FlowTestPlanCase(
                plan_id=plan_id,
                test_case_id=tc_id,
                sort_order=max_order,
                created_by=member_id or None,
            ))
            added += 1
        await session.commit()
    return {"ok": True, "added": added}


@sub_router.delete("/test-plans/{plan_id}/cases/{plan_case_id}")
async def remove_plan_case(plan_id: str, plan_case_id: str):
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(
            sa_delete(FlowTestPlanExecution)
            .where(FlowTestPlanExecution.plan_case_id == plan_case_id)
        )
        await session.execute(
            sa_delete(FlowTestPlanCase)
            .where(FlowTestPlanCase.id == plan_case_id, FlowTestPlanCase.plan_id == plan_id)
        )
        await session.commit()
    return {"ok": True}


# ============ Executions ============

@sub_router.post("/test-plans/{plan_id}/cases/{plan_case_id}/executions")
async def add_execution(plan_id: str, plan_case_id: str, body: TestPlanExecutionBody, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        pc = await session.get(FlowTestPlanCase, plan_case_id)
        if not pc or pc.plan_id != plan_id:
            return {"error": "计划用例不存在"}
        ex = FlowTestPlanExecution(
            plan_case_id=plan_case_id,
            result=body.result,
            executor_id=body.executor_id or member_id or None,
            notes=body.notes,
            bug_id=body.bug_id,
        )
        session.add(ex)
        await session.commit()
        await session.refresh(ex)
    return {
        "id": ex.id,
        "plan_case_id": ex.plan_case_id,
        "result": ex.result,
        "executor_id": ex.executor_id,
        "notes": ex.notes,
        "bug_id": ex.bug_id,
        "created_at": ex.created_at.isoformat() if ex.created_at else None,
    }


@sub_router.get("/test-plans/{plan_id}/cases/{plan_case_id}/executions")
async def list_executions(plan_id: str, plan_case_id: str):
    sf = get_session_factory()
    async with sf() as session:
        pc = await session.get(FlowTestPlanCase, plan_case_id)
        if not pc or pc.plan_id != plan_id:
            return {"error": "计划用例不存在"}
        rows = (await session.execute(
            select(FlowTestPlanExecution)
            .where(FlowTestPlanExecution.plan_case_id == plan_case_id)
            .order_by(FlowTestPlanExecution.created_at.desc())
        )).scalars().all()

        items = []
        for ex in rows:
            executor_name = await _resolve_member_name(session, ex.executor_id)
            items.append({
                "id": ex.id,
                "plan_case_id": ex.plan_case_id,
                "result": ex.result,
                "executor_id": ex.executor_id,
                "executor_name": executor_name,
                "notes": ex.notes,
                "bug_id": ex.bug_id,
                "created_at": ex.created_at.isoformat() if ex.created_at else None,
            })
    return {"items": items}
