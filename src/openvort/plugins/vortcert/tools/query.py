"""cert_query — query certificate status and expiry warnings."""

import json
from datetime import datetime, timezone

from sqlalchemy import select

from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool
from openvort.plugins.vortcert.models import CertDomain
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortcert.tools.query")


class CertQueryTool(BaseTool):
    name = "cert_query"
    description = (
        "查询 SSL/TLS 证书状态。"
        "可列出所有域名证书状态，筛选即将过期或已过期的证书，或检查单个域名的证书信息。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：list 列出全部，expiring 列出即将过期（30天内），check 检查单个域名",
                    "enum": ["list", "expiring", "check"],
                },
                "domain": {
                    "type": "string",
                    "description": "要检查的域名（action=check 时必填）",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        action = params["action"]

        if action == "check":
            return await self._check_one(params.get("domain", ""))
        elif action == "expiring":
            return await self._list_expiring()
        else:
            return await self._list_all()

    async def _list_all(self) -> str:
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(
                select(CertDomain).order_by(CertDomain.expires_at.asc().nullsfirst())
            )
            domains = result.scalars().all()

        items = []
        for d in domains:
            days = None
            if d.expires_at:
                delta = d.expires_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
                days = delta.days
            items.append({
                "domain": d.domain,
                "status": d.last_check_status or "unchecked",
                "expires_at": d.expires_at.isoformat() if d.expires_at else None,
                "days_remaining": days,
                "issuer": d.issuer,
                "label": d.label,
            })

        return json.dumps({"ok": True, "count": len(items), "domains": items}, ensure_ascii=False)

    async def _list_expiring(self) -> str:
        from datetime import timedelta
        threshold = datetime.now(timezone.utc) + timedelta(days=30)

        sf = get_session_factory()
        async with sf() as session:
            q = select(CertDomain).where(
                CertDomain.expires_at.isnot(None),
                CertDomain.expires_at <= threshold,
            ).order_by(CertDomain.expires_at.asc())
            result = await session.execute(q)
            domains = result.scalars().all()

        items = []
        for d in domains:
            delta = d.expires_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
            items.append({
                "domain": d.domain,
                "status": d.last_check_status,
                "expires_at": d.expires_at.isoformat(),
                "days_remaining": delta.days,
                "issuer": d.issuer,
            })

        return json.dumps({"ok": True, "count": len(items), "domains": items}, ensure_ascii=False)

    async def _check_one(self, domain: str) -> str:
        if not domain:
            return json.dumps({"ok": False, "message": "请提供要检查的域名"}, ensure_ascii=False)

        from openvort.plugins.vortcert.checker import check_domain_cert
        result = await check_domain_cert(domain)

        return json.dumps({
            "ok": True,
            "domain": result.domain,
            "status": result.status,
            "expires_at": result.expires_at.isoformat() if result.expires_at else None,
            "days_remaining": result.days_remaining,
            "issuer": result.issuer,
            "error": result.error_message,
        }, ensure_ascii=False)
