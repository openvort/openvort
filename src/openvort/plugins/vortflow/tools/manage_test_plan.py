"""
测试计划管理工具 -- vortflow_manage_test_plan

创建、修改、删除、复制测试计划，关联/移除用例，记录执行结果，
代码评审管理，查询计划列表和详情。
"""

import json

from sqlalchemy import delete as sa_delete, func, select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.manage_test_plan")


class ManageTestPlanTool(BaseTool):
    name = "vortflow_manage_test_plan"
    description = (
        "管理 VortFlow 测试计划。"
        "action=create 创建测试计划，需提供 project_id 和 title。"
        "action=update 修改测试计划信息。"
        "action=delete 删除测试计划（级联删除关联用例和执行记录，需用户确认「确认删除」）。"
        "action=copy 复制测试计划（含关联用例），需提供 plan_id。"
        "action=add_cases 为计划添加测试用例，需提供 plan_id 和 test_case_ids 列表。"
        "action=remove_case 从计划移除一条用例，需提供 plan_id 和 plan_case_id。"
        "action=execute 记录用例执行结果，需提供 plan_id、plan_case_id 和 result (passed/failed/blocked/skipped)。"
        "action=add_review 为计划添加代码评审（PR），需提供 plan_id 和 review 信息。"
        "action=update_review 更新评审状态/评审人，需提供 plan_id 和 review_id。"
        "action=remove_review 移除评审项。"
        "action=list_reviews 列出计划的代码评审项。"
        "action=list 查询测试计划列表，可按 project_id/status/keyword 过滤。"
        "action=detail 查询单个测试计划详情（含统计信息）。"
    )
    required_permission = "vortflow.story"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "create", "update", "delete", "copy",
                        "add_cases", "remove_case", "execute",
                        "add_review", "update_review", "remove_review", "list_reviews",
                        "list", "detail",
                    ],
                    "description": "操作类型",
                },
                "plan_id": {"type": "string", "description": "测试计划 ID（除 create/list 外必填）"},
                "project_id": {"type": "string", "description": "项目 ID（create/list 时使用）"},
                "title": {"type": "string", "description": "计划标题"},
                "description": {"type": "string", "description": "计划描述", "default": ""},
                "status": {
                    "type": "string",
                    "enum": ["planning", "in_progress", "completed", "suspended"],
                    "description": "计划状态",
                },
                "owner_name": {"type": "string", "description": "负责人姓名（用于匹配成员）", "default": ""},
                "iteration_id": {"type": "string", "description": "关联迭代 ID"},
                "version_id": {"type": "string", "description": "关联版本 ID"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "test_case_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "测试用例 ID 列表（add_cases 时使用）",
                },
                "plan_case_id": {"type": "string", "description": "计划用例 ID（remove_case/execute 时使用）"},
                "result": {
                    "type": "string",
                    "enum": ["passed", "failed", "blocked", "skipped"],
                    "description": "执行结果（execute 时使用）",
                },
                "notes": {"type": "string", "description": "执行备注", "default": ""},
                "bug_id": {"type": "string", "description": "关联缺陷 ID（execute 时可选）"},
                "keyword": {"type": "string", "description": "搜索关键词（list 时可选）", "default": ""},
                "confirm_text": {"type": "string", "description": "删除确认文本"},
                "review_id": {"type": "string", "description": "评审项 ID（update_review/remove_review 时使用）"},
                "repo_id": {"type": "string", "description": "Git 仓库 ID（add_review 时使用）"},
                "pr_number": {"type": "integer", "description": "PR 编号（add_review 时使用）"},
                "pr_url": {"type": "string", "description": "PR 链接"},
                "pr_title": {"type": "string", "description": "PR 标题"},
                "head_branch": {"type": "string", "description": "源分支"},
                "base_branch": {"type": "string", "description": "目标分支"},
                "reviewer_name": {"type": "string", "description": "评审人姓名"},
                "review_status": {
                    "type": "string",
                    "enum": ["pending", "approved", "rejected", "changes_requested"],
                    "description": "评审状态",
                },
                "review_notes": {"type": "string", "description": "评审意见"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.contacts.models import Member
        from openvort.plugins.vortflow.models import (
            FlowIteration,
            FlowTestPlan,
            FlowTestPlanCase,
            FlowTestPlanExecution,
            FlowTestPlanReview,
            FlowTestPlanReviewHistory,
            FlowVersion,
        )

        action = params["action"]
        member_id = params.get("_member_id", "")
        sf = self._get_sf()

        if action == "create":
            return await self._create(params, sf, member_id, Member, FlowTestPlan)
        elif action == "update":
            return await self._update(params, sf, member_id, Member, FlowTestPlan)
        elif action == "delete":
            return await self._delete(params, sf, FlowTestPlan, FlowTestPlanCase,
                                      FlowTestPlanExecution, FlowTestPlanReview)
        elif action == "copy":
            return await self._copy(params, sf, member_id, FlowTestPlan, FlowTestPlanCase)
        elif action == "add_cases":
            return await self._add_cases(params, sf, member_id, FlowTestPlan, FlowTestPlanCase)
        elif action == "remove_case":
            return await self._remove_case(params, sf, FlowTestPlanCase, FlowTestPlanExecution)
        elif action == "execute":
            return await self._execute_case(params, sf, member_id, FlowTestPlanCase, FlowTestPlanExecution)
        elif action == "add_review":
            return await self._add_review(params, sf, member_id, FlowTestPlan, FlowTestPlanReview)
        elif action == "update_review":
            return await self._update_review(params, sf, member_id, Member,
                                             FlowTestPlanReview, FlowTestPlanReviewHistory)
        elif action == "remove_review":
            return await self._remove_review(params, sf, FlowTestPlanReview)
        elif action == "list_reviews":
            return await self._list_reviews(params, sf, Member, FlowTestPlanReview)
        elif action == "list":
            return await self._list(params, sf, Member, FlowTestPlan, FlowTestPlanCase,
                                    FlowTestPlanExecution, FlowIteration, FlowVersion)
        elif action == "detail":
            return await self._detail(params, sf, Member, FlowTestPlan, FlowTestPlanCase,
                                      FlowTestPlanExecution, FlowIteration, FlowVersion)
        return json.dumps({"ok": False, "message": f"未知操作: {action}"})

    # ---- create ----

    async def _create(self, params, sf, member_id, Member, FlowTestPlan):
        project_id = params.get("project_id", "")
        title = params.get("title", "")
        if not project_id or not title:
            return json.dumps({"ok": False, "message": "创建测试计划需要提供 project_id 和 title"})
        owner_id = None
        owner_name = params.get("owner_name", "")
        async with sf() as session:
            if owner_name:
                m = (await session.execute(select(Member).where(Member.name == owner_name))).scalar_one_or_none()
                if m:
                    owner_id = m.id
            plan = FlowTestPlan(
                project_id=project_id, title=title, description=params.get("description", ""),
                status=params.get("status", "in_progress"), owner_id=owner_id or (member_id or None),
                iteration_id=params.get("iteration_id") or None, version_id=params.get("version_id") or None,
                start_date=params.get("start_date") or None, end_date=params.get("end_date") or None,
            )
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            plan_id = plan.id
        return json.dumps({"ok": True, "message": f"测试计划「{title}」已创建",
                           "plan_id": plan_id, "project_id": project_id}, ensure_ascii=False)

    # ---- update ----

    async def _update(self, params, sf, member_id, Member, FlowTestPlan):
        plan_id = params.get("plan_id", "")
        if not plan_id:
            return json.dumps({"ok": False, "message": "update 需要提供 plan_id"})
        async with sf() as session:
            plan = await session.get(FlowTestPlan, plan_id)
            if not plan:
                return json.dumps({"ok": False, "message": "测试计划不存在"})
            changes = {}
            for field in ("title", "description", "status", "start_date", "end_date"):
                if field in params and params[field] is not None:
                    setattr(plan, field, params[field])
                    changes[field] = params[field]
            for fk in ("iteration_id", "version_id"):
                if fk in params and params[fk] is not None:
                    setattr(plan, fk, params[fk] or None)
                    changes[fk] = params[fk]
            if params.get("owner_name"):
                m = (await session.execute(select(Member).where(Member.name == params["owner_name"]))).scalar_one_or_none()
                if m:
                    plan.owner_id = m.id
                    changes["owner"] = params["owner_name"]
            if not changes:
                return json.dumps({"ok": False, "message": "未提供任何要修改的字段"})
            await session.commit()
        return json.dumps({"ok": True, "message": f"测试计划「{plan.title}」已更新，修改字段: {'、'.join(changes.keys())}"}, ensure_ascii=False)

    # ---- delete ----

    async def _delete(self, params, sf, FlowTestPlan, FlowTestPlanCase, FlowTestPlanExecution, FlowTestPlanReview):
        plan_id = params.get("plan_id", "")
        confirm = params.get("confirm_text", "")
        if not plan_id:
            return json.dumps({"ok": False, "message": "delete 需要提供 plan_id"})
        if confirm != "确认删除":
            return json.dumps({"ok": False, "message": "删除测试计划需要用户确认。请让用户回复「确认删除」后再调用。"}, ensure_ascii=False)
        async with sf() as session:
            plan = await session.get(FlowTestPlan, plan_id)
            if not plan:
                return json.dumps({"ok": False, "message": "测试计划不存在"})
            title = plan.title
            case_ids = [r[0] for r in (await session.execute(
                select(FlowTestPlanCase.id).where(FlowTestPlanCase.plan_id == plan_id))).all()]
            if case_ids:
                await session.execute(sa_delete(FlowTestPlanExecution).where(FlowTestPlanExecution.plan_case_id.in_(case_ids)))
            await session.execute(sa_delete(FlowTestPlanCase).where(FlowTestPlanCase.plan_id == plan_id))
            await session.execute(sa_delete(FlowTestPlanReview).where(FlowTestPlanReview.plan_id == plan_id))
            await session.delete(plan)
            await session.commit()
        return json.dumps({"ok": True, "message": f"测试计划「{title}」已删除"}, ensure_ascii=False)

    # ---- copy ----

    async def _copy(self, params, sf, member_id, FlowTestPlan, FlowTestPlanCase):
        plan_id = params.get("plan_id", "")
        if not plan_id:
            return json.dumps({"ok": False, "message": "copy 需要提供 plan_id"})
        async with sf() as session:
            src = await session.get(FlowTestPlan, plan_id)
            if not src:
                return json.dumps({"ok": False, "message": "测试计划不存在"})
            new_plan = FlowTestPlan(
                project_id=src.project_id, title=params.get("title") or f"{src.title} (副本)",
                description=src.description, status="in_progress", owner_id=src.owner_id,
                iteration_id=src.iteration_id, version_id=src.version_id,
                start_date=src.start_date, end_date=src.end_date,
            )
            session.add(new_plan)
            await session.flush()
            case_rows = (await session.execute(
                select(FlowTestPlanCase).where(FlowTestPlanCase.plan_id == plan_id)
                .order_by(FlowTestPlanCase.sort_order))).scalars().all()
            for pc in case_rows:
                session.add(FlowTestPlanCase(plan_id=new_plan.id, test_case_id=pc.test_case_id,
                                             sort_order=pc.sort_order, created_by=member_id or None))
            await session.commit()
            await session.refresh(new_plan)
        return json.dumps({"ok": True, "message": f"测试计划已复制为「{new_plan.title}」，包含 {len(case_rows)} 条用例",
                           "plan_id": new_plan.id}, ensure_ascii=False)

    # ---- add_cases ----

    async def _add_cases(self, params, sf, member_id, FlowTestPlan, FlowTestPlanCase):
        plan_id = params.get("plan_id", "")
        test_case_ids = params.get("test_case_ids", [])
        if not plan_id or not test_case_ids:
            return json.dumps({"ok": False, "message": "add_cases 需要提供 plan_id 和 test_case_ids"})
        async with sf() as session:
            plan = await session.get(FlowTestPlan, plan_id)
            if not plan:
                return json.dumps({"ok": False, "message": "测试计划不存在"})
            existing_set = set((await session.execute(
                select(FlowTestPlanCase.test_case_id).where(FlowTestPlanCase.plan_id == plan_id))).scalars().all())
            max_order = (await session.execute(
                select(func.coalesce(func.max(FlowTestPlanCase.sort_order), 0))
                .where(FlowTestPlanCase.plan_id == plan_id))).scalar_one()
            added = 0
            for tc_id in test_case_ids:
                if tc_id in existing_set:
                    continue
                max_order += 1
                session.add(FlowTestPlanCase(plan_id=plan_id, test_case_id=tc_id,
                                             sort_order=max_order, created_by=member_id or None))
                added += 1
            await session.commit()
        skipped = len(test_case_ids) - added
        msg = f"已添加 {added} 条用例到计划「{plan.title}」"
        if skipped > 0:
            msg += f"，{skipped} 条已存在被跳过"
        return json.dumps({"ok": True, "message": msg, "added": added, "skipped": skipped}, ensure_ascii=False)

    # ---- remove_case ----

    async def _remove_case(self, params, sf, FlowTestPlanCase, FlowTestPlanExecution):
        plan_id = params.get("plan_id", "")
        plan_case_id = params.get("plan_case_id", "")
        if not plan_id or not plan_case_id:
            return json.dumps({"ok": False, "message": "remove_case 需要提供 plan_id 和 plan_case_id"})
        async with sf() as session:
            await session.execute(sa_delete(FlowTestPlanExecution).where(FlowTestPlanExecution.plan_case_id == plan_case_id))
            result = await session.execute(
                sa_delete(FlowTestPlanCase).where(FlowTestPlanCase.id == plan_case_id, FlowTestPlanCase.plan_id == plan_id))
            await session.commit()
            if result.rowcount == 0:
                return json.dumps({"ok": False, "message": "计划用例不存在"})
        return json.dumps({"ok": True, "message": "用例已从计划中移除"}, ensure_ascii=False)

    # ---- execute ----

    async def _execute_case(self, params, sf, member_id, FlowTestPlanCase, FlowTestPlanExecution):
        plan_id = params.get("plan_id", "")
        plan_case_id = params.get("plan_case_id", "")
        result_val = params.get("result", "")
        if not plan_id or not plan_case_id or not result_val:
            return json.dumps({"ok": False, "message": "execute 需要提供 plan_id、plan_case_id 和 result"})
        async with sf() as session:
            pc = await session.get(FlowTestPlanCase, plan_case_id)
            if not pc or pc.plan_id != plan_id:
                return json.dumps({"ok": False, "message": "计划用例不存在"})
            ex = FlowTestPlanExecution(
                plan_case_id=plan_case_id, result=result_val, executor_id=member_id or None,
                notes=params.get("notes", ""), bug_id=params.get("bug_id") or None,
            )
            session.add(ex)
            await session.commit()
            await session.refresh(ex)
        return json.dumps({"ok": True, "message": f"执行结果已记录: {result_val}", "execution_id": ex.id}, ensure_ascii=False)

    # ---- add_review ----

    async def _add_review(self, params, sf, member_id, FlowTestPlan, FlowTestPlanReview):
        plan_id = params.get("plan_id", "")
        repo_id = params.get("repo_id", "")
        pr_number = params.get("pr_number")
        if not plan_id or not repo_id or not pr_number:
            return json.dumps({"ok": False, "message": "add_review 需要 plan_id、repo_id、pr_number"})
        async with sf() as session:
            plan = await session.get(FlowTestPlan, plan_id)
            if not plan:
                return json.dumps({"ok": False, "message": "测试计划不存在"})
            existing = (await session.execute(select(FlowTestPlanReview).where(
                FlowTestPlanReview.plan_id == plan_id, FlowTestPlanReview.repo_id == repo_id,
                FlowTestPlanReview.pr_number == pr_number))).scalar_one_or_none()
            if existing:
                return json.dumps({"ok": False, "message": "该 PR 已添加到此计划"})
            review = FlowTestPlanReview(
                plan_id=plan_id, repo_id=repo_id, pr_number=pr_number,
                pr_url=params.get("pr_url", ""), pr_title=params.get("pr_title", ""),
                head_branch=params.get("head_branch", ""), base_branch=params.get("base_branch", ""),
                added_by=member_id or None,
            )
            session.add(review)
            await session.commit()
            await session.refresh(review)
        return json.dumps({"ok": True, "message": f"PR #{pr_number} 已添加到评审列表",
                           "review_id": review.id}, ensure_ascii=False)

    # ---- update_review ----

    async def _update_review(self, params, sf, member_id, Member, FlowTestPlanReview, FlowTestPlanReviewHistory):
        plan_id = params.get("plan_id", "")
        review_id = params.get("review_id", "")
        if not plan_id or not review_id:
            return json.dumps({"ok": False, "message": "update_review 需要 plan_id 和 review_id"})
        async with sf() as session:
            review = await session.get(FlowTestPlanReview, review_id)
            if not review or review.plan_id != plan_id:
                return json.dumps({"ok": False, "message": "评审项不存在"})
            old_status = review.review_status
            changes = {}
            if params.get("reviewer_name"):
                m = (await session.execute(select(Member).where(Member.name == params["reviewer_name"]))).scalar_one_or_none()
                if m:
                    old_reviewer = review.reviewer_id
                    review.reviewer_id = m.id
                    changes["reviewer"] = params["reviewer_name"]
                    if old_reviewer != m.id:
                        session.add(FlowTestPlanReviewHistory(
                            review_id=review_id, action="reviewer_assigned",
                            notes="评审人变更", actor_id=member_id or None))
            if params.get("review_status"):
                review.review_status = params["review_status"]
                changes["review_status"] = params["review_status"]
            if params.get("review_notes") is not None:
                review.review_notes = params["review_notes"]
                changes["review_notes"] = f"{len(params['review_notes'])} chars"
            if params.get("review_status") and params["review_status"] != old_status:
                session.add(FlowTestPlanReviewHistory(
                    review_id=review_id, action="status_changed", old_status=old_status,
                    new_status=params["review_status"], notes=params.get("review_notes", ""),
                    actor_id=member_id or None))
            if not changes:
                return json.dumps({"ok": False, "message": "未提供任何修改字段"})
            await session.commit()
        return json.dumps({"ok": True, "message": f"评审项已更新，修改字段: {'、'.join(changes.keys())}"}, ensure_ascii=False)

    # ---- remove_review ----

    async def _remove_review(self, params, sf, FlowTestPlanReview):
        plan_id = params.get("plan_id", "")
        review_id = params.get("review_id", "")
        if not plan_id or not review_id:
            return json.dumps({"ok": False, "message": "remove_review 需要 plan_id 和 review_id"})
        async with sf() as session:
            review = await session.get(FlowTestPlanReview, review_id)
            if not review or review.plan_id != plan_id:
                return json.dumps({"ok": False, "message": "评审项不存在"})
            await session.delete(review)
            await session.commit()
        return json.dumps({"ok": True, "message": "评审项已移除"}, ensure_ascii=False)

    # ---- list_reviews ----

    async def _list_reviews(self, params, sf, Member, FlowTestPlanReview):
        plan_id = params.get("plan_id", "")
        if not plan_id:
            return json.dumps({"ok": False, "message": "list_reviews 需要 plan_id"})
        async with sf() as session:
            rows = (await session.execute(
                select(FlowTestPlanReview).where(FlowTestPlanReview.plan_id == plan_id)
                .order_by(FlowTestPlanReview.created_at.desc()))).scalars().all()
            member_ids = {r.reviewer_id for r in rows if r.reviewer_id}
            member_map: dict[str, str] = {}
            if member_ids:
                members = (await session.execute(select(Member).where(Member.id.in_(list(member_ids))))).scalars().all()
                member_map = {m.id: m.name for m in members}
            items = [{
                "review_id": r.id, "repo_id": r.repo_id, "pr_number": r.pr_number,
                "pr_title": r.pr_title, "pr_url": r.pr_url, "head_branch": r.head_branch,
                "base_branch": r.base_branch,
                "reviewer_name": member_map.get(r.reviewer_id, "") if r.reviewer_id else "",
                "review_status": r.review_status,
                "review_notes": r.review_notes[:200] if r.review_notes else "",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            } for r in rows]
        return json.dumps({"ok": True, "count": len(items), "reviews": items}, ensure_ascii=False)

    # ---- list ----

    async def _list(self, params, sf, Member, FlowTestPlan, FlowTestPlanCase,
                    FlowTestPlanExecution, FlowIteration, FlowVersion):
        async with sf() as session:
            stmt = select(FlowTestPlan).order_by(FlowTestPlan.created_at.desc()).limit(50)
            if params.get("project_id"):
                stmt = stmt.where(FlowTestPlan.project_id == params["project_id"])
            if params.get("status"):
                stmt = stmt.where(FlowTestPlan.status == params["status"])
            if params.get("keyword"):
                like = f"%{params['keyword']}%"
                stmt = stmt.where(FlowTestPlan.title.ilike(like) | FlowTestPlan.description.ilike(like))
            rows = (await session.execute(stmt)).scalars().all()
            items = []
            for plan in rows:
                owner_name = ""
                if plan.owner_id:
                    m = await session.get(Member, plan.owner_id)
                    owner_name = m.name if m else ""
                total_cases = (await session.execute(
                    select(func.count()).select_from(FlowTestPlanCase)
                    .where(FlowTestPlanCase.plan_id == plan.id))).scalar_one()
                items.append({
                    "id": plan.id, "title": plan.title, "status": plan.status,
                    "owner_name": owner_name, "total_cases": total_cases,
                    "iteration_id": plan.iteration_id, "version_id": plan.version_id,
                    "start_date": plan.start_date, "end_date": plan.end_date,
                    "created_at": plan.created_at.isoformat() if plan.created_at else None,
                })
        return json.dumps({"ok": True, "count": len(items), "test_plans": items}, ensure_ascii=False)

    # ---- detail ----

    async def _detail(self, params, sf, Member, FlowTestPlan, FlowTestPlanCase,
                      FlowTestPlanExecution, FlowIteration, FlowVersion):
        plan_id = params.get("plan_id", "")
        if not plan_id:
            return json.dumps({"ok": False, "message": "detail 需要提供 plan_id"})
        async with sf() as session:
            plan = await session.get(FlowTestPlan, plan_id)
            if not plan:
                return json.dumps({"ok": False, "message": "测试计划不存在"})
            owner_name = ""
            if plan.owner_id:
                m = await session.get(Member, plan.owner_id)
                owner_name = m.name if m else ""
            iteration_name = ""
            if plan.iteration_id:
                it = await session.get(FlowIteration, plan.iteration_id)
                iteration_name = it.name if it else ""
            version_name = ""
            if plan.version_id:
                v = await session.get(FlowVersion, plan.version_id)
                version_name = v.name if v else ""
            total_cases = (await session.execute(
                select(func.count()).select_from(FlowTestPlanCase)
                .where(FlowTestPlanCase.plan_id == plan_id))).scalar_one()
            latest_sq = (
                select(FlowTestPlanExecution.plan_case_id,
                       func.max(FlowTestPlanExecution.created_at).label("max_ts"))
                .join(FlowTestPlanCase, FlowTestPlanExecution.plan_case_id == FlowTestPlanCase.id)
                .where(FlowTestPlanCase.plan_id == plan_id)
                .group_by(FlowTestPlanExecution.plan_case_id).subquery())
            latest_results = (await session.execute(
                select(FlowTestPlanExecution.result, func.count())
                .join(latest_sq, (FlowTestPlanExecution.plan_case_id == latest_sq.c.plan_case_id)
                      & (FlowTestPlanExecution.created_at == latest_sq.c.max_ts))
                .group_by(FlowTestPlanExecution.result))).all()
            passed = failed = blocked = skipped = 0
            for r, cnt in latest_results:
                if r == "passed": passed = cnt
                elif r == "failed": failed = cnt
                elif r == "blocked": blocked = cnt
                elif r == "skipped": skipped = cnt
        return json.dumps({"ok": True, "test_plan": {
            "id": plan.id, "project_id": plan.project_id, "title": plan.title,
            "description": plan.description, "status": plan.status, "owner_name": owner_name,
            "iteration_name": iteration_name, "version_name": version_name,
            "start_date": plan.start_date, "end_date": plan.end_date,
            "total_cases": total_cases, "executed": passed + failed + blocked + skipped,
            "passed": passed, "failed": failed, "blocked": blocked, "skipped": skipped,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
        }}, ensure_ascii=False)
