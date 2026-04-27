"""VortCert ORM models — SSL/TLS certificate management."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class CertDnsProvider(Base):
    """DNS provider configuration for ACME DNS-01 validation."""

    __tablename__ = "cert_dns_providers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64))
    provider_type: Mapped[str] = mapped_column(String(32), index=True)  # aliyun/tencent/cloudflare/namesilo/...
    api_key: Mapped[str] = mapped_column(Text, default="")  # Fernet encrypted
    api_secret: Mapped[str] = mapped_column(Text, default="")  # Fernet encrypted
    extra_config: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CertDomain(Base):
    """Domain inventory for certificate monitoring."""

    __tablename__ = "cert_domains"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    domain: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    domain_type: Mapped[str] = mapped_column(String(16), default="single")  # single/wildcard
    label: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    dns_provider_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("cert_dns_providers.id"), nullable=True
    )
    responsible_member_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("members.id"), nullable=True
    )
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_check_status: Mapped[str] = mapped_column(String(16), default="")  # ok/warning/critical/expired/error
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    issuer: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CertCertificate(Base):
    """Issued certificate records (from Let's Encrypt or manual upload)."""

    __tablename__ = "cert_certificates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(32), ForeignKey("cert_domains.id"), index=True)
    domain: Mapped[str] = mapped_column(String(256))
    cert_type: Mapped[str] = mapped_column(String(16), default="single")  # single/wildcard
    issued_by: Mapped[str] = mapped_column(String(64), default="letsencrypt")  # letsencrypt/manual
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cert_pem: Mapped[str] = mapped_column(Text, default="")  # Fernet encrypted
    key_pem: Mapped[str] = mapped_column(Text, default="")  # Fernet encrypted
    chain_pem: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active/expired/revoked
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CertCheckLog(Base):
    """Certificate check / probe log entries."""

    __tablename__ = "cert_check_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(32), ForeignKey("cert_domains.id"), index=True)
    domain: Mapped[str] = mapped_column(String(256))
    checked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    issuer: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok/warning/critical/expired/error
    error_message: Mapped[str] = mapped_column(Text, default="")
    serial_number: Mapped[str] = mapped_column(String(128), default="")


class CertDeployTarget(Base):
    """Deployment target for pushing certificates to CDN / BaoTa / etc."""

    __tablename__ = "cert_deploy_targets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128))
    target_type: Mapped[str] = mapped_column(String(32), index=True)  # aliyun_cdn / baota
    config: Mapped[str] = mapped_column(Text, default="{}")  # non-secret JSON config
    api_key: Mapped[str] = mapped_column(Text, default="")  # Fernet encrypted (baota API key, etc.)
    dns_provider_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("cert_dns_providers.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CertDeployLog(Base):
    """Deployment history log entries."""

    __tablename__ = "cert_deploy_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    certificate_id: Mapped[str] = mapped_column(String(32), ForeignKey("cert_certificates.id"), index=True)
    deploy_target_id: Mapped[str] = mapped_column(String(32), ForeignKey("cert_deploy_targets.id"), index=True)
    target_name: Mapped[str] = mapped_column(String(128), default="")
    domain: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/success/failed
    error_message: Mapped[str] = mapped_column(Text, default="")
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
