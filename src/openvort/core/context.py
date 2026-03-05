"""
请求上下文

封装一次请求的完整上下文：渠道、身份、角色、权限、渠道 prompt 等。
Agent Runtime 和 Tool 执行时的核心依赖。
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openvort.contacts.models import Member

# 角色 prompt 目录
_ROLE_PROMPTS_DIR = Path(__file__).parent.parent / "auth" / "prompts"


@dataclass
class RequestContext:
    """一次请求的完整上下文"""

    channel: str = ""  # 渠道标识 (wecom / dingtalk / cli)
    user_id: str = ""  # 平台 user_id
    member: Member | None = None  # 解析后的成员
    roles: list[str] = field(default_factory=list)  # 成员角色列表
    permissions: set[str] = field(default_factory=set)  # 成员权限集合
    position: str = ""  # 组织职位
    channel_prompt: str = ""  # 渠道 prompt 片段
    allowed_tools: list[str] | None = None  # 渠道允许的 Tool，None=全部
    max_reply_length: int = 0  # 回复长度限制，0=不限
    images: list[dict] = field(default_factory=list)  # 图片列表 [{data, media_type, ...}]
    platform_accounts: dict[str, str] = field(default_factory=dict)  # 平台账号映射 {platform: account}
    target_member_id: str = ""  # 目标成员 ID（用于 AI 员工代理聊天场景）
    caller_member_id: str = ""  # 发起请求的真实成员 ID
    _identity_refresher: Callable[["RequestContext"], Coroutine[Any, Any, None]] | None = field(
        default=None, repr=False
    )  # 可选回调：刷新身份信息（member、platform_accounts 等）

    async def refresh_identity(self) -> None:
        """刷新身份信息（同步/绑定后调用，更新 member 和 platform_accounts）"""
        if self._identity_refresher:
            await self._identity_refresher(self)

    def get_sender_prompt(self) -> str:
        """生成发送者上下文 prompt 片段"""
        if not self.member:
            return ""

        parts = [f"\n\n# 当前对话者\n姓名: {self.member.name}"]
        if self.position:
            parts.append(f"职位: {self.position}")
        if self.member.email:
            parts.append(f"邮箱: {self.member.email}")
        if self.roles:
            parts.append(f"角色: {', '.join(self.roles)}")

        # 加载角色 prompt
        role_hint = self._load_role_prompt()
        if role_hint:
            parts.append(f"\n{role_hint}")

        return "\n".join(parts)

    def has_permission(self, permission: str) -> bool:
        """检查是否有某权限"""
        return "*" in self.permissions or permission in self.permissions

    def _load_role_prompt(self) -> str:
        """加载最高优先级角色的 prompt 文件"""
        priority = ["admin", "manager", "member", "guest"]
        for role in priority:
            if role in self.roles:
                prompt_file = _ROLE_PROMPTS_DIR / f"{role}.md"
                if prompt_file.exists():
                    try:
                        return prompt_file.read_text(encoding="utf-8").strip()
                    except Exception:
                        pass
                break
        return ""
