"""
企微消息加解密

实现企业微信回调消息的签名验证、AES 加解密。
参考：https://developer.work.weixin.qq.com/document/path/90968
"""

import base64
import hashlib
import random
import socket
import string
import struct
import time
import xml.etree.ElementTree as ET

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


class WeComCrypto:
    """企微消息加解密"""

    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        self.token = token
        self.corp_id = corp_id
        self.aes_key = base64.b64decode(encoding_aes_key + "=")

    def verify_signature(self, signature: str, timestamp: str, nonce: str, echostr: str = "") -> bool:
        """验证签名"""
        items = sorted([self.token, timestamp, nonce, echostr])
        sha1 = hashlib.sha1("".join(items).encode()).hexdigest()
        return sha1 == signature

    def decrypt(self, encrypted: str) -> str:
        """解密消息"""
        cipher_text = base64.b64decode(encrypted)
        iv = self.aes_key[:16]
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(cipher_text) + decryptor.finalize()

        # 去除 PKCS7 填充
        pad_len = decrypted[-1]
        content = decrypted[:-pad_len]

        # 解析：16字节随机串 + 4字节消息长度 + 消息体 + corp_id
        msg_len = struct.unpack("!I", content[16:20])[0]
        msg = content[20:20 + msg_len].decode("utf-8")
        from_corp_id = content[20 + msg_len:].decode("utf-8")

        if from_corp_id != self.corp_id:
            raise ValueError(f"corp_id 不匹配: {from_corp_id} != {self.corp_id}")

        return msg

    def encrypt(self, reply_msg: str) -> str:
        """加密消息"""
        # 16字节随机串 + 4字节消息长度 + 消息体 + corp_id
        msg_bytes = reply_msg.encode("utf-8")
        random_str = "".join(random.choices(string.ascii_letters + string.digits, k=16)).encode()
        content = random_str + struct.pack("!I", len(msg_bytes)) + msg_bytes + self.corp_id.encode()

        # PKCS7 填充
        block_size = 32
        pad_len = block_size - (len(content) % block_size)
        content += bytes([pad_len] * pad_len)

        # AES-CBC 加密
        iv = self.aes_key[:16]
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(content) + encryptor.finalize()

        return base64.b64encode(encrypted).decode()

    def generate_signature(self, encrypted: str, timestamp: str, nonce: str) -> str:
        """生成签名"""
        items = sorted([self.token, timestamp, nonce, encrypted])
        return hashlib.sha1("".join(items).encode()).hexdigest()

    def decrypt_callback(self, xml_text: str, msg_signature: str, timestamp: str, nonce: str) -> dict:
        """解密回调消息，返回解析后的 dict"""
        # 验签
        root = ET.fromstring(xml_text)
        encrypt_node = root.find("Encrypt")
        if encrypt_node is None:
            raise ValueError("XML 中缺少 Encrypt 节点")

        encrypted = encrypt_node.text
        if not self.verify_signature(msg_signature, timestamp, nonce, encrypted):
            raise ValueError("签名验证失败")

        # 解密
        decrypted_xml = self.decrypt(encrypted)
        msg_root = ET.fromstring(decrypted_xml)

        return {child.tag: child.text or "" for child in msg_root}

    def encrypt_reply(self, reply_xml: str) -> str:
        """加密回复消息，返回完整的加密 XML"""
        encrypted = self.encrypt(reply_xml)
        timestamp = str(int(time.time()))
        nonce = "".join(random.choices(string.digits, k=10))
        signature = self.generate_signature(encrypted, timestamp, nonce)

        return f"""<xml>
<Encrypt><![CDATA[{encrypted}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
