"""VortFlow FastAPI router package."""

from fastapi import APIRouter

from .dashboard import sub_router as dashboard_router
from .projects import sub_router as projects_router
from .stories import sub_router as stories_router
from .tasks import sub_router as tasks_router
from .bugs import sub_router as bugs_router
from .iterations import sub_router as iterations_router
from .versions import sub_router as versions_router
from .views import sub_router as views_router
from .comments import sub_router as comments_router
from .work_item_links import sub_router as work_item_links_router
from .tags import sub_router as tags_router
from .statuses import sub_router as statuses_router
from .test_cases import sub_router as test_cases_router
from .test_plans import sub_router as test_plans_router
from .test_reports import sub_router as test_reports_router
from .notify import sub_router as notify_router
from .description_templates import sub_router as description_templates_router
from .convert import sub_router as convert_router
from .document_links import sub_router as document_links_router
from .reminder import sub_router as reminder_router
from .archive import sub_router as archive_router

router = APIRouter(prefix="/api/vortflow", tags=["vortflow"])

router.include_router(dashboard_router)
router.include_router(projects_router)
router.include_router(stories_router)
router.include_router(tasks_router)
router.include_router(bugs_router)
router.include_router(iterations_router)
router.include_router(versions_router)
router.include_router(views_router)
router.include_router(comments_router)
router.include_router(work_item_links_router)
router.include_router(tags_router)
router.include_router(statuses_router)
router.include_router(test_cases_router)
router.include_router(test_plans_router)
router.include_router(test_reports_router)
router.include_router(notify_router)
router.include_router(description_templates_router)
router.include_router(convert_router)
router.include_router(document_links_router)
router.include_router(reminder_router)
router.include_router(archive_router)
