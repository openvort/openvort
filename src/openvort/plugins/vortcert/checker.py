"""SSL certificate probe — check domain certificate via openssl s_client."""

import asyncio
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone

from openvort.utils.logging import get_logger

log = get_logger("plugins.vortcert.checker")


@dataclass
class CertCheckResult:
    domain: str
    status: str  # ok / warning / critical / expired / error
    expires_at: datetime | None = None
    issuer: str = ""
    serial_number: str = ""
    error_message: str = ""
    days_remaining: int | None = None


def _classify_status(days: int) -> str:
    if days < 0:
        return "expired"
    if days <= 7:
        return "critical"
    if days <= 14:
        return "warning"
    if days <= 30:
        return "warning"
    return "ok"


async def check_domain_cert(domain: str, port: int = 443, timeout: float = 10.0) -> CertCheckResult:
    """Probe a domain's SSL certificate and return structured result."""
    clean_domain = domain.lstrip("*.")

    try:
        cert_info = await asyncio.wait_for(
            _fetch_cert_info(clean_domain, port),
            timeout=timeout,
        )
        return cert_info
    except asyncio.TimeoutError:
        return CertCheckResult(
            domain=domain, status="error",
            error_message=f"Connection timed out after {timeout}s",
        )
    except Exception as e:
        return CertCheckResult(
            domain=domain, status="error",
            error_message=str(e),
        )


async def _fetch_cert_info(hostname: str, port: int) -> CertCheckResult:
    """Use Python ssl module to fetch certificate info (non-blocking via thread)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_cert_sync, hostname, port)


def _fetch_cert_sync(hostname: str, port: int) -> CertCheckResult:
    ctx = ssl.create_default_context()
    with ssl.create_connection((hostname, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()

    if not cert:
        return CertCheckResult(domain=hostname, status="error", error_message="No certificate returned")

    not_after_str = cert.get("notAfter", "")
    expires_at = None
    days_remaining = None
    if not_after_str:
        expires_at = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        delta = expires_at - datetime.now(timezone.utc)
        days_remaining = delta.days

    issuer_tuples = cert.get("issuer", ())
    issuer_parts = []
    for rdn in issuer_tuples:
        for attr_type, attr_value in rdn:
            if attr_type in ("organizationName", "commonName"):
                issuer_parts.append(attr_value)
    issuer = " / ".join(issuer_parts) if issuer_parts else ""

    serial = cert.get("serialNumber", "")

    status = _classify_status(days_remaining) if days_remaining is not None else "error"

    return CertCheckResult(
        domain=hostname,
        status=status,
        expires_at=expires_at,
        issuer=issuer,
        serial_number=serial,
        days_remaining=days_remaining,
    )


async def batch_check_domains(domains: list[dict], concurrency: int = 10) -> list[CertCheckResult]:
    """Check multiple domains concurrently. Each item: {"domain": "...", "port": 443}."""
    sem = asyncio.Semaphore(concurrency)

    async def _check(item: dict) -> CertCheckResult:
        async with sem:
            return await check_domain_cert(
                item["domain"], port=item.get("port", 443),
            )

    tasks = [_check(d) for d in domains]
    return await asyncio.gather(*tasks)
