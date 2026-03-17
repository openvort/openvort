"""
DM 配对安全

对未知发送者实施配对码验证流程：
- pairing 模式：未知发送者收到配对码，管理员通过 CLI 批准后加入 allowlist
- allowlist 模式：仅 allowlist 中的用户可对话
- open 模式：所有人可对话（不推荐）
"""

from __future__ import annotations

import json
import random
import string
import time
from pathlib import Path

from openvort.utils.logging import get_logger

log = get_logger("core.pairing")

# 配对码有效期（秒）
PAIRING_CODE_TTL = 600  # 10 分钟


class PairingManager:
    """DM 配对管理器

    管理未知发送者的配对流程和 allowlist 持久化。
    """

    def __init__(self, dm_policy: str = "pairing", data_dir: Path | None = None):
        """
        Args:
            dm_policy: "pairing" | "allowlist" | "open"
            data_dir: 数据目录（存储 allowlist 和 pending codes）
        """
        self._policy = dm_policy
        self._data_dir = data_dir or (Path.home() / ".openvort")
        self._allowlist_file = self._data_dir / "dm_allowlist.json"
        self._allowlist: dict[str, dict] = {}  # {channel:user_id: {approved_at, approved_by}}
        self._pending: dict[str, dict] = {}  # {code: {channel, user_id, created_at}}
        self._load_allowlist()

    @property
    def policy(self) -> str:
        return self._policy

    def check_access(self, channel: str, user_id: str) -> tuple[bool, str]:
        """检查用户是否有权发送 DM

        Args:
            channel: 通道名
            user_id: 用户 ID

        Returns:
            (allowed, message) — allowed=True 表示放行，message 为拒绝时的回复
        """
        if self._policy == "open":
            return True, ""

        key = f"{channel}:{user_id}"

        if key in self._allowlist:
            return True, ""

        if self._policy == "allowlist":
            return False, "⚠️ 你没有权限与我对话。请联系管理员将你加入白名单。"

        # pairing 模式：生成配对码
        if self._policy == "pairing":
            code = self._get_or_create_code(channel, user_id)
            return False, (
                f"👋 你好！我还不认识你。\n"
                f"请将以下配对码发给管理员进行验证：\n\n"
                f"🔑 配对码: {code}\n\n"
                f"管理员运行: openvort pairing approve {code}\n"
                f"配对码 {PAIRING_CODE_TTL // 60} 分钟内有效。"
            )

        return False, ""

    def approve(self, code: str, approved_by: str = "cli") -> tuple[bool, str]:
        """批准配对码

        Args:
            code: 配对码
            approved_by: 批准人

        Returns:
            (success, message)
        """
        pending = self._pending.get(code)
        if not pending:
            return False, f"配对码 {code} 不存在或已过期"

        # 检查过期
        if time.time() - pending["created_at"] > PAIRING_CODE_TTL:
            del self._pending[code]
            return False, f"配对码 {code} 已过期"

        channel = pending["channel"]
        user_id = pending["user_id"]
        key = f"{channel}:{user_id}"

        self._allowlist[key] = {
            "channel": channel,
            "user_id": user_id,
            "approved_at": time.time(),
            "approved_by": approved_by,
        }
        del self._pending[code]
        self._save_allowlist()

        log.info(f"已批准配对: {key} (by {approved_by})")
        return True, f"已批准 {channel}:{user_id}"

    def reject(self, code: str) -> tuple[bool, str]:
        """拒绝配对码"""
        if code in self._pending:
            info = self._pending.pop(code)
            return True, f"已拒绝 {info['channel']}:{info['user_id']}"
        return False, f"配对码 {code} 不存在"

    def add_to_allowlist(self, channel: str, user_id: str, approved_by: str = "admin") -> None:
        """直接加入白名单"""
        key = f"{channel}:{user_id}"
        self._allowlist[key] = {
            "channel": channel,
            "user_id": user_id,
            "approved_at": time.time(),
            "approved_by": approved_by,
        }
        self._save_allowlist()

    def remove_from_allowlist(self, channel: str, user_id: str) -> bool:
        """从白名单移除"""
        key = f"{channel}:{user_id}"
        if key in self._allowlist:
            del self._allowlist[key]
            self._save_allowlist()
            return True
        return False

    def list_pending(self) -> list[dict]:
        """列出待审批的配对请求"""
        now = time.time()
        result = []
        expired = []
        for code, info in self._pending.items():
            if now - info["created_at"] > PAIRING_CODE_TTL:
                expired.append(code)
            else:
                result.append({
                    "code": code,
                    "channel": info["channel"],
                    "user_id": info["user_id"],
                    "remaining_seconds": int(PAIRING_CODE_TTL - (now - info["created_at"])),
                })
        for code in expired:
            del self._pending[code]
        return result

    def list_allowlist(self) -> list[dict]:
        """列出白名单"""
        return list(self._allowlist.values())

    # ---- 内部方法 ----

    def _get_or_create_code(self, channel: str, user_id: str) -> str:
        """获取或创建配对码（同一用户复用未过期的码）"""
        now = time.time()
        # 查找已有未过期的码
        for code, info in self._pending.items():
            if info["channel"] == channel and info["user_id"] == user_id:
                if now - info["created_at"] < PAIRING_CODE_TTL:
                    return code
                else:
                    del self._pending[code]
                    break

        # 生成新码（6 位大写字母+数字）
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        self._pending[code] = {
            "channel": channel,
            "user_id": user_id,
            "created_at": now,
        }
        log.info(f"生成配对码: {code} -> {channel}:{user_id}")
        return code

    def _load_allowlist(self) -> None:
        """从文件加载白名单"""
        try:
            if self._allowlist_file.exists():
                data = json.loads(self._allowlist_file.read_text(encoding="utf-8"))
                self._allowlist = data
                log.info(f"已加载 DM 白名单: {len(self._allowlist)} 条")
        except Exception as e:
            log.warning(f"加载 DM 白名单失败: {e}")

    def _save_allowlist(self) -> None:
        """持久化白名单"""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._allowlist_file.write_text(
                json.dumps(self._allowlist, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning(f"保存 DM 白名单失败: {e}")
