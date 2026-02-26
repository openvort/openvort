"""
企业微信通讯录同步

调用企微 API 拉取部门和成员，转换为 OpenVort 通讯录格式。
"""

from openvort.channels.wecom.api import WeComAPI
from openvort.contacts.sync import ContactSyncProvider, PlatformContact, PlatformDepartment
from openvort.utils.logging import get_logger

log = get_logger("channels.wecom.sync")


class WeComContactSyncProvider(ContactSyncProvider):
    """企业微信通讯录同步提供者"""

    platform = "wecom"

    def __init__(self, api: WeComAPI):
        self._api = api

    async def fetch_members(self) -> list[PlatformContact]:
        """拉取企微全量成员（从根部门递归）"""
        contacts = []
        dept_ids = await self._get_all_department_ids()

        for dept_id in dept_ids:
            try:
                users = await self._api.get_department_users(dept_id)
                for u in users:
                    contacts.append(PlatformContact(
                        platform="wecom",
                        user_id=u.get("userid", ""),
                        username=u.get("userid", ""),
                        display_name=u.get("name", ""),
                        email=u.get("email", ""),
                        phone=u.get("mobile", ""),
                        position=u.get("position", ""),
                        department=",".join(str(d) for d in u.get("department", [])),
                        raw_data=u,
                    ))
            except Exception as e:
                log.warning(f"拉取部门 {dept_id} 成员失败: {e}")

        # 按 user_id 去重（一个人可能在多个部门）
        seen = set()
        unique = []
        for c in contacts:
            if c.user_id not in seen:
                seen.add(c.user_id)
                unique.append(c)

        return unique

    async def fetch_departments(self) -> list[PlatformDepartment]:
        """拉取企微部门列表"""
        data = await self._api._request("GET", "/department/list")
        departments = []
        for d in data.get("department", []):
            departments.append(PlatformDepartment(
                platform="wecom",
                dept_id=str(d.get("id", "")),
                name=d.get("name", ""),
                parent_dept_id=str(d.get("parentid", "")),
            ))
        return departments

    async def _get_all_department_ids(self) -> list[int]:
        """获取所有部门 ID"""
        data = await self._api._request("GET", "/department/list")
        return [d["id"] for d in data.get("department", [])]
