"""
汇报插件 API 路由

挂载到 /api/reports，登录用户可访问。
"""

from datetime import date

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _get_service():
    from openvort.db.engine import get_session_factory
    from openvort.plugins.report.service import ReportService
    return ReportService(get_session_factory())


# ---- Templates ----

class TemplateRequest(BaseModel):
    name: str
    report_type: str = "daily"
    content_schema: dict | None = None
    auto_collect: dict | None = None


@router.get("/templates")
async def list_templates():
    service = _get_service()
    templates = await service.list_templates()
    return {"templates": templates}


@router.post("/templates")
async def create_template(req: TemplateRequest):
    service = _get_service()
    result = await service.create_template(
        name=req.name,
        report_type=req.report_type,
        content_schema=req.content_schema,
        auto_collect=req.auto_collect,
    )
    return {"success": True, "template": result}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    service = _get_service()
    ok = await service.delete_template(template_id)
    return {"success": ok}


# ---- Rules ----

class RuleRequest(BaseModel):
    template_id: str
    scope: str = "member"
    target_id: str = ""
    reviewer_id: str | None = None
    deadline_cron: str = "0 18 * * 1-5"
    reminder_minutes: int = 30
    escalation_minutes: int = 120
    enabled: bool = True


@router.get("/rules")
async def list_rules(template_id: str | None = None):
    service = _get_service()
    rules = await service.list_rules(template_id=template_id)
    return {"rules": rules}


@router.post("/rules")
async def create_rule(req: RuleRequest):
    service = _get_service()
    result = await service.create_rule(
        template_id=req.template_id,
        scope=req.scope,
        target_id=req.target_id,
        reviewer_id=req.reviewer_id,
        deadline_cron=req.deadline_cron,
        reminder_minutes=req.reminder_minutes,
        escalation_minutes=req.escalation_minutes,
        enabled=req.enabled,
    )
    return {"success": True, "rule": result}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    service = _get_service()
    ok = await service.delete_rule(rule_id)
    return {"success": ok}


# ---- Reports ----

class ReportSubmitRequest(BaseModel):
    report_type: str = "daily"
    report_date: str | None = None
    title: str = ""
    content: str = ""
    template_id: str | None = None
    reviewer_id: str | None = None


class ReviewRequest(BaseModel):
    status: str  # reviewed / rejected
    comment: str = ""


@router.get("")
async def list_reports(
    request: Request,
    report_type: str | None = None,
    status: str | None = None,
    since: str | None = None,
    until: str | None = None,
    reporter_id: str | None = None,
    reviewer_id: str | None = None,
    scope: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    service = _get_service()

    payload = getattr(request.state, "user", None) or {}
    member_id = payload.get("member_id", "")

    if scope == "subordinate":
        # Look up subordinate IDs from reporting relations
        subordinate_ids = await service.get_subordinate_ids(member_id)
        reports = await service.list_reports(
            reporter_ids=subordinate_ids or [],
            report_type=report_type,
            status=status,
            since=date.fromisoformat(since) if since else None,
            until=date.fromisoformat(until) if until else None,
            limit=page_size,
        )
    else:
        rid = reporter_id or member_id
        reports = await service.list_reports(
            reporter_id=rid if not reviewer_id else None,
            reviewer_id=reviewer_id,
            report_type=report_type,
            status=status,
            since=date.fromisoformat(since) if since else None,
            until=date.fromisoformat(until) if until else None,
            limit=page_size,
        )
    return {"items": reports, "total": len(reports)}


@router.get("/stats")
async def report_stats(
    reviewer_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
):
    service = _get_service()
    stats = await service.get_report_stats(
        reviewer_id=reviewer_id,
        since=date.fromisoformat(since) if since else None,
        until=date.fromisoformat(until) if until else None,
    )
    return stats


@router.post("")
async def submit_report(req: ReportSubmitRequest, request: Request):
    service = _get_service()
    payload = getattr(request.state, "user", None) or {}
    member_id = payload.get("member_id", "unknown")

    # Auto-resolve reviewer from reporting relations if not specified
    reviewer_id = req.reviewer_id
    if not reviewer_id:
        reviewer_id = await service.get_reviewer_for_member(member_id)

    report_date = date.fromisoformat(req.report_date) if req.report_date else date.today()
    report = await service.create_report(
        reporter_id=member_id,
        report_type=req.report_type,
        report_date=report_date,
        title=req.title,
        content=req.content,
        status="submitted",
        template_id=req.template_id,
        reviewer_id=reviewer_id,
    )
    return {"success": True, "report": report}


@router.get("/{report_id}")
async def get_report(report_id: str):
    service = _get_service()
    report = await service.get_report(report_id)
    if not report:
        return {"success": False, "error": "汇报不存在"}
    return report


@router.put("/{report_id}")
async def update_report(report_id: str, req: ReportSubmitRequest):
    service = _get_service()
    fields = {}
    if req.title:
        fields["title"] = req.title
    if req.content:
        fields["content"] = req.content
    if req.reviewer_id:
        fields["reviewer_id"] = req.reviewer_id
    result = await service.update_report(report_id, **fields)
    if not result:
        return {"success": False, "error": "汇报不存在"}
    return {"success": True, "report": result}


@router.put("/{report_id}/review")
async def review_report(report_id: str, req: ReviewRequest):
    service = _get_service()
    result = await service.update_report(
        report_id,
        status=req.status,
        reviewer_comment=req.comment,
    )
    if not result:
        return {"success": False, "error": "汇报不存在"}
    return {"success": True, "report": result}


# ============ AI 生成 ============

@router.get("/generate-content-prompt")
async def generate_report_content_prompt(
    report_type: str = Query(..., description="汇报类型: daily/weekly/monthly"),
    report_date: str = Query("", description="汇报日期"),
):
    """生成 AI 创建汇报内容的 prompt"""
    date_text = report_date or "今天"
    
    if report_type == "daily":
        prompt = (
            f"请为 {date_text} 生成一份详细的日报内容。\n\n"
            f"请按照以下结构生成（Markdown 格式）：\n"
            f"1. 今日工作 - 列出完成的主要工作内容\n"
            f"2. 工作成果 - 描述取得的成果和产出\n"
            f"3. 遇到问题 - 描述遇到的问题和挑战\n"
            f"4. 明日计划 - 计划次日的工作内容\n\n"
            f"要求：内容要真实、具体，突出工作价值和成果。"
        )
    elif report_type == "weekly":
        prompt = (
            f"请为 {date_text} 生成一份详细的周报内容。\n\n"
            f"请按照以下结构生成（Markdown 格式）：\n"
            f"1. 本周工作概述 - 本周的主要工作内容\n"
            f"2. 成果与亮点 - 本周取得的主要成果\n"
            f"3. 问题与反思 - 遇到的问题和改进建议\n"
            f"4. 下周计划 - 计划下周的工作内容\n\n"
            f"要求：内容要全面、简洁，突出工作成效。"
        )
    elif report_type == "monthly":
        prompt = (
            f"请为 {date_text} 生成一份详细的月报内容。\n\n"
            f"请按照以下结构生成（Markdown 格式）：\n"
            f"1. 本月工作概述 - 本月的主要工作内容\n"
            f"2. 成果与数据 - 本月取得的主要成果和相关数据\n"
            f"3. 项目进展 - 参与项目的进展状态\n"
            f"4. 问题与改进 - 遇到的问题和解决方案\n"
            f"5. 下月计划 - 计划下月的工作重点\n\n"
            f"要求：内容要系统、全面，突出业绩和成长。"
        )
    else:
        prompt = f"请为 {date_text} 生成一份{report_type}汇报内容。"

    return {"prompt": prompt}
