"""VortCert FastAPI sub-router — domain, DNS provider, certificate CRUD + check."""

import io
import uuid
import zipfile
from datetime import datetime, timezone

def _utcnow() -> datetime:
    """UTC now without tzinfo, compatible with TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _strip_tz(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func, delete as sa_delete

from openvort.db.engine import get_session_factory
from openvort.plugins.vortcert.crypto import decrypt_value, encrypt_value
from openvort.plugins.vortcert.models import (
    CertCertificate, CertCheckLog, CertDeployLog, CertDeployTarget, CertDnsProvider, CertDomain,
)
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortcert.router")

router = APIRouter(prefix="/api/cert", tags=["vortcert"])


# ============ Schemas ============

class DnsProviderCreate(BaseModel):
    name: str
    provider_type: str
    api_key: str = ""
    api_secret: str = ""
    extra_config: str = "{}"


class DnsProviderUpdate(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    extra_config: str | None = None


class DomainCreate(BaseModel):
    domain: str
    domain_type: str = "single"
    label: str = ""
    note: str = ""
    dns_provider_id: str | None = None
    responsible_member_id: str | None = None


class DomainUpdate(BaseModel):
    domain: str | None = None
    domain_type: str | None = None
    label: str | None = None
    note: str | None = None
    dns_provider_id: str | None = None
    responsible_member_id: str | None = None


class DomainImport(BaseModel):
    domains: list[str]
    label: str = ""
    dns_provider_id: str | None = None


class CertIssueRequest(BaseModel):
    domain_id: str
    wildcard: bool = False


class DeployTargetCreate(BaseModel):
    name: str
    target_type: str  # aliyun_cdn / baota
    config: str = "{}"  # JSON
    api_key: str = ""  # baota panel API key
    dns_provider_id: str | None = None


class DeployTargetUpdate(BaseModel):
    name: str | None = None
    target_type: str | None = None
    config: str | None = None
    api_key: str | None = None
    dns_provider_id: str | None = None


class DeployRequest(BaseModel):
    certificate_id: str
    target_ids: list[str]


# ============ Helpers ============

def _mask_value(encrypted: str) -> str:
    """Decrypt and mask a value, showing first 2 and last 4 chars."""
    if not encrypted:
        return ""
    try:
        plain = decrypt_value(encrypted)
        if not plain or len(plain) <= 6:
            return "••••••••"
        return f"{plain[:2]}***{plain[-4:]}"
    except Exception:
        return "••••••••"


def _dns_provider_to_dict(p: CertDnsProvider) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "provider_type": p.provider_type,
        "has_key": bool(p.api_key),
        "has_secret": bool(p.api_secret),
        "api_key_masked": _mask_value(p.api_key),
        "api_secret_masked": _mask_value(p.api_secret),
        "extra_config": p.extra_config,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _domain_to_dict(d: CertDomain) -> dict:
    return {
        "id": d.id,
        "domain": d.domain,
        "domain_type": d.domain_type,
        "label": d.label,
        "note": d.note,
        "dns_provider_id": d.dns_provider_id,
        "responsible_member_id": d.responsible_member_id,
        "last_check_at": d.last_check_at.isoformat() if d.last_check_at else None,
        "last_check_status": d.last_check_status,
        "expires_at": d.expires_at.isoformat() if d.expires_at else None,
        "issuer": d.issuer,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def _cert_to_dict(c: CertCertificate) -> dict:
    return {
        "id": c.id,
        "domain_id": c.domain_id,
        "domain": c.domain,
        "cert_type": c.cert_type,
        "issued_by": c.issued_by,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "status": c.status,
        "issued_at": c.issued_at.isoformat() if c.issued_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _check_log_to_dict(l: CertCheckLog) -> dict:
    return {
        "id": l.id,
        "domain_id": l.domain_id,
        "domain": l.domain,
        "checked_at": l.checked_at.isoformat() if l.checked_at else None,
        "expires_at": l.expires_at.isoformat() if l.expires_at else None,
        "issuer": l.issuer,
        "status": l.status,
        "error_message": l.error_message,
        "serial_number": l.serial_number,
    }


# ============ Stats ============

@router.get("/stats")
async def get_stats():
    sf = get_session_factory()
    async with sf() as session:
        total = await session.scalar(select(func.count()).select_from(CertDomain)) or 0
        ok = await session.scalar(
            select(func.count()).where(CertDomain.last_check_status == "ok")
        ) or 0
        warning = await session.scalar(
            select(func.count()).where(CertDomain.last_check_status.in_(["warning", "critical"]))
        ) or 0
        expired = await session.scalar(
            select(func.count()).where(CertDomain.last_check_status == "expired")
        ) or 0
        error = await session.scalar(
            select(func.count()).where(CertDomain.last_check_status == "error")
        ) or 0
        unchecked = await session.scalar(
            select(func.count()).where(CertDomain.last_check_status == "")
        ) or 0

    return {
        "total": total,
        "ok": ok,
        "warning": warning,
        "expired": expired,
        "error": error,
        "unchecked": unchecked,
    }


# ============ DNS Provider CRUD ============

@router.get("/dns-providers")
async def list_dns_providers():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(CertDnsProvider).order_by(CertDnsProvider.created_at.desc())
        )
        return {"items": [_dns_provider_to_dict(p) for p in result.scalars().all()]}


@router.post("/dns-providers")
async def create_dns_provider(body: DnsProviderCreate):
    sf = get_session_factory()
    async with sf() as session:
        provider = CertDnsProvider(
            id=uuid.uuid4().hex,
            name=body.name,
            provider_type=body.provider_type,
            api_key=encrypt_value(body.api_key) if body.api_key else "",
            api_secret=encrypt_value(body.api_secret) if body.api_secret else "",
            extra_config=body.extra_config,
        )
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        return _dns_provider_to_dict(provider)


@router.put("/dns-providers/{provider_id}")
async def update_dns_provider(provider_id: str, body: DnsProviderUpdate):
    sf = get_session_factory()
    async with sf() as session:
        provider = await session.get(CertDnsProvider, provider_id)
        if not provider:
            raise HTTPException(404, "DNS provider not found")
        if body.name is not None:
            provider.name = body.name
        if body.provider_type is not None:
            provider.provider_type = body.provider_type
        if body.api_key is not None:
            provider.api_key = encrypt_value(body.api_key) if body.api_key else ""
        if body.api_secret is not None:
            provider.api_secret = encrypt_value(body.api_secret) if body.api_secret else ""
        if body.extra_config is not None:
            provider.extra_config = body.extra_config
        await session.commit()
        await session.refresh(provider)
        return _dns_provider_to_dict(provider)


@router.delete("/dns-providers/{provider_id}")
async def delete_dns_provider(provider_id: str):
    sf = get_session_factory()
    async with sf() as session:
        provider = await session.get(CertDnsProvider, provider_id)
        if not provider:
            raise HTTPException(404, "DNS provider not found")
        count = await session.scalar(
            select(func.count()).where(CertDomain.dns_provider_id == provider_id)
        )
        if count and count > 0:
            raise HTTPException(400, f"Cannot delete: {count} domains still reference this provider")
        await session.delete(provider)
        await session.commit()
        return {"ok": True}


# ============ Domain CRUD ============

@router.get("/domains")
async def list_domains(
    keyword: str = Query(""),
    label: str = Query(""),
    status: str = Query(""),
    dns_provider_id: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    sf = get_session_factory()
    async with sf() as session:
        q = select(CertDomain)
        if keyword:
            q = q.where(CertDomain.domain.contains(keyword) | CertDomain.note.contains(keyword))
        if label:
            q = q.where(CertDomain.label == label)
        if status:
            q = q.where(CertDomain.last_check_status == status)
        if dns_provider_id:
            q = q.where(CertDomain.dns_provider_id == dns_provider_id)

        total = await session.scalar(select(func.count()).select_from(q.subquery()))
        q = q.order_by(CertDomain.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        items = [_domain_to_dict(d) for d in result.scalars().all()]
        return {"items": items, "total": total or 0}


@router.post("/domains")
async def create_domain(body: DomainCreate):
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.scalar(select(CertDomain).where(CertDomain.domain == body.domain))
        if existing:
            raise HTTPException(400, f"Domain '{body.domain}' already exists")
        inferred_type = "wildcard" if body.domain.startswith("*.") else "single"
        domain = CertDomain(
            id=uuid.uuid4().hex,
            domain=body.domain,
            domain_type=inferred_type,
            label=body.label,
            note=body.note,
            dns_provider_id=body.dns_provider_id or None,
            responsible_member_id=body.responsible_member_id or None,
        )
        session.add(domain)
        await session.commit()
        await session.refresh(domain)
        return _domain_to_dict(domain)


@router.put("/domains/{domain_id}")
async def update_domain(domain_id: str, body: DomainUpdate):
    sf = get_session_factory()
    async with sf() as session:
        domain = await session.get(CertDomain, domain_id)
        if not domain:
            raise HTTPException(404, "Domain not found")
        if body.domain is not None:
            domain.domain = body.domain
        if body.domain_type is not None:
            domain.domain_type = body.domain_type
        if body.label is not None:
            domain.label = body.label
        if body.note is not None:
            domain.note = body.note
        if body.dns_provider_id is not None:
            domain.dns_provider_id = body.dns_provider_id or None
        if body.responsible_member_id is not None:
            domain.responsible_member_id = body.responsible_member_id or None
        await session.commit()
        await session.refresh(domain)
        return _domain_to_dict(domain)


@router.delete("/domains/{domain_id}")
async def delete_domain(domain_id: str):
    sf = get_session_factory()
    async with sf() as session:
        domain = await session.get(CertDomain, domain_id)
        if not domain:
            raise HTTPException(404, "Domain not found")
        await session.execute(sa_delete(CertCheckLog).where(CertCheckLog.domain_id == domain_id))
        await session.execute(sa_delete(CertCertificate).where(CertCertificate.domain_id == domain_id))
        await session.delete(domain)
        await session.commit()
        return {"ok": True}


@router.post("/domains/import")
async def import_domains(body: DomainImport):
    sf = get_session_factory()
    imported = 0
    skipped = 0
    async with sf() as session:
        for d in body.domains:
            d = d.strip()
            if not d:
                continue
            existing = await session.scalar(select(CertDomain).where(CertDomain.domain == d))
            if existing:
                skipped += 1
                continue
            domain_type = "wildcard" if d.startswith("*.") else "single"
            domain = CertDomain(
                id=uuid.uuid4().hex,
                domain=d,
                domain_type=domain_type,
                label=body.label,
                dns_provider_id=body.dns_provider_id or None,
            )
            session.add(domain)
            imported += 1
        await session.commit()
    return {"imported": imported, "skipped": skipped}


# ============ Certificate check / probe ============

@router.post("/check")
async def check_all_domains():
    """Trigger a full certificate check for all domains (with alert notifications)."""
    from openvort.plugins.vortcert.plugin import VortCertPlugin
    from openvort.web.deps import get_registry

    registry = get_registry()
    plugin = registry.get_plugin("vortcert")
    if isinstance(plugin, VortCertPlugin):
        await plugin.run_patrol()
    else:
        raise HTTPException(500, "VortCert plugin not loaded")

    sf = get_session_factory()
    async with sf() as session:
        total = await session.scalar(select(func.count()).select_from(CertDomain)) or 0
        ok = await session.scalar(
            select(func.count()).where(CertDomain.last_check_status == "ok")
        ) or 0
        warning = await session.scalar(
            select(func.count()).where(CertDomain.last_check_status.in_(["warning", "critical"]))
        ) or 0
        expired = await session.scalar(
            select(func.count()).where(CertDomain.last_check_status == "expired")
        ) or 0

    return {
        "checked": total,
        "summary": {"ok": ok, "warning": warning, "expired": expired},
    }


@router.post("/check/{domain_id}")
async def check_single_domain(domain_id: str):
    """Check certificate for a single domain."""
    from openvort.plugins.vortcert.checker import check_domain_cert

    sf = get_session_factory()
    async with sf() as session:
        domain_obj = await session.get(CertDomain, domain_id)
        if not domain_obj:
            raise HTTPException(404, "Domain not found")
        domain_name = domain_obj.domain

    check_result = await check_domain_cert(domain_name)

    now = _utcnow()
    sf2 = get_session_factory()
    async with sf2() as session:
        domain_obj = await session.get(CertDomain, domain_id)
        if domain_obj:
            domain_obj.last_check_at = now
            domain_obj.last_check_status = check_result.status
            domain_obj.expires_at = _strip_tz(check_result.expires_at)
            domain_obj.issuer = check_result.issuer

        log_entry = CertCheckLog(
            id=uuid.uuid4().hex,
            domain_id=domain_id,
            domain=domain_name,
            checked_at=now,
            expires_at=_strip_tz(check_result.expires_at),
            issuer=check_result.issuer,
            status=check_result.status,
            error_message=check_result.error_message,
            serial_number=check_result.serial_number,
        )
        session.add(log_entry)
        await session.commit()

    return {
        "domain": domain_name,
        "status": check_result.status,
        "expires_at": check_result.expires_at.isoformat() if check_result.expires_at else None,
        "days_remaining": check_result.days_remaining,
        "issuer": check_result.issuer,
        "error_message": check_result.error_message,
    }


@router.get("/check-logs")
async def list_check_logs(
    domain_id: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        q = select(CertCheckLog)
        if domain_id:
            q = q.where(CertCheckLog.domain_id == domain_id)
        total = await session.scalar(select(func.count()).select_from(q.subquery()))
        q = q.order_by(CertCheckLog.checked_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        items = [_check_log_to_dict(l) for l in result.scalars().all()]
        return {"items": items, "total": total or 0}


# ============ Certificate issue / renew / download ============

@router.get("/certificates")
async def list_certificates(
    domain_id: str = Query(""),
    status: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        q = select(CertCertificate)
        if domain_id:
            q = q.where(CertCertificate.domain_id == domain_id)
        if status:
            q = q.where(CertCertificate.status == status)
        total = await session.scalar(select(func.count()).select_from(q.subquery()))
        q = q.order_by(CertCertificate.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        items = [_cert_to_dict(c) for c in result.scalars().all()]
        return {"items": items, "total": total or 0}


@router.get("/certificates/{cert_id}/detail")
async def get_certificate_detail(cert_id: str):
    """Get certificate detail including decrypted PEM content."""
    sf = get_session_factory()
    async with sf() as session:
        cert = await session.get(CertCertificate, cert_id)
        if not cert:
            raise HTTPException(404, "Certificate not found")

        result = _cert_to_dict(cert)
        result["cert_pem"] = decrypt_value(cert.cert_pem) if cert.cert_pem else ""
        result["key_pem"] = decrypt_value(cert.key_pem) if cert.key_pem else ""
        result["chain_pem"] = cert.chain_pem or ""
        return result


def _get_acme_email() -> str:
    """Read ACME email from plugin config."""
    try:
        from openvort.web.deps import get_registry
        registry = get_registry()
        plugin = registry.get_plugin("vortcert")
        if plugin:
            return plugin.get_current_config().get("acme_email", "")
    except Exception:
        pass
    return ""


@router.post("/certificates/issue")
async def issue_certificate(body: CertIssueRequest):
    """Issue a new certificate via acme.sh."""
    from openvort.plugins.vortcert.issuer import issue_certificate as _issue, read_cert_file

    sf = get_session_factory()
    async with sf() as session:
        domain_obj = await session.get(CertDomain, body.domain_id)
        if not domain_obj:
            raise HTTPException(404, "Domain not found")
        if not domain_obj.dns_provider_id:
            raise HTTPException(400, "Domain has no DNS provider configured")
        dns_provider = await session.get(CertDnsProvider, domain_obj.dns_provider_id)
        if not dns_provider:
            raise HTTPException(400, "DNS provider not found")

        api_key = decrypt_value(dns_provider.api_key)
        api_secret = decrypt_value(dns_provider.api_secret)
        domain_name = domain_obj.domain.lstrip("*.")

    acme_email = _get_acme_email()
    result = await _issue(
        domain=domain_name,
        provider_type=dns_provider.provider_type,
        api_key=api_key,
        api_secret=api_secret,
        wildcard=body.wildcard,
        email=acme_email,
    )

    if not result.ok:
        detail = result.message
        if result.stderr:
            detail += f"\n\n--- stderr ---\n{result.stderr[-2000:]}"
        if result.stdout:
            detail += f"\n\n--- stdout ---\n{result.stdout[-2000:]}"
        raise HTTPException(500, detail)

    cert_pem = read_cert_file(result.cert_path)
    key_pem = read_cert_file(result.key_path)
    chain_pem = read_cert_file(result.chain_path)

    # Parse expiry from the issued cert
    expires_at = None
    try:
        import ssl
        import tempfile
        if cert_pem:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(cert_pem)
                f.flush()
                cert_info = ssl.PEM_cert_to_DER_cert(cert_pem)
    except Exception:
        pass

    now = _utcnow()
    sf2 = get_session_factory()
    async with sf2() as session:
        domain_obj = await session.get(CertDomain, body.domain_id)
        cert_record = CertCertificate(
            id=uuid.uuid4().hex,
            domain_id=body.domain_id,
            domain=domain_name if not body.wildcard else f"*.{domain_name}",
            cert_type="wildcard" if body.wildcard else "single",
            issued_by="letsencrypt",
            cert_pem=encrypt_value(cert_pem),
            key_pem=encrypt_value(key_pem),
            chain_pem=chain_pem,
            status="active",
            issued_at=now,
            expires_at=expires_at,
        )
        session.add(cert_record)
        await session.commit()
        await session.refresh(cert_record)
        return _cert_to_dict(cert_record)


@router.post("/certificates/{cert_id}/renew")
async def renew_certificate(cert_id: str):
    """Renew an existing certificate."""
    from openvort.plugins.vortcert.issuer import renew_certificate as _renew, read_cert_file

    sf = get_session_factory()
    async with sf() as session:
        cert = await session.get(CertCertificate, cert_id)
        if not cert:
            raise HTTPException(404, "Certificate not found")
        domain_name = cert.domain.lstrip("*.")

    result = await _renew(domain_name)
    if not result.ok:
        detail = result.message
        if result.stderr:
            detail += f"\n\n--- stderr ---\n{result.stderr[-2000:]}"
        if result.stdout:
            detail += f"\n\n--- stdout ---\n{result.stdout[-2000:]}"
        raise HTTPException(500, detail)

    cert_pem = read_cert_file(result.cert_path)
    key_pem = read_cert_file(result.key_path)
    chain_pem = read_cert_file(result.chain_path)

    now = _utcnow()
    sf2 = get_session_factory()
    async with sf2() as session:
        cert = await session.get(CertCertificate, cert_id)
        if cert:
            cert.cert_pem = encrypt_value(cert_pem)
            cert.key_pem = encrypt_value(key_pem)
            cert.chain_pem = chain_pem
            cert.issued_at = now
            cert.status = "active"
            await session.commit()
            await session.refresh(cert)
            return _cert_to_dict(cert)

    raise HTTPException(404, "Certificate not found after renewal")


@router.delete("/certificates/{cert_id}")
async def delete_certificate(cert_id: str):
    """Delete a certificate record."""
    sf = get_session_factory()
    async with sf() as session:
        cert = await session.get(CertCertificate, cert_id)
        if not cert:
            raise HTTPException(404, "Certificate not found")
        await session.execute(
            sa_delete(CertDeployLog).where(CertDeployLog.certificate_id == cert_id)
        )
        await session.delete(cert)
        await session.commit()
        return {"ok": True}


@router.get("/certificates/{cert_id}/download")
async def download_certificate(cert_id: str):
    """Download certificate files as a zip archive."""
    sf = get_session_factory()
    async with sf() as session:
        cert = await session.get(CertCertificate, cert_id)
        if not cert:
            raise HTTPException(404, "Certificate not found")

        cert_pem = decrypt_value(cert.cert_pem)
        key_pem = decrypt_value(cert.key_pem)
        chain_pem = cert.chain_pem or ""
        domain = cert.domain

    if not cert_pem:
        raise HTTPException(400, "No certificate data available")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        safe_name = domain.replace("*.", "wildcard.")
        if cert_pem:
            zf.writestr(f"{safe_name}.crt", cert_pem)
        if key_pem:
            zf.writestr(f"{safe_name}.key", key_pem)
        if chain_pem:
            zf.writestr(f"{safe_name}.chain.crt", chain_pem)
        if cert_pem and chain_pem:
            zf.writestr(f"{safe_name}.fullchain.crt", cert_pem + "\n" + chain_pem)
    buf.seek(0)

    filename = domain.replace("*.", "wildcard.") + "-cert.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============ Deploy Target CRUD ============

def _deploy_target_to_dict(t: CertDeployTarget) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "target_type": t.target_type,
        "config": t.config,
        "has_api_key": bool(t.api_key),
        "api_key_masked": _mask_value(t.api_key),
        "dns_provider_id": t.dns_provider_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _deploy_log_to_dict(l: CertDeployLog) -> dict:
    return {
        "id": l.id,
        "certificate_id": l.certificate_id,
        "deploy_target_id": l.deploy_target_id,
        "target_name": l.target_name,
        "domain": l.domain,
        "status": l.status,
        "error_message": l.error_message,
        "deployed_at": l.deployed_at.isoformat() if l.deployed_at else None,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


@router.get("/deploy-targets")
async def list_deploy_targets():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(CertDeployTarget).order_by(CertDeployTarget.created_at.desc())
        )
        return {"items": [_deploy_target_to_dict(t) for t in result.scalars().all()]}


@router.post("/deploy-targets")
async def create_deploy_target(body: DeployTargetCreate):
    sf = get_session_factory()
    async with sf() as session:
        target = CertDeployTarget(
            id=uuid.uuid4().hex,
            name=body.name,
            target_type=body.target_type,
            config=body.config,
            api_key=encrypt_value(body.api_key) if body.api_key else "",
            dns_provider_id=body.dns_provider_id or None,
        )
        session.add(target)
        await session.commit()
        await session.refresh(target)
        return _deploy_target_to_dict(target)


@router.put("/deploy-targets/{target_id}")
async def update_deploy_target(target_id: str, body: DeployTargetUpdate):
    sf = get_session_factory()
    async with sf() as session:
        target = await session.get(CertDeployTarget, target_id)
        if not target:
            raise HTTPException(404, "Deploy target not found")
        if body.name is not None:
            target.name = body.name
        if body.target_type is not None:
            target.target_type = body.target_type
        if body.config is not None:
            target.config = body.config
        if body.api_key is not None:
            target.api_key = encrypt_value(body.api_key) if body.api_key else ""
        if body.dns_provider_id is not None:
            target.dns_provider_id = body.dns_provider_id or None
        await session.commit()
        await session.refresh(target)
        return _deploy_target_to_dict(target)


@router.delete("/deploy-targets/{target_id}")
async def delete_deploy_target(target_id: str):
    sf = get_session_factory()
    async with sf() as session:
        target = await session.get(CertDeployTarget, target_id)
        if not target:
            raise HTTPException(404, "Deploy target not found")
        await session.execute(
            sa_delete(CertDeployLog).where(CertDeployLog.deploy_target_id == target_id)
        )
        await session.delete(target)
        await session.commit()
        return {"ok": True}


# ============ Deploy action ============

@router.post("/deploy")
async def deploy_certificate_to_targets(body: DeployRequest):
    """Deploy a certificate to one or more targets."""
    import json as _json

    from openvort.plugins.vortcert.deployer import deploy_certificate as _deploy

    sf = get_session_factory()
    async with sf() as session:
        cert = await session.get(CertCertificate, body.certificate_id)
        if not cert:
            raise HTTPException(404, "Certificate not found")
        cert_pem = decrypt_value(cert.cert_pem)
        key_pem = decrypt_value(cert.key_pem)
        chain_pem = cert.chain_pem or ""
        cert_domain = cert.domain
        if not cert_pem or not key_pem:
            raise HTTPException(400, "Certificate has no PEM content")

    fullchain_pem = (cert_pem + "\n" + chain_pem).strip() if chain_pem else cert_pem

    results = []
    for tid in body.target_ids:
        async with sf() as session:
            target = await session.get(CertDeployTarget, tid)
            if not target:
                results.append({"target_id": tid, "ok": False, "message": "Target not found"})
                continue

            config = _json.loads(target.config) if target.config else {}
            target_api_key = decrypt_value(target.api_key) if target.api_key else ""

            dns_api_key = ""
            dns_api_secret = ""
            if target.dns_provider_id:
                provider = await session.get(CertDnsProvider, target.dns_provider_id)
                if provider:
                    dns_api_key = decrypt_value(provider.api_key)
                    dns_api_secret = decrypt_value(provider.api_secret)

            target_name = target.name
            target_type = target.target_type

        deploy_result = await _deploy(
            target_type=target_type,
            config=config,
            cert_pem=fullchain_pem,
            key_pem=key_pem,
            api_key=dns_api_key,
            api_secret=dns_api_secret,
            target_api_key=target_api_key,
        )

        now = _utcnow()
        async with sf() as session:
            log_entry = CertDeployLog(
                id=uuid.uuid4().hex,
                certificate_id=body.certificate_id,
                deploy_target_id=tid,
                target_name=target_name,
                domain=cert_domain,
                status="success" if deploy_result.ok else "failed",
                error_message="" if deploy_result.ok else deploy_result.message,
                deployed_at=now if deploy_result.ok else None,
            )
            session.add(log_entry)
            await session.commit()

        results.append({
            "target_id": tid,
            "target_name": target_name,
            "ok": deploy_result.ok,
            "message": deploy_result.message,
        })

    return {"results": results}


@router.get("/deploy-logs")
async def list_deploy_logs(
    certificate_id: str = Query(""),
    deploy_target_id: str = Query(""),
    domain: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        q = select(CertDeployLog)
        if certificate_id:
            q = q.where(CertDeployLog.certificate_id == certificate_id)
        if deploy_target_id:
            q = q.where(CertDeployLog.deploy_target_id == deploy_target_id)
        if domain:
            q = q.where(CertDeployLog.domain.contains(domain))
        total = await session.scalar(select(func.count()).select_from(q.subquery()))
        q = q.order_by(CertDeployLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        items = [_deploy_log_to_dict(l) for l in result.scalars().all()]
        return {"items": items, "total": total or 0}
