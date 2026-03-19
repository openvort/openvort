"""
钉钉通讯录同步

调用钉钉组织通讯录 API 拉取部门与成员，转换为 OpenVort 通讯录格式。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openvort.contacts.sync import ContactSyncProvider, PlatformContact, PlatformDepartment
from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from openvort.channels.dingtalk.channel import DingTalkChannel

log = get_logger("channels.dingtalk.sync")

DT_OAPI_BASE = "https://oapi.dingtalk.com"
DT_ROOT_DEPARTMENT_ID = "1"
DT_ROOT_DEPARTMENT_NAME = "根部门"


class DingTalkContactSyncProvider(ContactSyncProvider):
    """钉钉通讯录同步提供者。"""

    platform = "dingtalk"

    def __init__(self, channel: "DingTalkChannel"):
        self._channel = channel

    async def fetch_departments(self) -> list[PlatformDepartment]:
        departments: list[PlatformDepartment] = [
            PlatformDepartment(
                platform="dingtalk",
                dept_id=DT_ROOT_DEPARTMENT_ID,
                name=DT_ROOT_DEPARTMENT_NAME,
                parent_dept_id="",
            )
        ]
        seen: set[str] = {DT_ROOT_DEPARTMENT_ID}
        queue = [DT_ROOT_DEPARTMENT_ID]

        while queue:
            parent_id = queue.pop(0)
            try:
                items = await self._request(
                    "/topapi/v2/department/listsub",
                    json={"dept_id": int(parent_id)},
                )
            except Exception as exc:
                log.warning("拉取钉钉部门失败: parent=%s err=%s", parent_id, exc)
                continue

            for item in items:
                dept_id = str(item.get("dept_id") or item.get("deptId") or "").strip()
                if not dept_id or dept_id in seen:
                    continue
                seen.add(dept_id)
                parent_dept_id = str(
                    item.get("parent_id") or item.get("parentId") or parent_id
                ).strip()
                departments.append(
                    PlatformDepartment(
                        platform="dingtalk",
                        dept_id=dept_id,
                        name=str(item.get("name") or "").strip(),
                        parent_dept_id=parent_dept_id,
                    )
                )
                queue.append(dept_id)

        return departments

    async def fetch_members(self) -> list[PlatformContact]:
        departments = await self.fetch_departments()
        department_name_map = {dept.dept_id: dept.name for dept in departments}
        seen_users: set[str] = set()
        contacts: list[PlatformContact] = []

        for dept in departments:
            cursor = 0
            while True:
                try:
                    page = await self._request(
                        "/topapi/user/listsimple",
                        json={
                            "dept_id": int(dept.dept_id),
                            "cursor": cursor,
                            "size": 100,
                            "contain_access_limit": False,
                        },
                    )
                except Exception as exc:
                    log.warning("拉取钉钉部门成员失败: dept=%s err=%s", dept.dept_id, exc)
                    break

                users = page.get("list") or page.get("result") or []
                if not isinstance(users, list):
                    users = []

                for user in users:
                    user_id = str(user.get("userid") or user.get("userId") or "").strip()
                    if not user_id or user_id in seen_users:
                        continue
                    seen_users.add(user_id)

                    detail = await self._get_user_detail(user_id)
                    merged = dict(user)
                    merged.update({k: v for k, v in detail.items() if v not in (None, "")})

                    dept_ids = merged.get("dept_id_list") or merged.get("department") or [dept.dept_id]
                    if not isinstance(dept_ids, list):
                        dept_ids = [dept.dept_id]
                    dept_ids = [str(item).strip() for item in dept_ids if str(item).strip()]
                    dept_names = [department_name_map.get(item, item) for item in dept_ids]

                    contacts.append(
                        PlatformContact(
                            platform="dingtalk",
                            user_id=user_id,
                            username=user_id,
                            display_name=str(
                                merged.get("name") or merged.get("nick") or merged.get("remark") or ""
                            ).strip(),
                            email=str(merged.get("email") or "").strip(),
                            phone=str(merged.get("mobile") or merged.get("telephone") or "").strip(),
                            avatar_url=str(
                                merged.get("avatar") or merged.get("avatar_mediaid") or ""
                            ).strip(),
                            position=str(
                                merged.get("title") or merged.get("position") or ""
                            ).strip(),
                            department=",".join(dept_ids),
                            raw_data={
                                **merged,
                                "department_names": dept_names,
                            },
                        )
                    )

                has_more = bool(page.get("has_more"))
                next_cursor = page.get("next_cursor")
                if not has_more or next_cursor in (None, "", cursor):
                    break
                cursor = int(next_cursor)

        return contacts

    async def _get_user_detail(self, user_id: str) -> dict[str, Any]:
        try:
            result = await self._request("/topapi/v2/user/get", json={"userid": user_id})
        except Exception as exc:
            log.warning("拉取钉钉用户详情失败: user_id=%s err=%s", user_id, exc)
            return {}

        if isinstance(result, dict):
            return result
        return {}

    async def _request(self, path: str, json: dict[str, Any] | None = None) -> Any:
        token = await self._channel._get_access_token()  # noqa: SLF001
        response = await self._channel._get_http().post(  # noqa: SLF001
            f"{DT_OAPI_BASE}{path}",
            params={"access_token": token},
            headers={"Content-Type": "application/json"},
            json=json or {},
        )
        response.raise_for_status()

        data = response.json()
        errcode = data.get("errcode", 0)
        if errcode not in (0, "0", None):
            errmsg = data.get("errmsg") or data.get("message") or "unknown error"
            raise RuntimeError(f"{path} failed: errcode={errcode}, errmsg={errmsg}")

        return data.get("result", data)
