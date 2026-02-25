"""消息中继服务"""

from openvort.relay.server import create_app
from openvort.relay.store import RelayStore

__all__ = ["RelayStore", "create_app"]
