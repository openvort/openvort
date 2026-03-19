"""
飞书事件回调加解密

飞书 Encrypt Key 模式使用 AES-256-CBC，密钥为 encrypt_key 的 SHA256 摘要。
"""

from __future__ import annotations

import base64
import hashlib
import json

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class FeishuCrypto:
    """飞书事件加解密工具。"""

    def __init__(self, encrypt_key: str):
        self._encrypt_key = encrypt_key
        self._key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()

    def decrypt(self, encrypted: str) -> dict:
        """解密回调中的 encrypt 字段。"""
        ciphertext = base64.b64decode(encrypted)
        if len(ciphertext) < 16:
            raise ValueError("ciphertext too short")

        iv = ciphertext[:16]
        payload = ciphertext[16:]
        if len(payload) % 16 != 0:
            raise ValueError("ciphertext is not a multiple of block size")

        cipher = Cipher(algorithms.AES(self._key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(payload) + decryptor.finalize()
        text = self._extract_json_text(plaintext)
        return json.loads(text)

    @staticmethod
    def verify_token(body: dict, verification_token: str) -> bool:
        """校验回调 token。"""
        if not verification_token:
            return True

        if body.get("type") == "url_verification":
            return body.get("token", "") == verification_token

        header = body.get("header", {})
        if header:
            return header.get("token", "") == verification_token

        return body.get("token", "") == verification_token

    @staticmethod
    def _extract_json_text(plaintext: bytes) -> str:
        """优先做 PKCS7 去填充，失败时回退到提取 JSON 片段。"""
        if plaintext:
            pad = plaintext[-1]
            if 0 < pad <= 16 and plaintext.endswith(bytes([pad]) * pad):
                try:
                    return plaintext[:-pad].decode("utf-8")
                except UnicodeDecodeError:
                    pass

        left = plaintext.find(b"{")
        right = plaintext.rfind(b"}")
        if left == -1 or right == -1 or right < left:
            raise ValueError("unable to locate json payload")
        return plaintext[left:right + 1].decode("utf-8")
