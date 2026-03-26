"""Test Plan CRUD, Plan Cases, Executions & Code Reviews."""

from fastapi import APIRouter, HTTPException, Query, Request
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
    FlowTestPlanReview,
    FlowTestPlanReviewHistory,
    FlowVersion,
)
from openvort.utils.logging import get_logger
from openvort.web.app import require_auth

from .helpers import (
    _build_module_path,
    _get_descendant_module_ids,
    _resolve_member_name,
    _test_plan_dict,
)

log = get_logger("plugins.vortflow.test_plans")

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


class TestPlanAddReviewsBody(BaseModel):
    reviews: list[dict]  # [{repo_id, pr_number, pr_url, pr_title, head_branch, base_branch}]


class TestPlanUpdateReviewBody(BaseModel):
    reviewer_id: str | None = None
    review_status: str | None = None  # pending/approved/rejected/changes_requested
    review_notes: str | None = None
    is_ai: bool = False


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


async def _review_stats(session, plan_id: str) -> dict:
    """Compute code review stats for a single plan."""
    rows = (await session.execute(
        select(FlowTestPlanReview.review_status, func.count())
        .where(FlowTestPlanReview.plan_id == plan_id)
        .group_by(FlowTestPlanReview.review_status)
    )).all()
    total = pending = approved = rejected = changes_requested = 0
    for status, cnt in rows:
        total += cnt
        if status == "pending":
            pending = cnt
        elif status == "approved":
            approved = cnt
        elif status == "rejected":
            rejected = cnt
        elif status == "changes_requested":
            changes_requested = cnt
    return {
        "review_total": total,
        "review_pending": pending,
        "review_approved": approved,
        "review_rejected": rejected,
        "review_changes_requested": changes_requested,
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
    r_stats = await _review_stats(session, plan.id)
    return {
        **_test_plan_dict(
            plan,
            owner_name=owner_name,
            iteration_name=iteration_name,
            version_name=version_name,
            **stats,
        ),
        **r_stats,
    }


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
    if not body.project_id or not body.project_id.strip():
        raise HTTPException(status_code=400, detail="project_id 不能为空")
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
        # Cascade: executions -> plan_cases -> reviews -> plan
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
        review_ids_result = await session.execute(
            select(FlowTestPlanReview.id).where(FlowTestPlanReview.plan_id == plan_id)
        )
        review_ids = [r[0] for r in review_ids_result.all()]
        if review_ids:
            await session.execute(
                sa_delete(FlowTestPlanReviewHistory)
                .where(FlowTestPlanReviewHistory.review_id.in_(review_ids))
            )
        await session.execute(
            sa_delete(FlowTestPlanReview).where(FlowTestPlanReview.plan_id == plan_id)
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


# ============ Code Reviews ============

def _review_to_dict(r: FlowTestPlanReview, *, reviewer_name: str = "", repo_name: str = "") -> dict:
    return {
        "id": r.id,
        "plan_id": r.plan_id,
        "repo_id": r.repo_id,
        "repo_name": repo_name,
        "pr_number": r.pr_number,
        "pr_url": r.pr_url,
        "pr_title": r.pr_title,
        "head_branch": r.head_branch,
        "base_branch": r.base_branch,
        "reviewer_id": r.reviewer_id,
        "reviewer_name": reviewer_name,
        "review_status": r.review_status,
        "review_notes": r.review_notes,
        "added_by": r.added_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@sub_router.get("/test-plans/{plan_id}/reviews")
async def list_plan_reviews(plan_id: str):
    sf = get_session_factory()
    async with sf() as session:
        rows = (await session.execute(
            select(FlowTestPlanReview)
            .where(FlowTestPlanReview.plan_id == plan_id)
            .order_by(FlowTestPlanReview.created_at.desc())
        )).scalars().all()

        # Batch-resolve repo names and reviewer names
        from openvort.plugins.vortgit.models import GitRepo
        repo_ids = {r.repo_id for r in rows if r.repo_id}
        repo_map: dict[str, str] = {}
        if repo_ids:
            repos = (await session.execute(
                select(GitRepo).where(GitRepo.id.in_(list(repo_ids)))
            )).scalars().all()
            repo_map = {r.id: r.name for r in repos}

        member_ids = {r.reviewer_id for r in rows if r.reviewer_id}
        member_map: dict[str, str] = {}
        if member_ids:
            members = (await session.execute(
                select(Member).where(Member.id.in_(list(member_ids)))
            )).scalars().all()
            member_map = {m.id: m.name for m in members}

        items = [
            _review_to_dict(
                r,
                reviewer_name=member_map.get(r.reviewer_id, "") if r.reviewer_id else "",
                repo_name=repo_map.get(r.repo_id, ""),
            )
            for r in rows
        ]
    return {"items": items}


@sub_router.post("/test-plans/{plan_id}/reviews")
async def add_plan_reviews(plan_id: str, body: TestPlanAddReviewsBody, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        plan = await session.get(FlowTestPlan, plan_id)
        if not plan:
            return {"error": "测试计划不存在"}

        existing = (await session.execute(
            select(FlowTestPlanReview.repo_id, FlowTestPlanReview.pr_number)
            .where(FlowTestPlanReview.plan_id == plan_id)
        )).all()
        existing_set = {(r[0], r[1]) for r in existing}

        added = 0
        for item in body.reviews:
            repo_id = item.get("repo_id", "")
            pr_number = item.get("pr_number", 0)
            if not repo_id or not pr_number:
                continue
            if (repo_id, pr_number) in existing_set:
                continue
            session.add(FlowTestPlanReview(
                plan_id=plan_id,
                repo_id=repo_id,
                pr_number=pr_number,
                pr_url=item.get("pr_url", ""),
                pr_title=item.get("pr_title", ""),
                head_branch=item.get("head_branch", ""),
                base_branch=item.get("base_branch", ""),
                added_by=member_id or None,
            ))
            added += 1
        await session.commit()
    return {"ok": True, "added": added}


@sub_router.put("/test-plans/{plan_id}/reviews/{review_id}")
async def update_plan_review(plan_id: str, review_id: str, body: TestPlanUpdateReviewBody, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        review = await session.get(FlowTestPlanReview, review_id)
        if not review or review.plan_id != plan_id:
            return {"error": "评审项不存在"}

        old_status = review.review_status

        if body.reviewer_id is not None:
            old_reviewer = review.reviewer_id
            review.reviewer_id = body.reviewer_id or None
            if old_reviewer != review.reviewer_id:
                session.add(FlowTestPlanReviewHistory(
                    review_id=review_id, action="reviewer_assigned",
                    notes=f"评审人变更", actor_id=actor_id or None,
                ))

        if body.review_status is not None:
            review.review_status = body.review_status
        if body.review_notes is not None:
            review.review_notes = body.review_notes

        if body.review_status and body.review_status != old_status:
            session.add(FlowTestPlanReviewHistory(
                review_id=review_id, action="status_changed",
                old_status=old_status, new_status=body.review_status,
                notes=body.review_notes or "", actor_id=actor_id or None,
                is_ai=body.is_ai if hasattr(body, "is_ai") else False,
            ))

        await session.commit()
        await session.refresh(review)
        reviewer_name = await _resolve_member_name(session, review.reviewer_id)
        from openvort.plugins.vortgit.models import GitRepo
        repo = await session.get(GitRepo, review.repo_id)
        return _review_to_dict(review, reviewer_name=reviewer_name, repo_name=repo.name if repo else "")


@sub_router.delete("/test-plans/{plan_id}/reviews/{review_id}")
async def remove_plan_review(plan_id: str, review_id: str):
    sf = get_session_factory()
    async with sf() as session:
        review = await session.get(FlowTestPlanReview, review_id)
        if not review or review.plan_id != plan_id:
            return {"error": "评审项不存在"}
        await session.execute(
            sa_delete(FlowTestPlanReviewHistory)
            .where(FlowTestPlanReviewHistory.review_id == review_id)
        )
        await session.delete(review)
        await session.commit()
    return {"ok": True}


@sub_router.get("/test-plans/{plan_id}/available-prs")
async def list_available_prs(plan_id: str, repo_id: str = Query(...)):
    """Fetch open PRs from a Git repo via VortGit provider."""
    from openvort.plugins.vortgit.models import GitProvider, GitRepo

    sf = get_session_factory()
    async with sf() as session:
        repo = await session.get(GitRepo, repo_id)
        if not repo:
            raise HTTPException(404, "仓库不存在")
        provider = await session.get(GitProvider, repo.provider_id)
        if not provider:
            raise HTTPException(404, "Git 平台配置不存在")

        already = (await session.execute(
            select(FlowTestPlanReview.pr_number)
            .where(FlowTestPlanReview.plan_id == plan_id, FlowTestPlanReview.repo_id == repo_id)
        )).scalars().all()
        already_set = set(already)

    client = _create_git_client(provider)
    try:
        prs = await client.list_pull_requests(repo.full_name, state="open", per_page=50)
    except Exception as e:
        log.error(f"Failed to fetch PRs from repo {repo.full_name}: {e}")
        raise HTTPException(502, f"获取 PR 列表失败: {e}")
    finally:
        await client.close()

    items = []
    for pr in prs:
        items.append({
            **pr,
            "already_added": pr.get("number", 0) in already_set,
        })
    return {"items": items}


# ============ Review History ============

@sub_router.get("/test-plans/{plan_id}/reviews/{review_id}/history")
async def list_review_history(plan_id: str, review_id: str):
    sf = get_session_factory()
    async with sf() as session:
        review = await session.get(FlowTestPlanReview, review_id)
        if not review or review.plan_id != plan_id:
            return {"error": "评审项不存在"}
        rows = (await session.execute(
            select(FlowTestPlanReviewHistory)
            .where(FlowTestPlanReviewHistory.review_id == review_id)
            .order_by(FlowTestPlanReviewHistory.created_at.desc())
        )).scalars().all()

        member_ids = {r.actor_id for r in rows if r.actor_id}
        member_map: dict[str, str] = {}
        if member_ids:
            members = (await session.execute(
                select(Member).where(Member.id.in_(list(member_ids)))
            )).scalars().all()
            member_map = {m.id: m.name for m in members}

        items = [{
            "id": r.id,
            "review_id": r.review_id,
            "action": r.action,
            "old_status": r.old_status,
            "new_status": r.new_status,
            "notes": r.notes,
            "actor_id": r.actor_id,
            "actor_name": member_map.get(r.actor_id, "") if r.actor_id else "",
            "is_ai": r.is_ai,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]
    return {"items": items}


# ============ AI Code Review ============

def _create_git_client(provider):
    """Create a git provider client."""
    from openvort.plugins.vortgit.crypto import decrypt_token
    token = decrypt_token(provider.access_token) if provider.access_token else ""
    if provider.platform == "gitee":
        from openvort.plugins.vortgit.providers.gitee import GiteeProvider
        return GiteeProvider(access_token=token, api_base=provider.api_base)
    raise HTTPException(400, f"暂不支持的平台: {provider.platform}")


@sub_router.post("/test-plans/{plan_id}/reviews/{review_id}/ai-review")
async def ai_review(plan_id: str, review_id: str, request: Request):
    """Use LLM to review PR code changes."""
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
    from openvort.plugins.vortgit.models import GitProvider, GitRepo

    sf = get_session_factory()
    async with sf() as session:
        review = await session.get(FlowTestPlanReview, review_id)
        if not review or review.plan_id != plan_id:
            return {"error": "评审项不存在"}
        repo = await session.get(GitRepo, review.repo_id)
        if not repo:
            return {"error": "仓库不存在"}
        provider = await session.get(GitProvider, repo.provider_id)
        if not provider:
            return {"error": "Git 平台配置不存在"}

    client = _create_git_client(provider)
    try:
        files = await client.get_pull_request_files(repo.full_name, review.pr_number)
        pr_detail = await client.get_pull_request_detail(repo.full_name, review.pr_number)
    except Exception as e:
        log.error(f"Failed to fetch PR data for AI review: {e}")
        raise HTTPException(502, f"获取 PR 数据失败: {e}")
    finally:
        await client.close()

    diff_parts = []
    for f in files[:30]:
        header = f"--- {f.get('filename', '')}\n"
        patch = f.get("patch", "")
        if patch and isinstance(patch, str):
            diff_parts.append(header + patch)
        elif isinstance(patch, dict):
            diff_parts.append(header + str(patch.get("diff", patch)))
    diff_text = "\n".join(diff_parts)
    if len(diff_text) > 30000:
        diff_text = diff_text[:30000] + "\n... (diff truncated)"

    pr_body = pr_detail.get("body", "") or ""
    prompt = (
        "你是一名资深代码评审员。请审查以下 Pull Request 的代码变更。\n\n"
        f"## PR 信息\n"
        f"标题：{review.pr_title}\n"
        f"描述：{pr_body[:500]}\n"
        f"分支：{review.head_branch} → {review.base_branch}\n\n"
        f"## 代码变更\n```diff\n{diff_text}\n```\n\n"
        "请从以下维度评审：\n"
        "1. 代码逻辑正确性\n"
        "2. 安全隐患\n"
        "3. 性能问题\n"
        "4. 代码风格和可维护性\n"
        "5. 是否有遗漏的边界情况\n\n"
        "请用中文回复。先给出评审结论（通过 / 需修改），然后逐条列出发现的问题（如果有）。\n"
        "格式：\n"
        "评审结论：通过 或 需修改\n"
        "评审意见：\n（逐条列出发现的问题，没有问题则写'代码质量良好，无明显问题'）"
    )

    from openvort.core.engine.llm import LLMClient
    from openvort.config.settings import get_settings
    settings = get_settings()
    llm = LLMClient(settings.llm.get_model_chain())
    try:
        result = await llm.create(
            system="你是一名专业的代码评审员，擅长发现代码中的逻辑错误、安全隐患和性能问题。",
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        log.error(f"AI review LLM call failed: {e}")
        raise HTTPException(502, f"AI 评审调用失败: {e}")

    ai_text = ""
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                ai_text += block.text
    if not ai_text:
        ai_text = str(result)

    ai_status = "approved"
    if "需修改" in ai_text or "需要修改" in ai_text:
        ai_status = "changes_requested"
    elif "已驳回" in ai_text:
        ai_status = "rejected"

    async with sf() as session:
        review = await session.get(FlowTestPlanReview, review_id)
        if review:
            old_status = review.review_status
            review.review_status = ai_status
            review.review_notes = ai_text
            session.add(FlowTestPlanReviewHistory(
                review_id=review_id, action="status_changed",
                old_status=old_status, new_status=ai_status,
                notes=ai_text, actor_id=actor_id or None, is_ai=True,
            ))
            await session.commit()
            await session.refresh(review)
            reviewer_name = await _resolve_member_name(session, review.reviewer_id)
            from openvort.plugins.vortgit.models import GitRepo as GR
            repo_obj = await session.get(GR, review.repo_id)
            return _review_to_dict(review, reviewer_name=reviewer_name, repo_name=repo_obj.name if repo_obj else "")
    return {"error": "评审项不存在"}
