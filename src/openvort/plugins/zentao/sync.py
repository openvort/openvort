"""
禅道通讯录同步

从禅道数据库读取用户和部门信息，转换为 OpenVort 通讯录格式。
"""

from openvort.contacts.sync import ContactSyncProvider, PlatformContact, PlatformDepartment
from openvort.plugins.zentao.db import ZentaoDB
from openvort.utils.logging import get_logger

log = get_logger("plugins.zentao.sync")


class ZentaoContactSyncProvider(ContactSyncProvider):
    """禅道通讯录同步提供者"""

    platform = "zentao"

    def __init__(self, db: ZentaoDB):
        self._db = db

    async def fetch_members(self) -> list[PlatformContact]:
        """从禅道 zt_user 表拉取全量用户"""
        rows = await self._db.async_fetch_all(
            "SELECT account, realname, email, mobile, role, dept FROM zt_user WHERE deleted='0'"
        )
        contacts = []
        for row in rows:
            contacts.append(PlatformContact(
                platform="zentao",
                user_id=row.get("account", ""),
                username=row.get("account", ""),
                display_name=row.get("realname", ""),
                email=row.get("email", ""),
                phone=row.get("mobile", ""),
                position=row.get("role", ""),
                department=str(row.get("dept", "")),
                raw_data=row,
            ))
        return contacts

    async def fetch_departments(self) -> list[PlatformDepartment]:
        """从禅道 zt_dept 表拉取部门列表"""
        rows = await self._db.async_fetch_all(
            "SELECT id, name, parent FROM zt_dept WHERE deleted='0' ORDER BY `order`"
        )
        departments = []
        for row in rows:
            departments.append(PlatformDepartment(
                platform="zentao",
                dept_id=str(row.get("id", "")),
                name=row.get("name", ""),
                parent_dept_id=str(row.get("parent", "")),
            ))
        return departments
