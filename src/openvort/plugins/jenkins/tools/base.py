"""
Common helpers for Jenkins tools.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from openvort.plugin.base import BaseTool
from openvort.plugins.jenkins.client import JenkinsClient, JenkinsClientError
from openvort.plugins.jenkins.config import JenkinsSettings
from openvort.utils.logging import get_logger

log = get_logger("plugins.jenkins.tools.base")


class JenkinsToolBase(BaseTool):
    """Base class to share client creation and error handling."""

    def __init__(self, settings: JenkinsSettings):
        self._settings = settings

    async def _run(self, fn: Callable[[JenkinsClient], Awaitable[dict[str, Any]]]) -> str:
        client = JenkinsClient(self._settings)
        try:
            if not client.is_configured():
                missing = ", ".join(client.missing_config_fields())
                return json.dumps(
                    {
                        "ok": False,
                        "message": f"Jenkins 插件未完成配置，请先在 /plugins 页面配置: {missing}",
                    },
                    ensure_ascii=False,
                )

            payload = await fn(client)
            if "ok" not in payload:
                payload["ok"] = True
            return json.dumps(payload, ensure_ascii=False, default=str)
        except JenkinsClientError as e:
            return json.dumps({"ok": False, "message": str(e)}, ensure_ascii=False)
        except Exception as e:
            log.exception(f"{self.name} 执行异常: {e}")
            return json.dumps({"ok": False, "message": f"工具执行失败: {e}"}, ensure_ascii=False)
        finally:
            await client.close()
