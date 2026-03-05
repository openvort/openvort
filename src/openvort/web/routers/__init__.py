"""
Web 面板路由
"""

from openvort.web.routers.auth import router as auth_router
from openvort.web.routers.chat import router as chat_router
from openvort.web.routers.dashboard import router as dashboard_router
from openvort.web.routers.me import router as me_router
from openvort.web.routers.contacts import router as contacts_router
from openvort.web.routers.members import router as members_router
from openvort.web.routers.departments import router as departments_router
from openvort.web.routers.reporting import router as reporting_router
from openvort.web.routers.org_calendar import router as org_calendar_router
from openvort.web.routers.plugins import router as plugins_router
from openvort.web.routers.skills import router as skills_router
from openvort.web.routers.member_skills import router as member_skills_router
from openvort.web.routers.channels import router as channels_router
from openvort.web.routers.settings import router as settings_router
from openvort.web.routers.logs import router as logs_router
from openvort.web.routers.schedules import schedules_router, admin_schedules_router
from openvort.web.routers.webhooks import router as webhooks_admin_router
from openvort.web.routers.agents import router as agents_router
from openvort.web.routers.models import router as models_router
from openvort.web.routers.upgrade import router as upgrade_router
from openvort.web.routers.virtual_roles import router as posts_router

# 保留旧名称的别名，保持向后兼容
virtual_roles_router = posts_router
from openvort.web.routers.work_assignments import work_assignments_router

__all__ = [
    "auth_router",
    "chat_router",
    "dashboard_router",
    "me_router",
    "contacts_router",
    "members_router",
    "departments_router",
    "reporting_router",
    "org_calendar_router",
    "plugins_router",
    "skills_router",
    "channels_router",
    "settings_router",
    "logs_router",
    "schedules_router",
    "admin_schedules_router",
    "webhooks_admin_router",
    "agents_router",
    "models_router",
    "member_skills_router",
    "upgrade_router",
    "posts_router",
    "virtual_roles_router",  # 兼容旧名称
    "work_assignments_router",
]
