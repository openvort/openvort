"""
企微 API 封装

异步 HTTP 客户端，封装 token 管理、消息发送、通讯录查询。
配置通过构造函数注入，支持多应用实例。
"""

import asyncio
import time

import httpx

from openvort.utils.logging import get_logger

log = get_logger("channels.wecom.api")


class WeComAPI:
    """企业微信 API 客户端"""

    def __init__(
        self,
        corp_id: str,
        app_secret: str,
        agent_id: str = "",
        api_base: str = "https://qyapi.weixin.qq.com/cgi-bin",
    ):
        self._corp_id = corp_id
        self._app_secret = app_secret
        self._agent_id = agent_id
        self._api_base = api_base
        self._http = httpx.AsyncClient(timeout=30)

        # Token 管理
        self._access_token: str = ""
        self._token_expires_at: float = 0
        self._token_lock = asyncio.Lock()

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        await self._http.aclose()

    # ---- Token 管理 ----

    async def get_access_token(self) -> str:
        """获取 access_token，自动刷新"""
        async with self._token_lock:
            if self._access_token and time.time() < self._token_expires_at - 60:
                return self._access_token

            resp = await self._http.get(
                f"{self._api_base}/gettoken",
                params={"corpid": self._corp_id, "corpsecret": self._app_secret},
            )
            data = resp.json()

            if data.get("errcode", 0) != 0:
                raise RuntimeError(f"获取 access_token 失败: {data}")

            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 7200)
            log.debug("access_token 已刷新")
            return self._access_token

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """带 token 的 API 请求"""
        token = await self.get_access_token()
        params = kwargs.pop("params", {})
        params["access_token"] = token

        resp = await self._http.request(method, f"{self._api_base}{path}", params=params, **kwargs)
        data = resp.json()

        # Token 过期自动重试一次
        if data.get("errcode") in (40014, 42001):
            log.warning("access_token 已过期，重新获取")
            self._access_token = ""
            token = await self.get_access_token()
            params["access_token"] = token
            resp = await self._http.request(method, f"{self._api_base}{path}", params=params, **kwargs)
            data = resp.json()

        if data.get("errcode", 0) != 0:
            log.error(f"API 请求失败: {path} -> {data}")

        return data

    # ---- 消息发送 ----

    async def send_text(self, content: str, touser: str = "", toparty: str = "", totag: str = "") -> dict:
        """发送文本消息"""
        payload = {
            "msgtype": "text",
            "agentid": self._agent_id,
            "text": {"content": content},
        }
        self._set_recipients(payload, touser, toparty, totag)
        return await self._request("POST", "/message/send", json=payload)

    async def send_markdown(self, content: str, touser: str = "", toparty: str = "", totag: str = "") -> dict:
        """发送 Markdown 消息"""
        payload = {
            "msgtype": "markdown",
            "agentid": self._agent_id,
            "markdown": {"content": content},
        }
        self._set_recipients(payload, touser, toparty, totag)
        return await self._request("POST", "/message/send", json=payload)

    async def send_textcard(
        self, title: str, description: str, url: str, btntxt: str = "详情",
        touser: str = "", toparty: str = "", totag: str = "",
    ) -> dict:
        """发送文本卡片消息"""
        payload = {
            "msgtype": "textcard",
            "agentid": self._agent_id,
            "textcard": {"title": title, "description": description, "url": url, "btntxt": btntxt},
        }
        self._set_recipients(payload, touser, toparty, totag)
        return await self._request("POST", "/message/send", json=payload)

    # ---- 通讯录 ----

    async def get_user(self, user_id: str) -> dict:
        """获取成员信息"""
        return await self._request("GET", "/user/get", params={"userid": user_id})

    async def get_department_users(self, department_id: int = 1) -> list[dict]:
        """获取部门成员列表"""
        data = await self._request("GET", "/user/list", params={"department_id": department_id})
        return data.get("userlist", [])

    # ---- 工具方法 ----

    @staticmethod
    def _set_recipients(payload: dict, touser: str, toparty: str, totag: str) -> None:
        """设置消息接收者"""
        if touser:
            payload["touser"] = touser if isinstance(touser, str) else "|".join(touser)
        elif not toparty and not totag:
            payload["touser"] = "@all"
        if toparty:
            payload["toparty"] = toparty if isinstance(toparty, str) else "|".join(toparty)
        if totag:
            payload["totag"] = totag if isinstance(totag, str) else "|".join(totag)

    async def health_check(self) -> bool:
        """检查 API 连通性"""
        try:
            token = await self.get_access_token()
            return bool(token)
        except Exception as e:
            log.error(f"企微 API 连通性检查失败: {e}")
            return False

    # ---- 媒体文件管理 ----

    async def upload_media(self, media_type: str, file_content: bytes, file_name: str) -> dict:
        """上传临时素材

        Args:
            media_type: 媒体文件类型 (image, voice, video, file)
            file_content: 文件二进制内容
            file_name: 文件名

        Returns:
            {"media_id": "xxx", "created_at": 1234567890}
        """
        from io import BytesIO

        files = {
            "media": (file_name, BytesIO(file_content), f"audio/{file_name.split('.')[-1]}")
        }
        params = {
            "access_token": await self.get_access_token(),
            "type": media_type,
        }
        resp = await self._http.post(
            f"{self._api_base}/media/upload",
            params=params,
            files=files,
        )
        data = resp.json()

        if data.get("errcode", 0) != 0:
            log.error(f"上传媒体文件失败: {data}")
            raise RuntimeError(f"上传媒体文件失败: {data}")

        log.info(f"媒体文件上传成功: media_id={data.get('media_id')}")
        return data

    async def get_media(self, media_id: str) -> bytes:
        """下载临时素材

        Args:
            media_id: 媒体文件 ID

        Returns:
            文件二进制内容
        """
        params = {
            "access_token": await self.get_access_token(),
            "media_id": media_id,
        }
        resp = await self._http.get(
            f"{self._api_base}/media/get",
            params=params,
        )

        # 检查是否返回错误 JSON
        try:
            data = resp.json()
            if data.get("errcode", 0) != 0:
                log.error(f"下载媒体文件失败: {data}")
                raise RuntimeError(f"下载媒体文件失败: {data}")
        except Exception:
            # 非 JSON 响应，说明是实际的媒体文件内容
            pass

        return resp.content

    async def send_voice(self, media_id: str, touser: str = "", toparty: str = "", totag: str = "") -> dict:
        """发送语音消息

        Args:
            media_id: 语音文件的 media_id
            touser: 接收成员 ID
            toparty: 接收部门 ID
            totag: 接收标签 ID

        Returns:
            API 响应
        """
        payload = {
            "msgtype": "voice",
            "agentid": self._agent_id,
            "voice": {"media_id": media_id},
        }
        self._set_recipients(payload, touser, toparty, totag)
        return await self._request("POST", "/message/send", json=payload)
