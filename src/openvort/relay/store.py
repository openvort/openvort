"""
Relay Store — 消息存储

使用 SQLite 存储中继消息，轻量无依赖。
"""

import json
import sqlite3
import time

from openvort.utils.logging import get_logger

log = get_logger("relay.store")


class RelayStore:
    """Relay 消息存储"""

    def __init__(self, db_path: str = "relay.db"):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def init(self) -> None:
        """初始化数据库"""
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS relay_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id TEXT DEFAULT '',
                from_user TEXT DEFAULT '',
                msg_type TEXT DEFAULT 'text',
                content TEXT DEFAULT '',
                raw_data TEXT DEFAULT '{}',
                processed INTEGER DEFAULT 0,
                created_at REAL DEFAULT 0
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_relay_processed ON relay_messages(processed)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_relay_created ON relay_messages(created_at)")
        self._conn.commit()
        log.info(f"Relay Store 已初始化: {self._db_path}")

    def save_message(self, msg_dict: dict) -> int:
        """保存一条消息，返回 ID"""
        cursor = self._conn.execute(
            """INSERT INTO relay_messages (msg_id, from_user, msg_type, content, raw_data, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                msg_dict.get("MsgId", ""),
                msg_dict.get("FromUserName", ""),
                msg_dict.get("MsgType", "text"),
                msg_dict.get("Content", ""),
                json.dumps(msg_dict, ensure_ascii=False),
                float(msg_dict.get("CreateTime", time.time())),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_messages(self, since_id: int = 0, limit: int = 50, unprocessed_only: bool = False) -> list[dict]:
        """获取消息列表"""
        sql = "SELECT id, msg_id, from_user, msg_type, content, raw_data, processed, created_at FROM relay_messages WHERE id > ?"
        params = [since_id]

        if unprocessed_only:
            sql += " AND processed = 0"

        sql += " ORDER BY id ASC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "id": r[0],
                "msg_id": r[1],
                "from_user": r[2],
                "msg_type": r[3],
                "content": r[4],
                "raw_data": json.loads(r[5]) if r[5] else {},
                "processed": bool(r[6]),
                "created_at": r[7],
            }
            for r in rows
        ]

    def mark_processed(self, msg_id: int) -> None:
        """标记消息已处理"""
        self._conn.execute("UPDATE relay_messages SET processed = 1 WHERE id = ?", (msg_id,))
        self._conn.commit()

    def cleanup(self, max_age_hours: int = 72) -> int:
        """清理过期消息"""
        cutoff = time.time() - max_age_hours * 3600
        cursor = self._conn.execute("DELETE FROM relay_messages WHERE created_at < ? AND processed = 1", (cutoff,))
        self._conn.commit()
        deleted = cursor.rowcount
        if deleted:
            log.info(f"已清理 {deleted} 条过期消息")
        return deleted
