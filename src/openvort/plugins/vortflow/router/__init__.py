"""VortFlow FastAPI router package."""

from fastapi import APIRouter

from .projects import sub_router as projects_router
from .stories import sub_router as stories_router
from .tasks import sub_router as tasks_router
from .bugs import sub_router as bugs_router
from .milestones import sub_router as milestones_router
from .iterations import sub_router as iterations_router
from .versions import sub_router as versions_router
from .views import sub_router as views_router
from .comments import sub_router as comments_router
from .work_item_links import sub_router as work_item_links_router
from .tags import sub_router as tags_router
from .statuses import sub_router as statuses_router
from .test_cases import sub_router as test_cases_router

router = APIRouter(prefix="/api/vortflow", tags=["vortflow"])

router.include_router(projects_router)
router.include_router(stories_router)
router.include_router(tasks_router)
router.include_router(bugs_router)
router.include_router(milestones_router)
router.include_router(iterations_router)
router.include_router(versions_router)
router.include_router(views_router)
router.include_router(comments_router)
router.include_router(work_item_links_router)
router.include_router(tags_router)
router.include_router(statuses_router)
router.include_router(test_cases_router)
