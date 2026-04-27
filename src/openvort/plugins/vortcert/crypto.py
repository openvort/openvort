"""Fernet symmetric encryption for DNS API keys and certificate private keys."""

from cryptography.fernet import Fernet

_fernet: Fernet | None = None
_key: bytes | None = None


def _ensure_key() -> bytes:
    global _key
    if _key is not None:
        return _key

    from openvort.config.settings import get_settings

    key_file = get_settings().data_dir / "vortcert_key"
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


def encrypt_value(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
