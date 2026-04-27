"""acme.sh wrapper — issue and renew Let's Encrypt certificates."""

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path

from openvort.utils.logging import get_logger

log = get_logger("plugins.vortcert.issuer")

DNS_PROVIDER_MAP = {
    "aliyun": "dns_ali",
    "tencent": "dns_dp",
    "cloudflare": "dns_cf",
    "namesilo": "dns_namesilo",
    "godaddy": "dns_gd",
    "namecheap": "dns_namecheap",
    "aws": "dns_aws",
    "azure": "dns_azure",
    "gcore": "dns_gcore",
    "hetzner": "dns_hetzner",
    "linode": "dns_linode",
    "vultr": "dns_vultr",
}

ENV_KEY_MAP = {
    "aliyun": {"api_key": "Ali_Key", "api_secret": "Ali_Secret"},
    "tencent": {"api_key": "DP_Id", "api_secret": "DP_Key"},
    "cloudflare": {"api_key": "CF_Key", "api_secret": "CF_Email"},
    "namesilo": {"api_key": "Namesilo_Key"},
    "godaddy": {"api_key": "GD_Key", "api_secret": "GD_Secret"},
    "namecheap": {"api_key": "NAMECHEAP_API_KEY", "api_secret": "NAMECHEAP_USERNAME"},
    "aws": {"api_key": "AWS_ACCESS_KEY_ID", "api_secret": "AWS_SECRET_ACCESS_KEY"},
}


@dataclass
class IssueResult:
    ok: bool
    domain: str
    cert_path: str = ""
    key_path: str = ""
    chain_path: str = ""
    fullchain_path: str = ""
    message: str = ""
    stdout: str = ""
    stderr: str = ""


def _get_acme_path() -> str | None:
    acme = shutil.which("acme.sh")
    if acme:
        return acme
    home_acme = Path.home() / ".acme.sh" / "acme.sh"
    if home_acme.exists():
        return str(home_acme)
    return None


async def _auto_install_acme(email: str) -> tuple[bool, str]:
    """Auto-install acme.sh if not present. Returns (ok, message)."""
    if _get_acme_path():
        return True, "acme.sh already installed"

    if not email:
        return False, "ACME email not configured. Go to Admin -> Plugins -> VortCert to set it."

    log.info("acme.sh not found, auto-installing...")

    import os
    env = dict(os.environ)
    home = env.get("HOME", str(Path.home()))
    env.setdefault("HOME", home)

    install_cmd = (
        "cd /tmp"
        " && curl -fsSL -o acme_install.sh https://get.acme.sh"
        f" && bash acme_install.sh --force --email {email}"
        " && rm -f acme_install.sh"
    )

    proc = await asyncio.create_subprocess_shell(
        install_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    stdout_str = stdout.decode(errors="replace")
    stderr_str = stderr.decode(errors="replace")
    combined = f"{stdout_str}\n{stderr_str}".strip()

    if proc.returncode != 0:
        log.error("acme.sh auto-install failed (rc=%d): %s", proc.returncode, combined[-500:])
        return False, f"acme.sh auto-install failed:\n{combined[-500:]}"

    acme = _get_acme_path()
    if acme:
        log.info("acme.sh auto-installed successfully at %s", acme)
        return True, "acme.sh installed"

    log.error(
        "acme.sh install script exited 0 but binary not found. "
        "Likely the GitHub archive download failed. Output: %s",
        combined[-800:],
    )
    return False, (
        "acme.sh install script succeeded but binary not found at "
        f"{Path.home() / '.acme.sh' / 'acme.sh'}. "
        "This usually means the GitHub archive download failed (network issue). "
        "Please install acme.sh manually: "
        "curl -fsSL https://get.acme.sh | sh -s email=YOUR_EMAIL"
    )


def _find_cert_dir(domain: str, wildcard: bool = False) -> Path | None:
    """Locate the acme.sh cert directory, handling _ecc suffix and wildcard naming."""
    base = Path.home() / ".acme.sh"
    candidates = [
        domain,
        f"{domain}_ecc",
        f"*.{domain}",
        f"*.{domain}_ecc",
    ]
    for name in candidates:
        d = base / name
        if d.is_dir():
            return d
    return None


def _build_env(provider_type: str, api_key: str, api_secret: str) -> dict[str, str]:
    """Build environment variables for acme.sh DNS validation."""
    import os
    env = dict(os.environ)
    mapping = ENV_KEY_MAP.get(provider_type, {})
    if "api_key" in mapping and api_key:
        env[mapping["api_key"]] = api_key
    if "api_secret" in mapping and api_secret:
        env[mapping["api_secret"]] = api_secret
    return env


async def issue_certificate(
    domain: str,
    provider_type: str,
    api_key: str,
    api_secret: str,
    wildcard: bool = False,
    email: str = "",
) -> IssueResult:
    """Issue a certificate via acme.sh with DNS-01 validation."""
    acme = _get_acme_path()
    if not acme:
        ok, msg = await _auto_install_acme(email)
        if not ok:
            return IssueResult(ok=False, domain=domain, message=msg)
        acme = _get_acme_path()

    dns_plugin = DNS_PROVIDER_MAP.get(provider_type)
    if not dns_plugin:
        return IssueResult(
            ok=False, domain=domain,
            message=f"Unsupported DNS provider: {provider_type}. Supported: {', '.join(DNS_PROVIDER_MAP.keys())}",
        )

    cmd = [acme, "--issue", "--dns", dns_plugin]
    if wildcard:
        cmd.extend(["-d", domain, "-d", f"*.{domain}"])
    else:
        cmd.extend(["-d", domain])

    env = _build_env(provider_type, api_key, api_secret)

    log.info(f"Issuing certificate for {domain} via {dns_plugin}")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    stdout = stdout_bytes.decode(errors="replace")
    stderr = stderr_bytes.decode(errors="replace")

    if proc.returncode != 0:
        # returncode 2 means cert already issued and not due for renewal
        if proc.returncode == 2:
            log.info(f"Certificate for {domain} already issued and valid")
        else:
            log.error(f"acme.sh failed (rc={proc.returncode}): {stderr}")
            return IssueResult(
                ok=False, domain=domain,
                message=f"acme.sh exited with code {proc.returncode}",
                stdout=stdout, stderr=stderr,
            )

    cert_dir = _find_cert_dir(domain, wildcard)
    if not cert_dir:
        return IssueResult(
            ok=False, domain=domain,
            message=f"Certificate files not found in ~/.acme.sh/ after issuing",
            stdout=stdout, stderr=stderr,
        )

    cert_path = cert_dir / f"{domain}.cer"
    key_path = cert_dir / f"{domain}.key"
    chain_path = cert_dir / "ca.cer"
    fullchain_path = cert_dir / "fullchain.cer"

    if not cert_path.exists():
        for f in cert_dir.iterdir():
            if f.suffix == ".cer" and "ca" not in f.name and "fullchain" not in f.name:
                cert_path = f
                break

    return IssueResult(
        ok=True,
        domain=domain,
        cert_path=str(cert_path) if cert_path.exists() else "",
        key_path=str(key_path) if key_path.exists() else "",
        chain_path=str(chain_path) if chain_path.exists() else "",
        fullchain_path=str(fullchain_path) if fullchain_path.exists() else "",
        message="Certificate issued successfully",
        stdout=stdout, stderr=stderr,
    )


async def renew_certificate(domain: str) -> IssueResult:
    """Renew an existing certificate via acme.sh."""
    acme = _get_acme_path()
    if not acme:
        return IssueResult(
            ok=False, domain=domain,
            message="acme.sh not found",
        )

    cmd = [acme, "--renew", "-d", domain, "--force"]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    stdout = stdout_bytes.decode(errors="replace")
    stderr = stderr_bytes.decode(errors="replace")

    if proc.returncode != 0:
        return IssueResult(
            ok=False, domain=domain,
            message=f"Renewal failed (rc={proc.returncode})",
            stdout=stdout, stderr=stderr,
        )

    cert_dir = _find_cert_dir(domain)
    if not cert_dir:
        return IssueResult(
            ok=False, domain=domain,
            message="Certificate files not found after renewal",
            stdout=stdout, stderr=stderr,
        )
    return IssueResult(
        ok=True,
        domain=domain,
        cert_path=str(cert_dir / f"{domain}.cer"),
        key_path=str(cert_dir / f"{domain}.key"),
        chain_path=str(cert_dir / "ca.cer"),
        fullchain_path=str(cert_dir / "fullchain.cer"),
        message="Certificate renewed successfully",
        stdout=stdout, stderr=stderr,
    )


def read_cert_file(path: str) -> str:
    """Read a certificate/key file and return its content."""
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")
