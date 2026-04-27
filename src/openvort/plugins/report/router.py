"""
汇报插件 API 路由 (v2)

挂载到 /api/reports，登录用户可访问。
"""

from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from openvort.web.app import require_auth

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _get_service():
    from openvort.db.engine import get_session_factory
    from openvort.plugins.report.service import ReportService
    return ReportService(get_session_factory())


def _member_id(request: Request) -> str:
    """Extract member_id from JWT payload via Authorization header."""
    from openvort.web.auth import verify_token
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    payload = verify_token(token) if token else None
    return (payload or {}).get("sub", "")


# ============ Publications ============

class PublicationRequest(BaseModel):
    name: str
    description: str = ""
    report_type: str = "daily"
    content_schema: dict | None = None
    content_template: str = ""
    repeat_cycle: str = "daily"
    deadline_time: str = "次日 10:00"
    reminder_enabled: bool = True
    reminder_time: str = "10:00"
    skip_weekends: bool = True
    skip_holidays: bool = True
    allow_multiple: bool = True
    allow_edit: bool = True
    notify_summary: bool = True
    notify_on_receive: bool = True
    submitter_ids: list[str] = []
    whitelist_ids: list[str] = []
    receiver_ids: list[str] = []
    receiver_filters: dict[str, list[str]] | None = None


class PublicationUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    report_type: str | None = None
    content_schema: dict | None = None
    content_template: str | None = None
    repeat_cycle: str | None = None
    deadline_time: str | None = None
    reminder_enabled: bool | None = None
    reminder_time: str | None = None
    skip_weekends: bool | None = None
    skip_holidays: bool | None = None
    allow_multiple: bool | None = None
    allow_edit: bool | None = None
    notify_summary: bool | None = None
    notify_on_receive: bool | None = None
    enabled: bool | None = None
    submitter_ids: list[str] | None = None
    whitelist_ids: list[str] | None = None
    receiver_ids: list[str] | None = None
    receiver_filters: dict[str, list[str]] | None = None


@router.get("/publications")
async def list_publications():
    service = _get_service()
    pubs = await service.list_publications()
    return {"publications": pubs}


@router.post("/publications")
async def create_publication(req: PublicationRequest, request: Request):
    service = _get_service()
    owner_id = _member_id(request) or None
    result = await service.create_publication(
        name=req.name, description=req.description, report_type=req.report_type,
        content_schema=req.content_schema, content_template=req.content_template,
        repeat_cycle=req.repeat_cycle,
        deadline_time=req.deadline_time, reminder_enabled=req.reminder_enabled,
        reminder_time=req.reminder_time, skip_weekends=req.skip_weekends,
        skip_holidays=req.skip_holidays, allow_multiple=req.allow_multiple,
        allow_edit=req.allow_edit, notify_summary=req.notify_summary,
        notify_on_receive=req.notify_on_receive, owner_id=owner_id,
        submitter_ids=req.submitter_ids, whitelist_ids=req.whitelist_ids,
        receiver_ids=req.receiver_ids, receiver_filters=req.receiver_filters,
    )
    return {"success": True, "publication": result}


@router.get("/publications/{pub_id}")
async def get_publication(pub_id: str):
    service = _get_service()
    result = await service.get_publication(pub_id)
    if not result:
        return {"success": False, "error": "发布不存在"}
    return result


@router.put("/publications/{pub_id}")
async def update_publication(pub_id: str, req: PublicationUpdateRequest):
    service = _get_service()
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    result = await service.update_publication(pub_id, **fields)
    if not result:
        return {"success": False, "error": "发布不存在"}
    return {"success": True, "publication": result}


@router.delete("/publications/{pub_id}")
async def delete_publication(pub_id: str):
    service = _get_service()
    ok = await service.delete_publication(pub_id)
    return {"success": ok}


class ReminderRequest(BaseModel):
    report_date: str | None = None


@router.post("/publications/{pub_id}/remind")
async def send_reminders(pub_id: str, request: Request, req: ReminderRequest | None = None):
    service = _get_service()
    member_id = _member_id(request)
    report_date = date.fromisoformat(req.report_date) if req and req.report_date else None
    result = await service.send_fill_reminders(pub_id, report_date=report_date, receiver_id=member_id or None)
    return result


@router.post("/publications/{pub_id}/summary")
async def send_summary(pub_id: str):
    service = _get_service()
    result = await service.send_deadline_summary(pub_id)
    return result


# ============ Reports ============

class ReportSubmitRequest(BaseModel):
    report_type: str = "daily"
    report_date: str | None = None
    title: str = ""
    content: str = ""
    publication_id: str | None = None


@router.get("/my-publications")
async def my_publications(request: Request):
    """Get publications where the current user is a submitter."""
    service = _get_service()
    member_id = _member_id(request)
    pubs = await service.get_publications_for_submitter(member_id)
    return {"publications": pubs}


@router.get("")
async def list_reports(
    request: Request,
    report_type: str | None = None,
    status: str | None = None,
    since: str | None = None,
    until: str | None = None,
    publication_id: str | None = None,
    scope: str | None = None,
    reporter_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    service = _get_service()
    member_id = _member_id(request)

    since_date = date.fromisoformat(since) if since else None
    until_date = date.fromisoformat(until) if until else None

    if scope == "received":
        reports = await service.list_received_reports(
            member_id,
            publication_id=publication_id,
            reporter_id=reporter_id,
            report_type=report_type,
            status=status,
            since=since_date,
            until=until_date,
            limit=page_size,
        )
    else:
        reports = await service.list_reports(
            reporter_id=member_id,
            publication_id=publication_id,
            report_type=report_type,
            status=status,
            since=since_date,
            until=until_date,
            limit=page_size,
        )
    return {"items": reports, "total": len(reports)}


@router.get("/submission-detail")
async def submission_detail(
    request: Request,
    publication_id: str,
    report_date: str,
):
    service = _get_service()
    member_id = _member_id(request)
    rd = date.fromisoformat(report_date)
    result = await service.get_submission_detail(publication_id, rd, receiver_id=member_id)
    if not result:
        return {"success": False, "error": "发布不存在"}
    return result


@router.get("/submission-stats")
async def submission_stats(
    request: Request,
    publication_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
):
    service = _get_service()
    member_id = _member_id(request)
    kwargs: dict = {}
    if publication_id:
        kwargs["publication_id"] = publication_id
    if since:
        kwargs["since"] = date.fromisoformat(since)
    if until:
        kwargs["until"] = date.fromisoformat(until)
    stats = await service.get_submission_stats(member_id, **kwargs)
    return {"items": stats}


@router.get("/stats")
async def report_stats(
    request: Request,
    scope: str | None = None,
    since: str | None = None,
    until: str | None = None,
):
    service = _get_service()
    member_id = _member_id(request)
    kwargs: dict = {}
    if scope == "received":
        kwargs["receiver_id"] = member_id
    else:
        kwargs["reporter_id"] = member_id
    if since:
        kwargs["since"] = date.fromisoformat(since)
    if until:
        kwargs["until"] = date.fromisoformat(until)
    stats = await service.get_report_stats(**kwargs)
    return stats


@router.post("")
async def submit_report(req: ReportSubmitRequest, request: Request):
    service = _get_service()
    member_id = _member_id(request) or "unknown"

    report_date = date.fromisoformat(req.report_date) if req.report_date else date.today()
    report = await service.create_report(
        reporter_id=member_id,
        report_type=req.report_type,
        report_date=report_date,
        title=req.title,
        content=req.content,
        status="submitted",
        publication_id=req.publication_id,
    )
    return {"success": True, "report": report}


@router.get("/{report_id}")
async def get_report(report_id: str, request: Request):
    service = _get_service()
    member_id = _member_id(request)
    report = await service.get_report(report_id, member_id=member_id)
    if not report:
        return {"success": False, "error": "汇报不存在"}
    if "error" in report:
        return {"success": False, "error": report["error"]}
    return report


@router.post("/{report_id}/read")
async def mark_read(report_id: str, request: Request):
    service = _get_service()
    member_id = _member_id(request)
    await service.mark_report_read(report_id, member_id)
    return {"success": True}


@router.post("/read-all")
async def mark_all_read(request: Request, publication_id: str | None = None):
    service = _get_service()
    member_id = _member_id(request)
    count = await service.mark_all_reports_read(member_id, publication_id=publication_id)
    return {"success": True, "count": count}


@router.post("/{report_id}/withdraw")
async def withdraw_report(report_id: str, request: Request):
    service = _get_service()
    member_id = _member_id(request)
    result = await service.withdraw_report(report_id, member_id)
    if not result:
        return {"success": False, "error": "汇报不存在"}
    if "error" in result:
        return {"success": False, "error": result["error"]}
    return {"success": True, "report": result}


@router.put("/{report_id}")
async def update_report(report_id: str, req: ReportSubmitRequest, request: Request):
    service = _get_service()
    member_id = _member_id(request)
    fields: dict = {}
    if req.title:
        fields["title"] = req.title
    if req.content:
        fields["content"] = req.content
    result = await service.update_report(report_id, member_id=member_id, **fields)
    if not result:
        return {"success": False, "error": "汇报不存在"}
    if "error" in result:
        return {"success": False, "error": result["error"]}
    return {"success": True, "report": result}
