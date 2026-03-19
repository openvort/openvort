"""企业日历路由"""

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.web.deps import get_db_session_factory

router = APIRouter()


class CalendarEntryRequest(BaseModel):
    date: str  # YYYY-MM-DD
    day_type: str  # workday / holiday
    name: str = ""


class BatchCalendarRequest(BaseModel):
    entries: list[CalendarEntryRequest]


@router.get("")
async def list_calendar(year: int | None = None):
    """按年份获取企业日历"""
    from sqlalchemy import select

    from openvort.contacts.models import OrgCalendar

    if year is None:
        year = date.today().year

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = (
            select(OrgCalendar)
            .where(OrgCalendar.year == year)
            .order_by(OrgCalendar.date)
        )
        result = await session.execute(stmt)
        entries = result.scalars().all()

        items = []
        for e in entries:
            items.append({
                "id": e.id,
                "date": e.date.isoformat(),
                "day_type": e.day_type,
                "name": e.name,
                "year": e.year,
            })
        return {"entries": items, "year": year}


@router.post("")
async def create_entry(req: CalendarEntryRequest):
    """新增日历条目"""
    from openvort.contacts.models import OrgCalendar

    entry_date = date.fromisoformat(req.date)
    session_factory = get_db_session_factory()
    async with session_factory() as session:
        entry = OrgCalendar(
            date=entry_date,
            day_type=req.day_type,
            name=req.name,
            year=entry_date.year,
        )
        session.add(entry)
        try:
            await session.commit()
            await session.refresh(entry)
            return {"success": True, "id": entry.id}
        except Exception:
            await session.rollback()
            return {"success": False, "error": "该日期已存在日历条目"}


@router.post("/batch")
async def batch_create(req: BatchCalendarRequest):
    """批量导入日历条目（已存在的跳过）"""
    from sqlalchemy import select

    from openvort.contacts.models import OrgCalendar

    session_factory = get_db_session_factory()
    created = 0
    skipped = 0

    async with session_factory() as session:
        for item in req.entries:
            entry_date = date.fromisoformat(item.date)
            stmt = select(OrgCalendar).where(OrgCalendar.date == entry_date)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                skipped += 1
                continue

            entry = OrgCalendar(
                date=entry_date,
                day_type=item.day_type,
                name=item.name,
                year=entry_date.year,
            )
            session.add(entry)
            created += 1

        await session.commit()

    return {"success": True, "created": created, "skipped": skipped}


@router.delete("/{entry_id}")
async def delete_entry(entry_id: int):
    """删除日历条目"""
    from sqlalchemy import delete

    from openvort.contacts.models import OrgCalendar

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = delete(OrgCalendar).where(OrgCalendar.id == entry_id)
        result = await session.execute(stmt)
        await session.commit()
        return {"success": result.rowcount > 0}


@router.post("/sync-holidays")
async def sync_holidays(year: int | None = None):
    """从公开 API 同步法定节假日"""
    import httpx

    from openvort.contacts.models import OrgCalendar

    if year is None:
        year = date.today().year

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"https://timor.tech/api/holiday/year/{year}")
            data = resp.json()

        if data.get("code") != 0:
            return {"success": False, "error": data.get("msg", "API 返回错误")}

        holidays = data.get("holiday", {})
        entries: list[CalendarEntryRequest] = []
        for _date_str, info in holidays.items():
            if info.get("holiday"):
                entries.append(CalendarEntryRequest(
                    date=info["date"],
                    day_type="holiday",
                    name=info.get("name", ""),
                ))
            else:
                entries.append(CalendarEntryRequest(
                    date=info["date"],
                    day_type="workday",
                    name=info.get("name", "调休补班"),
                ))

        result = await batch_create(BatchCalendarRequest(entries=entries))
        return {
            "success": True,
            "year": year,
            "total_entries": len(entries),
            "created": result.get("created", 0),
            "skipped": result.get("skipped", 0),
        }
    except httpx.HTTPError as e:
        return {"success": False, "error": f"请求节假日 API 失败: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class UpdateWorkSettingsRequest(BaseModel):
    timezone: str | None = None
    work_start: str | None = None
    work_end: str | None = None
    work_days: str | None = None
    lunch_start: str | None = None
    lunch_end: str | None = None


_ORG_DB_PREFIX = "org."
_ORG_FIELDS = ("timezone", "work_start", "work_end", "work_days", "lunch_start", "lunch_end")


@router.get("/work-settings")
async def get_work_settings():
    """获取工时设置（DB 覆盖优先于 .env）"""
    from openvort.config.settings import get_settings
    org = get_settings().org
    return {
        "timezone": org.timezone,
        "work_start": org.work_start,
        "work_end": org.work_end,
        "work_days": org.work_days,
        "lunch_start": org.lunch_start,
        "lunch_end": org.lunch_end,
    }


@router.put("/work-settings")
async def update_work_settings(req: UpdateWorkSettingsRequest):
    """更新工时设置（保存到 DB 并同步 settings 单例）"""
    from openvort.config.settings import get_settings
    from openvort.web.deps import get_config_service

    config_service = get_config_service()
    settings = get_settings()
    items: dict[str, str] = {}

    for field in _ORG_FIELDS:
        value = getattr(req, field, None)
        if value is not None:
            items[f"{_ORG_DB_PREFIX}{field}"] = value
            setattr(settings.org, field, value)

    if items:
        await config_service.set_many(items)

    return {"success": True}
