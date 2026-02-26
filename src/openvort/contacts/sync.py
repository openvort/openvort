"""
通讯录同步抽象层

定义 ContactSyncProvider 接口和平台联系人数据类。
Channel / Plugin 实现此接口即可接入通讯录同步。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PlatformContact:
    """平台侧联系人（同步输入）"""

    platform: str  # wecom / dingtalk / feishu / zentao / gitee
    user_id: str  # 平台侧唯一 ID
    username: str = ""  # 账号名
    display_name: str = ""  # 显示名
    email: str = ""
    phone: str = ""
    position: str = ""  # 职位
    department: str = ""  # 部门名称
    raw_data: dict = field(default_factory=dict)  # 完整原始数据


@dataclass
class PlatformDepartment:
    """平台侧部门"""

    platform: str
    dept_id: str  # 平台侧部门 ID
    name: str = ""
    parent_dept_id: str = ""  # 上级部门 ID（平台侧）


class ContactSyncProvider(ABC):
    """通讯录同步提供者

    每个 Channel / Plugin 可实现此接口，提供从外部平台拉取成员和部门的能力。
    ContactService 统一调度同步流程。
    """

    platform: str = ""  # 平台标识，如 "wecom", "zentao"

    @abstractmethod
    async def fetch_members(self) -> list[PlatformContact]:
        """拉取平台全量成员列表"""
        ...

    @abstractmethod
    async def fetch_departments(self) -> list[PlatformDepartment]:
        """拉取平台部门列表"""
        ...
