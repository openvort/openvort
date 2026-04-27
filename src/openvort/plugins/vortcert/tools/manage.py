"""cert_manage — manage domains and DNS provider configurations."""

import json
import uuid

from sqlalchemy import select

from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool
from openvort.plugins.vortcert.crypto import encrypt_value
from openvort.plugins.vortcert.models import CertDnsProvider, CertDomain
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortcert.tools.manage")


class CertManageTool(BaseTool):
    name = "cert_manage"
    description = (
        "管理 SSL 证书的域名清单和 DNS 服务商配置。"
        "可添加/删除域名、配置 DNS 服务商（阿里云/腾讯云/Cloudflare 等）。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "操作类型：add_domain 添加域名，remove_domain 删除域名，"
                        "list_domains 列出域名，add_dns_provider 添加 DNS 服务商，"
                        "list_dns_providers 列出 DNS 服务商"
                    ),
                    "enum": ["add_domain", "remove_domain", "list_domains", "add_dns_provider", "list_dns_providers"],
                },
                "domain": {
                    "type": "string",
                    "description": "域名（add_domain/remove_domain 时使用）",
                },
                "label": {
                    "type": "string",
                    "description": "域名标签/分组（add_domain 时可选）",
                },
                "dns_provider_name": {
                    "type": "string",
                    "description": "DNS 服务商名称（add_dns_provider 时使用）",
                },
                "dns_provider_type": {
                    "type": "string",
                    "description": "DNS 服务商类型（add_dns_provider 时使用）",
                    "enum": ["aliyun", "tencent", "cloudflare", "namesilo", "godaddy", "namecheap", "aws"],
                },
                "api_key": {
                    "type": "string",
                    "description": "DNS 服务商 API Key",
                },
                "api_secret": {
                    "type": "string",
                    "description": "DNS 服务商 API Secret",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        action = params["action"]

        if action == "add_domain":
            return await self._add_domain(params)
        elif action == "remove_domain":
            return await self._remove_domain(params)
        elif action == "list_domains":
            return await self._list_domains()
        elif action == "add_dns_provider":
            return await self._add_dns_provider(params)
        elif action == "list_dns_providers":
            return await self._list_dns_providers()
        else:
            return json.dumps({"ok": False, "message": f"不支持的操作: {action}"}, ensure_ascii=False)

    async def _add_domain(self, params: dict) -> str:
        domain = params.get("domain", "").strip()
        if not domain:
            return json.dumps({"ok": False, "message": "请提供域名"}, ensure_ascii=False)

        label = params.get("label", "")
        domain_type = "wildcard" if domain.startswith("*.") else "single"

        sf = get_session_factory()
        async with sf() as session:
            existing = await session.scalar(select(CertDomain).where(CertDomain.domain == domain))
            if existing:
                return json.dumps({"ok": False, "message": f"域名 {domain} 已存在"}, ensure_ascii=False)

            domain_obj = CertDomain(
                id=uuid.uuid4().hex,
                domain=domain,
                domain_type=domain_type,
                label=label,
            )
            session.add(domain_obj)
            await session.commit()

        return json.dumps({"ok": True, "message": f"域名 {domain} 已添加"}, ensure_ascii=False)

    async def _remove_domain(self, params: dict) -> str:
        domain = params.get("domain", "").strip()
        if not domain:
            return json.dumps({"ok": False, "message": "请提供域名"}, ensure_ascii=False)

        sf = get_session_factory()
        async with sf() as session:
            domain_obj = await session.scalar(select(CertDomain).where(CertDomain.domain == domain))
            if not domain_obj:
                return json.dumps({"ok": False, "message": f"域名 {domain} 不存在"}, ensure_ascii=False)
            await session.delete(domain_obj)
            await session.commit()

        return json.dumps({"ok": True, "message": f"域名 {domain} 已删除"}, ensure_ascii=False)

    async def _list_domains(self) -> str:
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(select(CertDomain).order_by(CertDomain.domain))
            domains = result.scalars().all()

        items = [{"domain": d.domain, "label": d.label, "status": d.last_check_status or "unchecked"} for d in domains]
        return json.dumps({"ok": True, "count": len(items), "domains": items}, ensure_ascii=False)

    async def _add_dns_provider(self, params: dict) -> str:
        name = params.get("dns_provider_name", "").strip()
        ptype = params.get("dns_provider_type", "").strip()
        api_key = params.get("api_key", "")
        api_secret = params.get("api_secret", "")

        if not name or not ptype:
            return json.dumps({"ok": False, "message": "请提供 DNS 服务商名称和类型"}, ensure_ascii=False)

        sf = get_session_factory()
        async with sf() as session:
            provider = CertDnsProvider(
                id=uuid.uuid4().hex,
                name=name,
                provider_type=ptype,
                api_key=encrypt_value(api_key) if api_key else "",
                api_secret=encrypt_value(api_secret) if api_secret else "",
            )
            session.add(provider)
            await session.commit()

        return json.dumps({"ok": True, "message": f"DNS 服务商 {name} ({ptype}) 已添加"}, ensure_ascii=False)

    async def _list_dns_providers(self) -> str:
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(select(CertDnsProvider).order_by(CertDnsProvider.name))
            providers = result.scalars().all()

        items = [{"name": p.name, "type": p.provider_type, "has_key": bool(p.api_key)} for p in providers]
        return json.dumps({"ok": True, "count": len(items), "providers": items}, ensure_ascii=False)
