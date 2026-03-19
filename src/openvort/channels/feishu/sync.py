"""
飞书通讯录同步

调用飞书通讯录 API 拉取部门和成员，转换为 OpenVort 通讯录格式。
"""

from __future__ import annotations

from openvort.channels.feishu.api import FeishuAPI
from openvort.contacts.sync import ContactSyncProvider, PlatformContact, PlatformDepartment
from openvort.utils.logging import get_logger

log = get_logger("channels.feishu.sync")

FEISHU_ROOT_DEPARTMENT_ID = "0"
FEISHU_ROOT_DEPARTMENT_NAME = "根部门"


class FeishuContactSyncProvider(ContactSyncProvider):
    """飞书通讯录同步提供者。"""

    platform = "feishu"

    def __init__(self, api: FeishuAPI):
        self._api = api

    async def fetch_members(self) -> list[PlatformContact]:
        contacts: list[PlatformContact] = []
        departments = await self.fetch_departments()
        seen: set[str] = set()

        for dept in departments:
            try:
                users = await self._api.get_department_users(dept.dept_id)
            except Exception as e:
                log.warning(f"拉取飞书部门成员失败: dept={dept.dept_id}, err={e}")
                continue

            for user in users:
                user = await self._enrich_user(user)
                open_id = user.get("open_id", "")
                if not open_id or open_id in seen:
                    continue
                seen.add(open_id)

                department_ids = user.get("department_ids") or [dept.dept_id]
                department = ",".join(str(item) for item in department_ids if item)
                avatar = user.get("avatar", {}) or {}
                contacts.append(PlatformContact(
                    platform="feishu",
                    user_id=open_id,
                    username=user.get("user_id", "") or open_id,
                    display_name=user.get("name", ""),
                    email=user.get("email", ""),
                    phone=user.get("mobile", ""),
                    avatar_url=avatar.get("avatar_72", "") or avatar.get("avatar_240", ""),
                    position=user.get("job_title", "") or user.get("position", ""),
                    department=department,
                    raw_data=user,
                ))

        return contacts

    async def _enrich_user(self, user: dict) -> dict:
        """Fetch full user detail when department listing returns only minimal fields."""
        open_id = (user.get("open_id") or "").strip()
        if not open_id:
            return user

        if any(user.get(key) for key in ("name", "email", "mobile", "user_id", "job_title", "position")):
            return user

        try:
            detail = await self._api.get_user(open_id, "open_id")
        except Exception as e:
            log.warning(f"拉取飞书用户详情失败: open_id={open_id}, err={e}")
            return user

        if not detail:
            return user

        merged = dict(user)
        merged.update({k: v for k, v in detail.items() if v not in (None, "")})
        merged.setdefault("open_id", open_id)
        return merged

    async def fetch_departments(self) -> list[PlatformDepartment]:
        departments: list[PlatformDepartment] = [
            PlatformDepartment(
                platform="feishu",
                dept_id=FEISHU_ROOT_DEPARTMENT_ID,
                name=FEISHU_ROOT_DEPARTMENT_NAME,
                parent_dept_id="",
            )
        ]
        seen: set[str] = {FEISHU_ROOT_DEPARTMENT_ID}
        queue = [FEISHU_ROOT_DEPARTMENT_ID]

        while queue:
            parent_id = queue.pop(0)
            try:
                items = await self._api.get_departments(parent_id)
            except Exception as e:
                log.warning(f"拉取飞书部门失败: parent={parent_id}, err={e}")
                continue

            for item in items:
                dept_id = item.get("department_id", "")
                if not dept_id or dept_id in seen:
                    continue
                seen.add(dept_id)
                departments.append(PlatformDepartment(
                    platform="feishu",
                    dept_id=dept_id,
                    name=item.get("name", ""),
                    parent_dept_id=item.get("parent_department_id", ""),
                ))
                queue.append(dept_id)

        return departments
