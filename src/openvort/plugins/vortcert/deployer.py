"""Certificate deployer — push certs to Alibaba Cloud CDN, BaoTa panel, etc."""

import hashlib
import json
import time
from dataclasses import dataclass

import httpx

from openvort.utils.logging import get_logger

log = get_logger("plugins.vortcert.deployer")


@dataclass
class DeployResult:
    ok: bool
    target_name: str
    message: str = ""


# ============ Alibaba Cloud CDN ============


async def deploy_to_aliyun_cdn(
    *,
    cdn_domain: str,
    cert_pem: str,
    key_pem: str,
    access_key_id: str,
    access_key_secret: str,
    cert_name: str = "",
) -> DeployResult:
    """Deploy SSL certificate to Alibaba Cloud CDN via OpenAPI SDK."""
    try:
        from alibabacloud_cdn20180510.client import Client
        from alibabacloud_cdn20180510 import models as cdn_models
        from alibabacloud_tea_openapi import models as openapi_models
    except ImportError:
        return DeployResult(
            ok=False,
            target_name=cdn_domain,
            message="alibabacloud-cdn20180510 SDK not installed. Run: pip install alibabacloud-cdn20180510",
        )

    if not cert_name:
        cert_name = f"vortcert-{cdn_domain}-{int(time.time())}"

    try:
        config = openapi_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        )
        config.endpoint = "cdn.aliyuncs.com"
        client = Client(config)

        req = cdn_models.SetCdnDomainSSLCertificateRequest(
            domain_name=cdn_domain,
            cert_name=cert_name,
            cert_type="upload",
            sslprotocol="on",
            sslpub=cert_pem,
            sslpri=key_pem,
        )
        response = client.set_cdn_domain_sslcertificate(req)
        log.info("Deployed cert to Alibaba CDN %s, request_id=%s", cdn_domain, response.body.request_id)
        return DeployResult(ok=True, target_name=cdn_domain, message="Certificate deployed to Alibaba Cloud CDN")
    except Exception as exc:
        log.error("Alibaba CDN deploy failed for %s: %s", cdn_domain, exc)
        return DeployResult(ok=False, target_name=cdn_domain, message=str(exc))


# ============ BaoTa Panel ============


def _bt_auth_params(api_key: str) -> dict:
    """Generate BaoTa panel API authentication parameters."""
    now = str(int(time.time()))
    key_md5 = hashlib.md5(api_key.encode()).hexdigest()
    request_token = hashlib.md5((now + key_md5).encode()).hexdigest()
    return {"request_time": now, "request_token": request_token}


async def deploy_to_baota(
    *,
    panel_url: str,
    api_key: str,
    site_name: str,
    cert_pem: str,
    key_pem: str,
) -> DeployResult:
    """Deploy SSL certificate to a BaoTa panel site."""
    panel_url = panel_url.rstrip("/")
    url = f"{panel_url}/site?action=SetSSL"

    data = {
        "type": "1",
        "siteName": site_name,
        "key": key_pem,
        "csr": cert_pem,
    }
    data.update(_bt_auth_params(api_key))

    try:
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            result = resp.json()

        if result.get("status"):
            log.info("Deployed cert to BaoTa site %s at %s", site_name, panel_url)
            return DeployResult(ok=True, target_name=site_name, message="Certificate deployed to BaoTa panel")
        else:
            msg = result.get("msg", "Unknown BaoTa API error")
            log.error("BaoTa deploy failed for %s: %s", site_name, msg)
            return DeployResult(ok=False, target_name=site_name, message=msg)
    except Exception as exc:
        log.error("BaoTa deploy failed for %s: %s", site_name, exc)
        return DeployResult(ok=False, target_name=site_name, message=str(exc))


# ============ Dispatcher ============


async def deploy_certificate(
    *,
    target_type: str,
    config: dict,
    cert_pem: str,
    key_pem: str,
    api_key: str = "",
    api_secret: str = "",
    target_api_key: str = "",
) -> DeployResult:
    """Dispatch deployment to the appropriate handler based on target_type.

    - api_key/api_secret: from the linked DNS provider (for aliyun_cdn)
    - target_api_key: from the deploy target itself (for baota)
    """
    if target_type == "aliyun_cdn":
        cdn_domain = config.get("cdn_domain", "")
        if not cdn_domain:
            return DeployResult(ok=False, target_name="", message="Missing cdn_domain in config")
        if not api_key or not api_secret:
            return DeployResult(ok=False, target_name=cdn_domain, message="Missing Alibaba Cloud API credentials")
        return await deploy_to_aliyun_cdn(
            cdn_domain=cdn_domain,
            cert_pem=cert_pem,
            key_pem=key_pem,
            access_key_id=api_key,
            access_key_secret=api_secret,
            cert_name=config.get("cert_name", ""),
        )

    elif target_type == "baota":
        panel_url = config.get("panel_url", "")
        site_name = config.get("site_name", "")
        if not panel_url or not site_name:
            return DeployResult(ok=False, target_name=site_name, message="Missing panel_url or site_name in config")
        if not target_api_key:
            return DeployResult(ok=False, target_name=site_name, message="Missing BaoTa API key")
        return await deploy_to_baota(
            panel_url=panel_url,
            api_key=target_api_key,
            site_name=site_name,
            cert_pem=cert_pem,
            key_pem=key_pem,
        )

    else:
        return DeployResult(ok=False, target_name="", message=f"Unsupported target type: {target_type}")
