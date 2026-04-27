"""cert_issue — issue or renew SSL certificates via acme.sh."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool
from openvort.plugins.vortcert.crypto import decrypt_value, encrypt_value
from openvort.plugins.vortcert.models import CertCertificate, CertDnsProvider, CertDomain
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortcert.tools.issue")


class CertIssueTool(BaseTool):
    name = "cert_issue"
    description = (
        "签发或续期 SSL/TLS 证书（Let's Encrypt）。"
        "可为域名签发新证书或续期已有证书，需要域名已配置 DNS 服务商。"
    )

    @staticmethod
    def _get_acme_email() -> str:
        try:
            from openvort.web.deps import get_registry
            plugin = get_registry().get_plugin("vortcert")
            if plugin:
                return plugin.get_current_config().get("acme_email", "")
        except Exception:
            pass
        return ""

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：issue 签发新证书，renew 续期已有证书",
                    "enum": ["issue", "renew"],
                },
                "domain": {
                    "type": "string",
                    "description": "域名（如 example.com）",
                },
                "wildcard": {
                    "type": "boolean",
                    "description": "是否签发通配符证书（*.example.com）",
                    "default": False,
                },
            },
            "required": ["action", "domain"],
        }

    async def execute(self, params: dict) -> str:
        action = params["action"]
        domain = params.get("domain", "").strip()
        wildcard = params.get("wildcard", False)

        if not domain:
            return json.dumps({"ok": False, "message": "请提供域名"}, ensure_ascii=False)

        if action == "issue":
            return await self._issue(domain, wildcard)
        elif action == "renew":
            return await self._renew(domain)
        else:
            return json.dumps({"ok": False, "message": f"不支持的操作: {action}"}, ensure_ascii=False)

    async def _issue(self, domain: str, wildcard: bool) -> str:
        from openvort.plugins.vortcert.issuer import issue_certificate, read_cert_file

        clean_domain = domain.lstrip("*.")

        sf = get_session_factory()
        async with sf() as session:
            domain_obj = await session.scalar(
                select(CertDomain).where(CertDomain.domain.in_([clean_domain, f"*.{clean_domain}", domain]))
            )
            if not domain_obj:
                return json.dumps({"ok": False, "message": f"域名 {domain} 未在系统中注册，请先添加域名"}, ensure_ascii=False)
            if not domain_obj.dns_provider_id:
                return json.dumps({"ok": False, "message": f"域名 {domain} 未配置 DNS 服务商，无法签发证书"}, ensure_ascii=False)
            dns_provider = await session.get(CertDnsProvider, domain_obj.dns_provider_id)
            if not dns_provider:
                return json.dumps({"ok": False, "message": "DNS 服务商配置不存在"}, ensure_ascii=False)

            api_key = decrypt_value(dns_provider.api_key)
            api_secret = decrypt_value(dns_provider.api_secret)
            provider_type = dns_provider.provider_type
            domain_id = domain_obj.id

        acme_email = self._get_acme_email()
        result = await issue_certificate(
            domain=clean_domain,
            provider_type=provider_type,
            api_key=api_key,
            api_secret=api_secret,
            wildcard=wildcard,
            email=acme_email,
        )

        if not result.ok:
            return json.dumps({"ok": False, "message": result.message, "stderr": result.stderr[:500]}, ensure_ascii=False)

        cert_pem = read_cert_file(result.cert_path)
        key_pem = read_cert_file(result.key_path)
        chain_pem = read_cert_file(result.chain_path)

        now = datetime.now(timezone.utc)
        sf2 = get_session_factory()
        async with sf2() as session:
            cert_record = CertCertificate(
                id=uuid.uuid4().hex,
                domain_id=domain_id,
                domain=f"*.{clean_domain}" if wildcard else clean_domain,
                cert_type="wildcard" if wildcard else "single",
                issued_by="letsencrypt",
                cert_pem=encrypt_value(cert_pem),
                key_pem=encrypt_value(key_pem),
                chain_pem=chain_pem,
                status="active",
                issued_at=now,
            )
            session.add(cert_record)
            await session.commit()

        return json.dumps({
            "ok": True,
            "message": f"证书签发成功: {'*.' + clean_domain if wildcard else clean_domain}",
            "domain": f"*.{clean_domain}" if wildcard else clean_domain,
            "cert_id": cert_record.id,
        }, ensure_ascii=False)

    async def _renew(self, domain: str) -> str:
        from openvort.plugins.vortcert.issuer import renew_certificate, read_cert_file

        clean_domain = domain.lstrip("*.")
        result = await renew_certificate(clean_domain)

        if not result.ok:
            return json.dumps({"ok": False, "message": result.message, "stderr": result.stderr[:500]}, ensure_ascii=False)

        cert_pem = read_cert_file(result.cert_path)
        key_pem = read_cert_file(result.key_path)
        chain_pem = read_cert_file(result.chain_path)

        sf = get_session_factory()
        async with sf() as session:
            cert = await session.scalar(
                select(CertCertificate)
                .where(CertCertificate.domain.in_([clean_domain, f"*.{clean_domain}"]))
                .order_by(CertCertificate.created_at.desc())
            )
            if cert:
                cert.cert_pem = encrypt_value(cert_pem)
                cert.key_pem = encrypt_value(key_pem)
                cert.chain_pem = chain_pem
                cert.issued_at = datetime.now(timezone.utc)
                cert.status = "active"
                await session.commit()

        return json.dumps({
            "ok": True,
            "message": f"证书续期成功: {clean_domain}",
            "domain": clean_domain,
        }, ensure_ascii=False)
