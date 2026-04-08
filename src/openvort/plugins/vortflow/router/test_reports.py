"""Test Report CRUD & data aggregation."""

import json
from datetime import datetime

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from openvort.contacts.models import Member
from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowBug,
    FlowTestCase,
    FlowTestCaseWorkItem,
    FlowTestPlan,
    FlowTestPlanCase,
    FlowTestPlanExecution,
    FlowTestPlanReview,
    FlowTestReport,
)
from openvort.web.app import require_auth

from .helpers import _resolve_member_name

sub_router = APIRouter()


# ============ Pydantic Schemas ============

class TestReportCreate(BaseModel):
    plan_id: str
    title: str = ""


class TestReportUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None


# ============ Snapshot builder ============

async def _build_report_snapshot(session, plan: FlowTestPlan) -> dict:
    """Build a comprehensive data snapshot for the test report."""
    plan_id = plan.id

    # --- Case execution stats ---
    plan_cases = (await session.execute(
        select(FlowTestPlanCase, FlowTestCase)
        .join(FlowTestCase, FlowTestPlanCase.test_case_id == FlowTestCase.id)
        .where(FlowTestPlanCase.plan_id == plan_id)
    )).all()

    total_cases = len(plan_cases)
    plan_case_ids = [pc.id for pc, _ in plan_cases]

    # Latest execution per plan_case
    latest_exec_map: dict[str, str] = {}
    all_exec_count = 0
    exec_result_counts: dict[str, int] = {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0}

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

        # All executions for process overview
        all_execs = (await session.execute(
            select(FlowTestPlanExecution)
            .where(FlowTestPlanExecution.plan_case_id.in_(plan_case_ids))
            .order_by(FlowTestPlanExecution.created_at.desc())
        )).scalars().all()
        all_exec_count = len(all_execs)
        for ex in all_execs:
            if ex.result in exec_result_counts:
                exec_result_counts[ex.result] += 1

    # Latest result distribution
    latest_passed = sum(1 for r in latest_exec_map.values() if r == "passed")
    latest_failed = sum(1 for r in latest_exec_map.values() if r == "failed")
    latest_blocked = sum(1 for r in latest_exec_map.values() if r == "blocked")
    latest_skipped = sum(1 for r in latest_exec_map.values() if r == "skipped")
    executed_cases = len(latest_exec_map)

    # Per-case execution details
    case_exec_map: dict[str, list] = {}
    if plan_case_ids:
        all_case_execs = (await session.execute(
            select(FlowTestPlanExecution)
            .where(FlowTestPlanExecution.plan_case_id.in_(plan_case_ids))
        )).scalars().all()
        for ex in all_case_execs:
            case_exec_map.setdefault(ex.plan_case_id, []).append(ex.result)

    # Batch-resolve maintainer names and bug counts to avoid N+1 queries
    maintainer_ids = {tc.maintainer_id for _, tc in plan_cases if tc.maintainer_id}
    maintainer_map: dict[str, str] = {}
    if maintainer_ids:
        m_rows = (await session.execute(
            select(Member).where(Member.id.in_(list(maintainer_ids)))
        )).scalars().all()
        maintainer_map = {m.id: m.name for m in m_rows}

    test_case_ids_for_bugs = [tc.id for _, tc in plan_cases]
    bug_count_map: dict[str, int] = {}
    if test_case_ids_for_bugs:
        bug_count_rows = (await session.execute(
            select(FlowTestCaseWorkItem.test_case_id, func.count())
            .where(FlowTestCaseWorkItem.test_case_id.in_(test_case_ids_for_bugs),
                   FlowTestCaseWorkItem.entity_type == "bug")
            .group_by(FlowTestCaseWorkItem.test_case_id)
        )).all()
        bug_count_map = {row[0]: row[1] for row in bug_count_rows}

    case_details = []
    for pc, tc in plan_cases:
        execs = case_exec_map.get(pc.id, [])
        dist = {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0}
        for r in execs:
            if r in dist:
                dist[r] += 1

        case_details.append({
            "test_case_id": tc.id,
            "title": tc.title,
            "case_type": tc.case_type,
            "priority": tc.priority,
            "maintainer_name": maintainer_map.get(tc.maintainer_id, "") if tc.maintainer_id else "",
            "latest_result": latest_exec_map.get(pc.id, ""),
            "execution_count": len(execs),
            "execution_distribution": dist,
            "bug_count": bug_count_map.get(tc.id, 0),
        })

    # Execution frequency distribution
    exec_freq: dict[int, int] = {}
    for pc, _ in plan_cases:
        count = len(case_exec_map.get(pc.id, []))
        exec_freq[count] = exec_freq.get(count, 0) + 1

    # --- Bug stats ---
    test_case_ids = [tc.id for _, tc in plan_cases]
    bug_ids: set[str] = set()
    if test_case_ids:
        bug_links = (await session.execute(
            select(FlowTestCaseWorkItem.entity_id)
            .where(FlowTestCaseWorkItem.test_case_id.in_(test_case_ids),
                   FlowTestCaseWorkItem.entity_type == "bug")
        )).scalars().all()
        bug_ids = set(bug_links)

    # Also collect bug_ids from executions
    if plan_case_ids:
        exec_bug_ids = (await session.execute(
            select(FlowTestPlanExecution.bug_id)
            .where(FlowTestPlanExecution.plan_case_id.in_(plan_case_ids),
                   FlowTestPlanExecution.bug_id.isnot(None),
                   FlowTestPlanExecution.bug_id != "")
        )).scalars().all()
        bug_ids.update(exec_bug_ids)

    bugs_data = []
    bugs: list = []
    bug_state_dist: dict[str, int] = {}
    bug_severity_dist: dict[int, int] = {}
    bug_assignee_dist: dict[str, int] = {}
    resolved_bug_count = 0

    if bug_ids:
        bugs = (await session.execute(
            select(FlowBug).where(FlowBug.id.in_(list(bug_ids)))
        )).scalars().all()

        member_ids = {b.assignee_id for b in bugs if b.assignee_id}
        member_map: dict[str, str] = {}
        if member_ids:
            members = (await session.execute(
                select(Member).where(Member.id.in_(list(member_ids)))
            )).scalars().all()
            member_map = {m.id: m.name for m in members}

        resolved_states = {"resolved", "verified", "closed"}
        for b in bugs:
            state = b.state or "open"
            bug_state_dist[state] = bug_state_dist.get(state, 0) + 1
            bug_severity_dist[b.severity] = bug_severity_dist.get(b.severity, 0) + 1
            assignee_name = member_map.get(b.assignee_id, "") if b.assignee_id else ""
            label = assignee_name or "未指派"
            bug_assignee_dist[label] = bug_assignee_dist.get(label, 0) + 1
            if state in resolved_states:
                resolved_bug_count += 1

            bugs_data.append({
                "id": b.id,
                "title": b.title,
                "state": state,
                "severity": b.severity,
                "assignee_name": assignee_name,
            })

    # --- Developer quality (grouped by assignee = developer) ---
    developer_quality_by_id: dict[str, dict] = {}
    for b in bugs:
        if not b.assignee_id:
            continue
        dev_id = b.assignee_id
        if dev_id not in developer_quality_by_id:
            developer_quality_by_id[dev_id] = {
                "developer_name": member_map.get(dev_id, dev_id),
                "bug_count": 0, "critical_count": 0,
                "severity_distribution": {"1": 0, "2": 0, "3": 0, "4": 0},
            }
        dq = developer_quality_by_id[dev_id]
        dq["bug_count"] += 1
        dq["severity_distribution"][str(b.severity)] += 1
        if b.severity <= 2:
            dq["critical_count"] += 1

    developer_quality = sorted(
        developer_quality_by_id.values(), key=lambda x: x["bug_count"], reverse=True,
    )

    # --- PR / Code review stats ---
    reviews = (await session.execute(
        select(FlowTestPlanReview)
        .where(FlowTestPlanReview.plan_id == plan_id)
        .order_by(FlowTestPlanReview.created_at.desc())
    )).scalars().all()

    review_member_ids = {r.reviewer_id for r in reviews if r.reviewer_id}
    review_added_by_ids = {r.added_by for r in reviews if r.added_by}
    all_review_member_ids = review_member_ids | review_added_by_ids
    review_member_map: dict[str, str] = {}
    if all_review_member_ids:
        members = (await session.execute(
            select(Member).where(Member.id.in_(list(all_review_member_ids)))
        )).scalars().all()
        review_member_map = {m.id: m.name for m in members}

    from openvort.plugins.vortgit.models import GitRepo
    review_repo_ids = {r.repo_id for r in reviews if r.repo_id}
    review_repo_map: dict[str, str] = {}
    if review_repo_ids:
        repos = (await session.execute(
            select(GitRepo).where(GitRepo.id.in_(list(review_repo_ids)))
        )).scalars().all()
        review_repo_map = {r.id: r.name for r in repos}

    reviews_data = []
    for r in reviews:
        reviews_data.append({
            "id": r.id,
            "pr_number": r.pr_number,
            "pr_title": r.pr_title,
            "pr_url": r.pr_url,
            "head_branch": r.head_branch,
            "base_branch": r.base_branch,
            "repo_name": review_repo_map.get(r.repo_id, ""),
            "reviewer_name": review_member_map.get(r.reviewer_id, "") if r.reviewer_id else "",
            "review_status": r.review_status,
            "added_by_name": review_member_map.get(r.added_by, "") if r.added_by else "",
        })

    review_approved = sum(1 for r in reviews if r.review_status == "approved")
    review_total = len(reviews)

    # --- Plan meta ---
    owner_name = await _resolve_member_name(session, plan.owner_id)

    from openvort.plugins.vortflow.models import FlowIteration, FlowVersion
    iteration_name = ""
    if plan.iteration_id:
        it = await session.get(FlowIteration, plan.iteration_id)
        iteration_name = it.name if it else ""
    version_name = ""
    if plan.version_id:
        v = await session.get(FlowVersion, plan.version_id)
        version_name = v.name if v else ""

    # Pass/fail verdict
    all_passed = (latest_passed == total_cases and total_cases > 0)
    no_unresolved_bugs = (resolved_bug_count == len(bugs_data)) if bugs_data else True
    verdict = "passed" if (all_passed and no_unresolved_bugs) else "failed"

    pass_rate = round((latest_passed / total_cases) * 100, 1) if total_cases else 0
    exec_rate = round((executed_cases / total_cases) * 100, 1) if total_cases else 0
    bug_resolve_rate = round((resolved_bug_count / len(bugs_data)) * 100, 1) if bugs_data else 100

    return {
        "plan": {
            "id": plan.id,
            "title": plan.title,
            "status": plan.status,
            "owner_name": owner_name,
            "start_date": plan.start_date,
            "end_date": plan.end_date,
            "iteration_name": iteration_name,
            "version_name": version_name,
        },
        "overview": {
            "verdict": verdict,
            "total_cases": total_cases,
            "executed_cases": executed_cases,
            "total_bugs": len(bugs_data),
            "pass_rate": pass_rate,
            "exec_rate": exec_rate,
            "bug_resolve_rate": bug_resolve_rate,
        },
        "case_result": {
            "passed": latest_passed,
            "failed": latest_failed,
            "blocked": latest_blocked,
            "skipped": latest_skipped,
            "unexecuted": total_cases - executed_cases,
        },
        "bug_overview": {
            "total": len(bugs_data),
            "resolved": resolved_bug_count,
            "resolve_rate": bug_resolve_rate,
            "state_distribution": bug_state_dist,
            "severity_distribution": {str(k): v for k, v in bug_severity_dist.items()},
            "assignee_distribution": bug_assignee_dist,
        },
        "bugs": bugs_data,
        "developer_quality": developer_quality,
        "reviews": reviews_data,
        "review_stats": {
            "total": review_total,
            "approved": review_approved,
        },
        "execution_process": {
            "total_cases": total_cases,
            "executed_cases": executed_cases,
            "total_executions": all_exec_count,
            "result_distribution": exec_result_counts,
            "frequency_distribution": {str(k): v for k, v in sorted(exec_freq.items())},
        },
        "case_details": case_details,
    }


# ============ CRUD ============

@sub_router.get("/test-reports")
async def list_test_reports(
    plan_id: str = Query(""),
    project_id: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowTestReport).order_by(FlowTestReport.created_at.desc())
        count_stmt = select(func.count()).select_from(FlowTestReport)
        if plan_id:
            stmt = stmt.where(FlowTestReport.plan_id == plan_id)
            count_stmt = count_stmt.where(FlowTestReport.plan_id == plan_id)
        if project_id:
            stmt = stmt.where(FlowTestReport.project_id == project_id)
            count_stmt = count_stmt.where(FlowTestReport.project_id == project_id)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()

        member_ids = {r.creator_id for r in rows if r.creator_id}
        member_map: dict[str, str] = {}
        if member_ids:
            members = (await session.execute(
                select(Member).where(Member.id.in_(list(member_ids)))
            )).scalars().all()
            member_map = {m.id: m.name for m in members}

        plan_ids = {r.plan_id for r in rows if r.plan_id}
        plan_map: dict[str, str] = {}
        if plan_ids:
            plans = (await session.execute(
                select(FlowTestPlan).where(FlowTestPlan.id.in_(list(plan_ids)))
            )).scalars().all()
            plan_map = {p.id: p.title for p in plans}

        items = [{
            "id": r.id,
            "plan_id": r.plan_id,
            "plan_title": plan_map.get(r.plan_id, ""),
            "project_id": r.project_id,
            "title": r.title,
            "creator_id": r.creator_id,
            "creator_name": member_map.get(r.creator_id, "") if r.creator_id else "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        } for r in rows]

    return {"total": total, "items": items}


@sub_router.get("/test-reports/{report_id}")
async def get_test_report(report_id: str):
    sf = get_session_factory()
    async with sf() as session:
        report = await session.get(FlowTestReport, report_id)
        if not report:
            return {"error": "测试报告不存在"}
        creator_name = await _resolve_member_name(session, report.creator_id)
        snapshot = json.loads(report.snapshot_json) if report.snapshot_json else {}
        return {
            "id": report.id,
            "plan_id": report.plan_id,
            "project_id": report.project_id,
            "title": report.title,
            "summary": report.summary,
            "snapshot": snapshot,
            "creator_id": report.creator_id,
            "creator_name": creator_name,
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        }


@sub_router.post("/test-reports")
async def create_test_report(body: TestReportCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        plan = await session.get(FlowTestPlan, body.plan_id)
        if not plan:
            return {"error": "测试计划不存在"}

        snapshot = await _build_report_snapshot(session, plan)
        title = body.title or f"{plan.title}测试报告"

        default_summary = (
            "# 测试报告总结\n\n"
            "## 1. 测试概述\n\n\n\n"
            "## 2. 测试范围\n\n\n\n"
            "## 3. 测试结果概览\n\n\n\n"
            "## 4. 主要缺陷分析\n\n\n\n"
            "## 5. 关键风险与建议\n\n"
        )

        report = FlowTestReport(
            plan_id=plan.id,
            project_id=plan.project_id,
            title=title,
            summary=default_summary,
            snapshot_json=json.dumps(snapshot, ensure_ascii=False, default=str),
            creator_id=member_id or None,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
        creator_name = await _resolve_member_name(session, report.creator_id)

    return {
        "id": report.id,
        "plan_id": report.plan_id,
        "project_id": report.project_id,
        "title": report.title,
        "summary": report.summary,
        "snapshot": snapshot,
        "creator_id": report.creator_id,
        "creator_name": creator_name,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


@sub_router.put("/test-reports/{report_id}")
async def update_test_report(report_id: str, body: TestReportUpdate):
    sf = get_session_factory()
    async with sf() as session:
        report = await session.get(FlowTestReport, report_id)
        if not report:
            return {"error": "测试报告不存在"}
        if body.title is not None:
            report.title = body.title
        if body.summary is not None:
            report.summary = body.summary
        await session.commit()
        await session.refresh(report)
        creator_name = await _resolve_member_name(session, report.creator_id)
        snapshot = json.loads(report.snapshot_json) if report.snapshot_json else {}
    return {
        "id": report.id,
        "plan_id": report.plan_id,
        "project_id": report.project_id,
        "title": report.title,
        "summary": report.summary,
        "snapshot": snapshot,
        "creator_id": report.creator_id,
        "creator_name": creator_name,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


@sub_router.delete("/test-reports/{report_id}")
async def delete_test_report(report_id: str):
    sf = get_session_factory()
    async with sf() as session:
        report = await session.get(FlowTestReport, report_id)
        if not report:
            return {"error": "测试报告不存在"}
        await session.delete(report)
        await session.commit()
    return {"ok": True}
