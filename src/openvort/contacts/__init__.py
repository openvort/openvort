"""
通讯录模块

提供统一的成员管理、多平台身份映射和智能匹配能力。
"""

from openvort.contacts.resolver import IdentityResolver
from openvort.contacts.service import ContactService
from openvort.contacts.sync import ContactSyncProvider, PlatformContact, PlatformDepartment

__all__ = [
    "ContactService",
    "ContactSyncProvider",
    "IdentityResolver",
    "PlatformContact",
    "PlatformDepartment",
]
