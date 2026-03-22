"""
飞书 API 封装

异步 HTTP 客户端，封装 token 管理、消息发送、通讯录查询和消息资源下载。
"""

from __future__ import annotations

import asyncio
import json
import time
from io import BytesIO
from uuid import uuid4

import httpx

from openvort.utils.logging import get_logger

log = get_logger("channels.feishu.api")

FEISHU_AUTH_EXPIRED_CODES = {99991663, 99991664, 99991668}


class FeishuAPI:
    """飞书 OpenAPI 客户端"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        api_base: str = "https://open.feishu.cn/open-apis",
    ):
        self._app_id = app_id
        self._app_secret = app_secret
        self._api_base = api_base.rstrip("/")
        self._http = httpx.AsyncClient(timeout=30)
        self._tenant_access_token = ""
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        await self._http.aclose()

    async def health_check(self) -> bool:
        """检查飞书 API 连通性。"""
        try:
            return bool(await self._get_token())
        except Exception as e:
            log.error(f"飞书 API 连通性检查失败: {e}")
            return False

    async def _get_token(self) -> str:
        """获取 tenant_access_token，自动缓存和刷新。"""
        async with self._token_lock:
            if self._tenant_access_token and time.time() < self._token_expires_at - 300:
                return self._tenant_access_token

            resp = await self._http.post(
                f"{self._api_base}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self._app_id,
                    "app_secret": self._app_secret,
                },
            )
            data = resp.json()
            if data.get("code", -1) != 0:
                raise RuntimeError(f"获取 tenant_access_token 失败: {data}")

            self._tenant_access_token = data.get("tenant_access_token", "")
            expires_in = data.get("expire", 7200)
            self._token_expires_at = time.time() + expires_in
            return self._tenant_access_token

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """带鉴权的 JSON API 请求。"""
        token = await self._get_token()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        resp = await self._http.request(method, f"{self._api_base}{path}", headers=headers, **kwargs)
        data = resp.json()

        if data.get("code") in FEISHU_AUTH_EXPIRED_CODES:
            self._tenant_access_token = ""
            token = await self._get_token()
            headers["Authorization"] = f"Bearer {token}"
            resp = await self._http.request(method, f"{self._api_base}{path}", headers=headers, **kwargs)
            data = resp.json()

        if data.get("code", -1) != 0:
            log.error(f"飞书 API 请求失败: {path} -> {data}")
            raise RuntimeError(data.get("msg") or str(data))

        return data

    async def _request_bytes(self, method: str, path: str, **kwargs) -> bytes:
        """带鉴权的二进制 API 请求。"""
        token = await self._get_token()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        resp = await self._http.request(method, f"{self._api_base}{path}", headers=headers, **kwargs)

        if resp.headers.get("content-type", "").startswith("application/json"):
            data = resp.json()
            if data.get("code") in FEISHU_AUTH_EXPIRED_CODES:
                self._tenant_access_token = ""
                token = await self._get_token()
                headers["Authorization"] = f"Bearer {token}"
                resp = await self._http.request(method, f"{self._api_base}{path}", headers=headers, **kwargs)
            else:
                raise RuntimeError(data.get("msg") or str(data))

        return resp.content

    async def send_text(self, receive_id: str, text: str, receive_id_type: str = "open_id") -> dict:
        return await self.send_message(
            receive_id=receive_id,
            msg_type="text",
            content={"text": text},
            receive_id_type=receive_id_type,
        )

    async def send_post(self, receive_id: str, content: dict, receive_id_type: str = "open_id") -> dict:
        return await self.send_message(
            receive_id=receive_id,
            msg_type="post",
            content=content,
            receive_id_type=receive_id_type,
        )

    async def send_interactive(self, receive_id: str, card: dict, receive_id_type: str = "open_id") -> dict:
        return await self.send_message(
            receive_id=receive_id,
            msg_type="interactive",
            content=card,
            receive_id_type=receive_id_type,
        )

    async def send_message(
        self,
        receive_id: str,
        msg_type: str,
        content: str | dict,
        receive_id_type: str = "open_id",
        extra_data: dict | None = None,
    ) -> dict:
        payload_content = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": payload_content,
            "uuid": str(uuid4()),
        }
        if extra_data:
            payload.update(extra_data)
        return await self._request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json=payload,
        )

    async def send_image(self, receive_id: str, image_key: str, receive_id_type: str = "open_id") -> dict:
        return await self.send_message(
            receive_id=receive_id,
            msg_type="image",
            content={"image_key": image_key},
            receive_id_type=receive_id_type,
        )

    async def send_audio(self, receive_id: str, file_key: str, receive_id_type: str = "open_id") -> dict:
        return await self.send_message(
            receive_id=receive_id,
            msg_type="audio",
            content={"file_key": file_key},
            receive_id_type=receive_id_type,
        )

    async def reply_message(
        self,
        message_id: str,
        msg_type: str,
        content: str | dict,
        extra_data: dict | None = None,
    ) -> dict:
        payload_content = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        payload = {
            "msg_type": msg_type,
            "content": payload_content,
            "uuid": str(uuid4()),
        }
        if extra_data:
            payload.update(extra_data)
        return await self._request(
            "POST",
            f"/im/v1/messages/{message_id}/reply",
            json=payload,
        )

    async def create_card(self, card: dict) -> dict:
        return await self._request(
            "POST",
            "/cardkit/v1/cards",
            json={
                "type": "card_json",
                "data": json.dumps(card, ensure_ascii=False),
            },
        )

    async def update_card_markdown(self, card_id: str, text: str, sequence: int, element_id: str = "content") -> dict:
        return await self._request(
            "PUT",
            f"/cardkit/v1/cards/{card_id}/elements/{element_id}/content",
            json={
                "content": text,
                "sequence": sequence,
                "uuid": f"s_{card_id}_{sequence}",
            },
        )

    async def update_card_settings(self, card_id: str, settings: dict, sequence: int) -> dict:
        return await self._request(
            "PATCH",
            f"/cardkit/v1/cards/{card_id}/settings",
            json={
                "settings": json.dumps(settings, ensure_ascii=False),
                "sequence": sequence,
                "uuid": f"c_{card_id}_{sequence}",
            },
        )

    async def upload_image(self, data: bytes, filename: str = "image.png") -> str:
        token = await self._get_token()
        resp = await self._http.post(
            f"{self._api_base}/im/v1/images",
            headers={"Authorization": f"Bearer {token}"},
            data={"image_type": "message"},
            files={"image": (filename, BytesIO(data), "application/octet-stream")},
        )
        payload = resp.json()
        if payload.get("code", -1) != 0:
            raise RuntimeError(payload.get("msg") or str(payload))
        return payload.get("data", {}).get("image_key", "")

    async def upload_file(
        self,
        data: bytes,
        filename: str,
        file_type: str = "stream",
        duration: int | None = None,
    ) -> str:
        token = await self._get_token()
        form_data = {
            "file_type": file_type,
            "file_name": filename,
        }
        if duration is not None:
            form_data["duration"] = str(duration)
        resp = await self._http.post(
            f"{self._api_base}/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data=form_data,
            files={"file": (filename, BytesIO(data), "application/octet-stream")},
        )
        payload = resp.json()
        if payload.get("code", -1) != 0:
            raise RuntimeError(payload.get("msg") or str(payload))
        return payload.get("data", {}).get("file_key", "")

    async def download_image(self, image_key: str) -> bytes:
        return await self._request_bytes("GET", f"/im/v1/images/{image_key}")

    async def download_message_resource(self, message_id: str, file_key: str, resource_type: str) -> bytes:
        return await self._request_bytes(
            "GET",
            f"/im/v1/messages/{message_id}/resources/{file_key}",
            params={"type": resource_type},
        )

    async def get_user(self, user_id: str, id_type: str = "open_id") -> dict:
        data = await self._request(
            "GET",
            f"/contact/v3/users/{user_id}",
            params={"user_id_type": id_type},
        )
        return data.get("data", {}).get("user", {})

    async def get_department_users(self, department_id: str) -> list[dict]:
        users: list[dict] = []
        page_token = ""

        while True:
            data = await self._request(
                "GET",
                "/contact/v3/users/find_by_department",
                params={
                    "department_id": department_id,
                    "department_id_type": "department_id",
                    "user_id_type": "open_id",
                    "page_size": 50,
                    "page_token": page_token,
                },
            )
            payload = data.get("data", {})
            users.extend(payload.get("items", []))
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token", "")
            if not page_token:
                break

        return users

    async def get_departments(self, parent_id: str = "0") -> list[dict]:
        departments: list[dict] = []
        page_token = ""

        while True:
            data = await self._request(
                "GET",
                "/contact/v3/departments",
                params={
                    "parent_department_id": parent_id,
                    "department_id_type": "department_id",
                    "page_size": 50,
                    "page_token": page_token,
                },
            )
            payload = data.get("data", {})
            departments.extend(payload.get("items", []))
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token", "")
            if not page_token:
                break

        return departments
