"""
禅道数据库访问层

封装 pymysql 连接和常用操作，包括 zt_action 审计日志写入。
所有方法提供同步和异步两种版本。
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

import pymysql

from openvort.plugins.zentao.config import ZentaoSettings
from openvort.utils.logging import get_logger

log = get_logger("plugins.zentao.db")

# 默认 AI 操作账号（兜底，优先用操作人自己的禅道账号）
AI_ACCOUNT = "openVortAi"


def get_actor(params: dict) -> str:
    """从 tool params 中获取操作人账号，优先用注入的禅道账号"""
    return params.get("_zentao_account") or AI_ACCOUNT


def get_actor_display(db: "ZentaoDB", params: dict) -> str:
    """获取操作人展示名：优先禅道 realname，回退账号"""
    actor = get_actor(params)
    try:
        row = db.fetch_one(
            "SELECT realname FROM zt_user WHERE account=%s AND deleted='0' LIMIT 1",
            (actor,),
        )
        if row and row.get("realname"):
            return row["realname"]
    except Exception:
        # 展示名查询失败不影响主流程，回退账号
        pass
    return actor


class ZentaoDB:
    """禅道数据库操作"""

    def __init__(self, settings: ZentaoSettings):
        self._settings = settings

    def get_conn(self) -> pymysql.Connection:
        """获取数据库连接（每次新建，用完需关闭）"""
        return pymysql.connect(**self._settings.to_pymysql_kwargs())

    # ---- 同步查询 ----

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """查询单条记录"""
        conn = self.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """查询多条记录"""
        conn = self.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """执行写操作，返回 lastrowid"""
        conn = self.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                last_id = cur.lastrowid
            conn.commit()
            return last_id
        finally:
            conn.close()

    def execute_many(self, statements: list[tuple[str, tuple]]) -> int:
        """在同一事务中执行多条 SQL，返回最后一条的 lastrowid"""
        conn = self.get_conn()
        try:
            last_id = 0
            with conn.cursor() as cur:
                for sql, params in statements:
                    cur.execute(sql, params)
                    last_id = cur.lastrowid
            conn.commit()
            return last_id
        finally:
            conn.close()

    # ---- 异步包装 ----

    async def async_fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        return await asyncio.to_thread(self.fetch_one, sql, params)

    async def async_fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        return await asyncio.to_thread(self.fetch_all, sql, params)

    async def async_execute(self, sql: str, params: tuple = ()) -> int:
        return await asyncio.to_thread(self.execute, sql, params)

    async def async_execute_many(self, statements: list[tuple[str, tuple]]) -> int:
        return await asyncio.to_thread(self.execute_many, statements)

    # ---- zt_action 审计日志 ----

    def log_action(
        self,
        cur,
        object_type: str,
        object_id: int,
        action: str,
        *,
        product: int = 0,
        project: int = 0,
        execution: int = 0,
        actor: str = AI_ACCOUNT,
        comment: str = "",
        extra: str = "",
    ) -> None:
        """写入禅道操作审计日志（在已有事务中调用）"""
        cur.execute(
            """INSERT INTO zt_action
               (objectType, objectID, product, project, execution,
                actor, action, date, comment, extra)
               VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)""",
            (object_type, object_id, product, project, execution,
             actor, action, comment, extra),
        )

    # ---- 常用查询辅助 ----

    def find_product_id(self, name: str) -> Optional[int]:
        """根据产品名称或 code 查找产品 ID"""
        row = self.fetch_one(
            "SELECT id FROM zt_product WHERE deleted='0' AND (name=%s OR code=%s) LIMIT 1",
            (name, name),
        )
        return row["id"] if row else None

    def find_project_id(self, name: str) -> Optional[int]:
        """根据项目名称查找项目 ID"""
        row = self.fetch_one(
            "SELECT id FROM zt_project WHERE deleted='0' AND name=%s AND type='project' LIMIT 1",
            (name,),
        )
        return row["id"] if row else None

    def find_execution_id(self, name: str) -> Optional[int]:
        """根据迭代名称查找执行 ID"""
        row = self.fetch_one(
            "SELECT id FROM zt_project WHERE deleted='0' AND name=%s AND type='sprint' LIMIT 1",
            (name,),
        )
        return row["id"] if row else None

    def get_execution_project(self, execution_id: int) -> Optional[int]:
        """获取迭代所属的项目 ID"""
        row = self.fetch_one(
            "SELECT parent FROM zt_project WHERE id=%s AND deleted='0'",
            (execution_id,),
        )
        return row["parent"] if row else None
