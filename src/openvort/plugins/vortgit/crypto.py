"""Token encryption/decryption using Fernet symmetric encryption."""

from cryptography.fernet import Fernet

_fernet: Fernet | None = None
_key: bytes | None = None


def _ensure_key() -> bytes:
    """Get or generate the encryption key, persisted in data_dir."""
    global _key
    if _key is not None:
        return _key

    from openvort.config.settings import get_settings
    from openvort.plugins.vortgit.config import VortGitSettings

    settings = VortGitSettings()
    if settings.encryption_key:
        _key = settings.encryption_key.encode()
        return _key

    key_file = get_settings().data_dir / "vortgit_key"
    if key_file.exists():
        _key = key_file.read_bytes().strip()
    else:
        _key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(_key)

    return _key


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_ensure_key())
    return _fernet


def encrypt_token(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
