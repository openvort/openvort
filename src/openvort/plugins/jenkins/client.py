"""
Jenkins REST API client.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx

@dataclass(slots=True)
class JenkinsConnection:
    """Runtime Jenkins connection config."""

    url: str
    username: str
    api_token: str
    verify_ssl: bool = True


class JenkinsClientError(RuntimeError):
    """Raised when Jenkins API call fails."""


class JenkinsClient:
    """轻量 Jenkins API 客户端（Basic Auth + 可选 Crumb）。"""

    def __init__(self, connection: JenkinsConnection):
        self._connection = connection
        self._base_url = (connection.url or "").rstrip("/")
        self._username = connection.username or ""
        self._api_token = connection.api_token or ""
        self._verify_ssl = bool(connection.verify_ssl)
        self._client = httpx.AsyncClient(
            timeout=30,
            auth=(self._username, self._api_token) if self._username else None,
            verify=self._verify_ssl,
        )
        self._crumb_field = ""
        self._crumb_value = ""

    def is_configured(self) -> bool:
        return bool(self._base_url and self._username and self._api_token)

    def missing_config_fields(self) -> list[str]:
        missing: list[str] = []
        if not self._base_url:
            missing.append("url")
        if not self._username:
            missing.append("username")
        if not self._api_token:
            missing.append("api_token")
        return missing

    async def close(self) -> None:
        await self._client.aclose()

    async def get_system_info(self) -> dict:
        tree = "mode,nodeDescription,useCrumbs,primaryView[name],views[name],numExecutors,quietingDown"
        return await self._get_json(f"/api/json?tree={tree}")

    async def list_jobs(
        self,
        *,
        view: str = "",
        folder: str = "",
        keyword: str = "",
        recursive: bool = True,
        include_folders: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        tree = "jobs[name,fullName,url,color,_class,lastBuild[number,url,result,timestamp,building],inQueue]"
        if view and folder:
            raise JenkinsClientError("view 和 folder 不能同时指定")

        if view:
            root_path = self._job_path(view, is_view=True)
        elif folder:
            root_path = self._job_path(folder)
        else:
            root_path = ""

        root_data = await self._get_json(
            f"{root_path}/api/json?tree={tree}" if root_path else f"/api/json?tree={tree}"
        )
        jobs_raw = root_data.get("jobs", []) if isinstance(root_data, dict) else []
        keyword_lc = keyword.strip().lower()
        max_limit = max(1, limit)

        jobs: list[dict] = []
        seen: set[str] = set()
        folder_queue: list[str] = []
        visited_folders: set[str] = set()

        def collect(items: list[dict], parent_full_name: str = "") -> None:
            for item in items:
                name = str(item.get("name", "") or "")
                raw_full_name = str(item.get("fullName", "") or "")
                full_name = raw_full_name or f"{parent_full_name}/{name}".strip("/") or name
                if not full_name:
                    continue

                is_folder = self._is_folder(item)
                if is_folder and recursive and full_name not in visited_folders:
                    folder_queue.append(full_name)

                unique_key = full_name or item.get("url", "")
                if unique_key in seen:
                    continue
                seen.add(unique_key)

                if not include_folders and is_folder:
                    continue
                if keyword_lc and keyword_lc not in name.lower() and keyword_lc not in full_name.lower():
                    continue

                jobs.append(
                    {
                        "name": name,
                        "full_name": full_name,
                        "url": item.get("url", ""),
                        "color": item.get("color", ""),
                        "in_queue": bool(item.get("inQueue", False)),
                        "last_build": item.get("lastBuild") or None,
                        "is_folder": is_folder,
                        "class": item.get("_class", ""),
                    }
                )

        collect(jobs_raw)
        while folder_queue:
            folder_name = folder_queue.pop(0)
            if folder_name in visited_folders:
                continue
            visited_folders.add(folder_name)

            sub_data = await self._get_json(f"{self._job_path(folder_name)}/api/json?tree={tree}")
            sub_jobs = sub_data.get("jobs", []) if isinstance(sub_data, dict) else []
            collect(sub_jobs, parent_full_name=folder_name)

        return jobs[:max_limit]

    async def get_job_info(self, job_name: str) -> dict:
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        tree = (
            "name,fullName,displayName,description,url,buildable,color,nextBuildNumber,"
            "inQueue,lastBuild[number,result,timestamp,building,duration,url],"
            "lastCompletedBuild[number,result,timestamp,duration,url],"
            "builds[number,result,timestamp,building,duration,url]{0,20},"
            "property[parameterDefinitions[name,type,_class,defaultParameterValue[value],description,choices]]"
        )
        return await self._get_json(f"{self._job_path(job_name)}/api/json?tree={tree}")

    async def get_parameter_choices(self, job_name: str, param_name: str, param_class: str) -> list[str]:
        """Fetch dynamic choices for a build parameter (e.g. Git branches)."""
        try:
            safe_class = quote(param_class, safe=".@$")
            safe_param = quote(param_name, safe="")
            path = f"{self._job_path(job_name)}/descriptorByName/{safe_class}/fillValueItems?param={safe_param}"
            data = await self._get_json(path)
            values = data.get("values", [])
            return [
                str(v.get("value", "") or v.get("name", ""))
                for v in values
                if isinstance(v, dict) and (v.get("value") or v.get("name"))
            ]
        except JenkinsClientError:
            return []

    async def trigger_build(self, job_name: str, parameters: dict | None = None) -> dict:
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        params = parameters or {}
        if params:
            resp = await self._request("POST", f"{self._job_path(job_name)}/buildWithParameters", data=params)
        else:
            resp = await self._request("POST", f"{self._job_path(job_name)}/build")
        queue_url = resp.headers.get("Location") or resp.headers.get("location") or ""
        return {"queued": True, "queue_url": queue_url}

    async def get_build_status(self, job_name: str, build_number: int) -> dict:
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        if build_number <= 0:
            raise JenkinsClientError("build_number 必须大于 0")
        tree = (
            "id,number,displayName,url,result,building,duration,estimatedDuration,timestamp,"
            "queueId,description,fullDisplayName,actions[causes[shortDescription]]"
        )
        path = f"{self._job_path(job_name)}/{build_number}/api/json?tree={tree}"
        return await self._get_json(path)

    async def get_build_log(self, job_name: str, build_number: int, *, tail_lines: int = 200) -> dict:
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        if build_number <= 0:
            raise JenkinsClientError("build_number 必须大于 0")
        resp = await self._request("GET", f"{self._job_path(job_name)}/{build_number}/consoleText")
        text = resp.text or ""
        lines = text.splitlines()
        if tail_lines > 0 and len(lines) > tail_lines:
            lines = lines[-tail_lines:]
            truncated = True
        else:
            truncated = False
        return {
            "log": "\n".join(lines),
            "line_count": len(text.splitlines()),
            "tail_lines": tail_lines,
            "truncated": truncated,
        }

    async def get_job_config(self, job_name: str) -> str:
        """Fetch raw config.xml for the given job."""
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        resp = await self._request("GET", f"{self._job_path(job_name)}/config.xml")
        return resp.text or ""

    async def create_job(self, job_name: str, config_xml: str, *, folder: str = "") -> dict:
        """Create a new job under *folder* (or root) with the given XML config."""
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        if not config_xml:
            raise JenkinsClientError("config_xml 不能为空")

        base = self._job_path(folder) if folder else ""
        await self._ensure_crumb()
        headers: dict[str, str] = {"Content-Type": "application/xml"}
        if self._crumb_field and self._crumb_value:
            headers[self._crumb_field] = self._crumb_value

        url = f"{self._base_url}{base}/createItem?name={quote(job_name, safe='')}"
        try:
            resp = await self._client.post(url, content=config_xml.encode("utf-8"), headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = e.response.text.strip()[:300]
            raise JenkinsClientError(
                f"创建 Job 失败: {e.response.status_code} {detail}"
            ) from e
        except Exception as e:
            raise JenkinsClientError(f"创建 Job 异常: {e}") from e

        return {"created": True, "name": job_name, "folder": folder}

    async def update_job_config(self, job_name: str, config_xml: str) -> dict:
        """Overwrite config.xml for an existing job."""
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        if not config_xml:
            raise JenkinsClientError("config_xml 不能为空")

        await self._ensure_crumb()
        headers: dict[str, str] = {"Content-Type": "application/xml"}
        if self._crumb_field and self._crumb_value:
            headers[self._crumb_field] = self._crumb_value

        url = f"{self._base_url}{self._job_path(job_name)}/config.xml"
        try:
            resp = await self._client.post(url, content=config_xml.encode("utf-8"), headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = e.response.text.strip()[:300]
            raise JenkinsClientError(
                f"更新 Job 配置失败: {e.response.status_code} {detail}"
            ) from e
        except Exception as e:
            raise JenkinsClientError(f"更新 Job 配置异常: {e}") from e

        return {"updated": True, "name": job_name}

    async def delete_job(self, job_name: str) -> dict:
        """Delete a job."""
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        await self._request("POST", f"{self._job_path(job_name)}/doDelete")
        return {"deleted": True, "name": job_name}

    async def copy_job(self, src_name: str, new_name: str, *, folder: str = "") -> dict:
        """Copy an existing job to *new_name* under *folder* (or root)."""
        if not src_name:
            raise JenkinsClientError("src_name 不能为空")
        if not new_name:
            raise JenkinsClientError("new_name 不能为空")

        base = self._job_path(folder) if folder else ""
        await self._ensure_crumb()
        headers: dict[str, str] = {"Content-Type": "application/x-www-form-urlencoded"}
        if self._crumb_field and self._crumb_value:
            headers[self._crumb_field] = self._crumb_value

        safe_new = quote(new_name, safe="")
        safe_src = quote(src_name, safe="")
        url = f"{self._base_url}{base}/createItem?name={safe_new}&mode=copy&from={safe_src}"
        try:
            resp = await self._client.post(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = e.response.text.strip()[:300]
            raise JenkinsClientError(
                f"复制 Job 失败: {e.response.status_code} {detail}"
            ) from e
        except Exception as e:
            raise JenkinsClientError(f"复制 Job 异常: {e}") from e

        return {"copied": True, "src": src_name, "name": new_name, "folder": folder}

    async def enable_job(self, job_name: str) -> dict:
        """Enable a disabled job."""
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        await self._request("POST", f"{self._job_path(job_name)}/enable")
        return {"enabled": True, "name": job_name}

    async def disable_job(self, job_name: str) -> dict:
        """Disable a job."""
        if not job_name:
            raise JenkinsClientError("job_name 不能为空")
        await self._request("POST", f"{self._job_path(job_name)}/disable")
        return {"disabled": True, "name": job_name}

    async def get_queue_info(self) -> dict:
        tree = "items[id,task[name,url],why,inQueueSince,stuck,blocked,buildable,params,url]"
        return await self._get_json(f"/queue/api/json?tree={tree}")

    async def _ensure_crumb(self) -> None:
        if self._crumb_field and self._crumb_value:
            return
        if not self._username:
            return

        try:
            data = await self._get_json("/crumbIssuer/api/json")
            self._crumb_field = data.get("crumbRequestField", "")
            self._crumb_value = data.get("crumb", "")
        except JenkinsClientError:
            # Jenkins may disable CSRF or crumb endpoint.
            self._crumb_field = ""
            self._crumb_value = ""

    async def _get_json(self, path: str) -> dict:
        resp = await self._request("GET", path)
        try:
            data = resp.json()
        except Exception as e:
            raise JenkinsClientError(f"Jenkins 返回非 JSON 响应: {e}") from e
        if not isinstance(data, dict):
            raise JenkinsClientError("Jenkins JSON 响应格式异常")
        return data

    async def _request(
        self, method: str, path: str, *, params: dict | None = None, data: dict | None = None
    ) -> httpx.Response:
        if not self._base_url:
            raise JenkinsClientError("Jenkins URL 未配置")

        url = f"{self._base_url}{path}" if path.startswith("/") else f"{self._base_url}/{path}"
        headers: dict[str, str] = {}
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            await self._ensure_crumb()
            if self._crumb_field and self._crumb_value:
                headers[self._crumb_field] = self._crumb_value

        try:
            resp = await self._client.request(method, url, params=params, data=data, headers=headers)
            # With CSRF enabled and no valid crumb, Jenkins usually returns 403.
            if resp.status_code == 403 and method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                self._crumb_field = ""
                self._crumb_value = ""
                await self._ensure_crumb()
                if self._crumb_field and self._crumb_value:
                    headers[self._crumb_field] = self._crumb_value
                    resp = await self._client.request(method, url, params=params, data=data, headers=headers)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            detail = e.response.text.strip()[:300]
            raise JenkinsClientError(
                f"Jenkins 请求失败: {e.response.status_code} {e.request.method} {e.request.url} {detail}"
            ) from e
        except Exception as e:
            raise JenkinsClientError(f"Jenkins 请求异常: {e}") from e

    @staticmethod
    def _job_path(name: str, *, is_view: bool = False) -> str:
        """Convert nested name to Jenkins path: folder/job/sub."""
        parts = [p for p in name.strip("/").split("/") if p]
        if not parts:
            raise JenkinsClientError("名称不能为空")
        key = "view" if is_view else "job"
        return "".join(f"/{key}/{quote(p, safe='')}" for p in parts)

    @staticmethod
    def _is_folder(item: dict) -> bool:
        cls = str(item.get("_class", "") or "").lower()
        # Common Jenkins folder classes:
        # - com.cloudbees.hudson.plugins.folder.Folder
        # - org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject
        return ("folder" in cls) or ("multibranch" in cls)
