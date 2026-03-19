"""
组织管理插件

将通讯录 Tool 注册到 Agent，让用户通过聊天管理组织架构。
作为核心模块的 Plugin 壳，通过 entry_points 自动发现。
"""

from openvort.contacts.sync import ContactSyncProvider
from openvort.contacts.tools.bind_identity import BindIdentityTool
from openvort.contacts.tools.match_suggestions import MatchSuggestionsTool
from openvort.contacts.tools.resolve_match import ResolveMatchTool
from openvort.contacts.tools.search_member import SearchMemberTool
from openvort.contacts.tools.sync_contacts import SyncContactsTool
from openvort.plugin.base import BasePlugin, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("contacts.plugin")


class ContactsPlugin(BasePlugin):
    """组织管理插件 — 提供聊天式通讯录和组织架构管理能力"""

    name = "contacts"
    display_name = "组织管理"
    description = "通讯录同步、成员搜索、身份映射、汇报关系管理"
    version = "0.1.0"
    core = True  # 核心插件，不可禁用

    def __init__(self):
        self._sync_tool = SyncContactsTool()
        self._search_tool = SearchMemberTool()
        self._suggestions_tool = MatchSuggestionsTool()
        self._resolve_tool = ResolveMatchTool()
        self._bind_tool = BindIdentityTool()

    def set_providers(self, providers: list[ContactSyncProvider]) -> None:
        """注入同步提供者（由 PluginLoader 在加载完成后调用）"""
        self._sync_tool.set_providers(providers)
        log.info(f"通讯录插件已注入 {len(providers)} 个同步源")

    def set_auth_service(self, auth_service) -> None:
        """注入 AuthService（由启动流程调用）"""
        self._sync_tool.set_auth_service(auth_service)

    def get_tools(self) -> list[BaseTool]:
        return [
            self._sync_tool,
            self._search_tool,
            self._suggestions_tool,
            self._resolve_tool,
            self._bind_tool,
        ]

    def get_permissions(self) -> list[dict]:
        return [
            {"code": "contacts.sync", "display_name": "同步通讯录"},
            {"code": "contacts.search", "display_name": "搜索成员"},
            {"code": "contacts.match", "display_name": "管理匹配建议"},
        ]

    def get_prompts(self) -> list[str]:
        return [
            "## 组织管理\n"
            "- 用户可以要求同步通讯录（需管理员权限）\n"
            "- 可以搜索成员，查看其在各平台的身份映射\n"
            "- 管理员可以查看和处理待确认的匹配建议\n"
            "- 同步支持的平台：企业微信、禅道等已配置的平台\n"
            "\n"
            "### 称谓搜索\n"
            "contacts_search 支持中文称谓/昵称（如「杨总」「老王」「小李」「张工」「刘老师」等），"
            "会自动提取姓名进行模糊匹配。当搜索结果有多人时，结合职位(position)和部门帮用户确认目标人选。\n"
            "- 如果用户使用称谓（如「杨总」），直接用该称谓调用 contacts_search，无需要求用户提供全名\n"
            "- 如果匹配到唯一结果，可直接使用；多个结果时，列出候选人让用户确认\n"
        ]
