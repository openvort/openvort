"""
One-time migration script: Zentao bugs → VortFlow flow_bugs.

Usage:
    python migrate_zentao_bugs.py --dry-run   # preview only
    python migrate_zentao_bugs.py             # execute migration
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import date, datetime

import pymysql
from pymysql.cursors import DictCursor
import psycopg2
from psycopg2.extras import DictCursor as PgDictCursor, execute_values

# ── Config ──────────────────────────────────────────────────────

ZENTAO_CONN = dict(
    host="192.168.8.221", port=3306,
    user="zentao", password="ptYftCci2sYeHJ5N",
    database="zentao", charset="utf8mb4",
    cursorclass=DictCursor,
)

PG_CONN = dict(
    host="192.168.8.231", port=5432,
    user="openvort", password="tF4cr3LhBtKsKHAA",
    dbname="openvort",
)

# Zentao product_id → VortFlow project_id
PRODUCT_MAP = {
    3: "6bbf08e858df4adc87860cc8e68ed520",   # VortMall
    5: "ed32023ab2fb4b7094d1005050f27338",   # 佰消安
    6: "2404c11bde544c00a7b75284568f1ee5",   # Tigshop-Java
    7: "7fcd9624b1da49bea387101ef5958f2a",   # Tigshop → Tigshop-PHP
}

PRODUCT_NAMES = {3: "VortMall", 5: "佰消安", 6: "Tigshop-Java", 7: "Tigshop"}

_ZERO_DATE = date(1, 1, 1)
_ZERO_DT = datetime(1, 1, 1)


def _safe_date(v):
    """Convert zentao date/datetime; treat 0000-00-00 and similar as None."""
    if v is None:
        return None
    if isinstance(v, str):
        return None if (v.startswith("0000") or not v.strip()) else v
    if isinstance(v, datetime):
        return None if v.year < 1900 else v
    if isinstance(v, date):
        return None if v.year < 1900 else v
    return v

# Zentao status → VortFlow state
STATUS_MAP = {
    "active": "open",
    "resolved": "resolved",
    "closed": "closed",
}


def _uuid() -> str:
    return uuid.uuid4().hex


def build_user_map(zt_conn, pg_conn) -> dict[str, str | None]:
    """Build zentao account → VortFlow member_id mapping by realname."""
    zt_cur = zt_conn.cursor()
    zt_cur.execute("SELECT account, realname FROM zt_user WHERE deleted='0'")
    zt_users = {r["account"]: r["realname"] for r in zt_cur.fetchall()}

    pg_cur = pg_conn.cursor(cursor_factory=PgDictCursor)
    pg_cur.execute("SELECT id, name FROM members WHERE is_virtual = false")
    vf_members = {r["name"]: r["id"] for r in pg_cur.fetchall()}

    mapping: dict[str, str | None] = {}
    unmatched = []

    for account, realname in zt_users.items():
        member_id = vf_members.get(realname)
        mapping[account] = member_id
        if not member_id:
            unmatched.append((account, realname))

    return mapping, unmatched


def create_container_stories(pg_conn, dry_run: bool) -> dict[str, str]:
    """Create a placeholder story per project for migrated bugs. Returns project_id → story_id."""
    pg_cur = pg_conn.cursor()
    result = {}
    for product_id, project_id in PRODUCT_MAP.items():
        story_id = _uuid()
        name = PRODUCT_NAMES[product_id]
        if not dry_run:
            pg_cur.execute(
                """INSERT INTO flow_stories (id, project_id, title, description, state, priority)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (story_id, project_id, f"禅道历史缺陷 - {name}",
                 "从禅道迁移的历史缺陷容器需求", "intake", 4),
            )
        result[project_id] = story_id
        print(f"  容器需求: {name} → story_id={story_id[:8]}...")
    return result


def create_missing_members(pg_conn, unmatched: list, dry_run: bool) -> dict[str, str]:
    """Create members for unmatched zentao accounts. Returns account → new member_id."""
    extra_map = {}
    if not unmatched:
        return extra_map
    pg_cur = pg_conn.cursor()
    for account, realname in unmatched:
        member_id = _uuid()
        display_name = realname if realname else account
        if not dry_run:
            pg_cur.execute(
                """INSERT INTO members (id, name, email, phone, avatar_url, avatar_source,
                   position, bio, password_hash, is_account, status, notification_prefs,
                   is_virtual, post, virtual_role, virtual_system_prompt, skills,
                   auto_report, report_frequency)
                   VALUES (%s, %s, '', '', '', '', '', '', '', false, 'active', '{}',
                           false, '', '', '', '[]', false, 'daily')""",
                (member_id, display_name),
            )
        extra_map[account] = member_id
        print(f"  新建成员: {display_name} (account={account}) → {member_id[:8]}...")
    return extra_map


def fetch_zentao_bugs(zt_conn) -> list[dict]:
    """Fetch all bugs for the 4 target products."""
    cur = zt_conn.cursor()
    product_ids = ",".join(str(p) for p in PRODUCT_MAP.keys())
    cur.execute(f"""
        SELECT id, product, title, steps, severity, pri, type, status,
               openedBy, openedDate, assignedTo, assignedDate,
               resolvedBy, resolvedDate, closedBy, closedDate,
               deadline, confirmed, activatedCount
        FROM zt_bug
        WHERE deleted='0' AND product IN ({product_ids})
        ORDER BY product, id
    """)
    return cur.fetchall()


def migrate(dry_run: bool):
    zt_conn = pymysql.connect(**ZENTAO_CONN)
    pg_conn = psycopg2.connect(**PG_CONN)
    pg_conn.autocommit = False

    try:
        # 1. Build user mapping
        print("\n[1/5] 构建人员映射...")
        user_map, unmatched = build_user_map(zt_conn, pg_conn)
        matched = sum(1 for v in user_map.values() if v)
        print(f"  已匹配: {matched}, 未匹配: {len(unmatched)}")
        if unmatched:
            for acc, name in unmatched:
                print(f"    未匹配: account={acc} realname={name}")

        # 2. Create members for unmatched
        print("\n[2/5] 处理未匹配用户...")
        if unmatched:
            extra = create_missing_members(pg_conn, unmatched, dry_run)
            user_map.update(extra)
        else:
            print("  无需创建新成员")

        # 3. Create container stories
        print("\n[3/5] 创建容器需求...")
        story_map = create_container_stories(pg_conn, dry_run)

        # 4. Fetch zentao bugs
        print("\n[4/5] 读取禅道 Bug 数据...")
        bugs = fetch_zentao_bugs(zt_conn)
        print(f"  共 {len(bugs)} 个 bug")

        # 5. Insert into VortFlow
        print("\n[5/5] 写入 VortFlow...")
        pg_cur = pg_conn.cursor()

        bug_rows = []
        event_rows = []
        stats = {pid: 0 for pid in PRODUCT_MAP.keys()}

        for b in bugs:
            project_id = PRODUCT_MAP[b["product"]]
            story_id = story_map[project_id]
            bug_id = _uuid()

            state = STATUS_MAP.get(b["status"], "open")
            severity = b["severity"] if 1 <= b["severity"] <= 4 else 3
            reporter_id = user_map.get(b["openedBy"])
            assignee_id = user_map.get(b["assignedTo"]) if b["assignedTo"] else None

            opened_date = _safe_date(b["openedDate"]) or datetime.now()
            deadline = _safe_date(b.get("deadline"))

            resolved_by = user_map.get(b["resolvedBy"]) if b.get("resolvedBy") else None
            closed_date = _safe_date(b.get("closedDate"))
            resolved_date = _safe_date(b.get("resolvedDate"))

            start_at = opened_date
            end_at = closed_date or resolved_date

            description = b["steps"] or ""

            bug_rows.append((
                bug_id, story_id, None,
                b["title"], description, severity, state,
                reporter_id, assignee_id, resolved_by,
                "[]", "[]",
                None, None, deadline, start_at, end_at,
                None, "",
                opened_date, opened_date,
            ))

            event_rows.append((
                "bug", bug_id, "created",
                reporter_id,
                json.dumps({"title": b["title"], "source": "zentao", "zentao_id": b["id"]}, ensure_ascii=False),
                opened_date,
            ))

            stats[b["product"]] += 1

        if not dry_run:
            execute_values(pg_cur, """
                INSERT INTO flow_bugs
                    (id, story_id, task_id,
                     title, description, severity, state,
                     reporter_id, assignee_id, developer_id,
                     tags_json, collaborators_json,
                     estimate_hours, actual_hours, deadline, start_at, end_at,
                     repo_id, branch,
                     created_at, updated_at)
                VALUES %s
            """, bug_rows, page_size=500)

            execute_values(pg_cur, """
                INSERT INTO flow_events
                    (entity_type, entity_id, action, actor_id, detail, created_at)
                VALUES %s
            """, event_rows, page_size=500)

            pg_conn.commit()
            print("  写入完成!")
        else:
            print("  [DRY-RUN] 跳过写入")

        # Summary
        print("\n" + "=" * 50)
        print("迁移摘要:")
        for pid, count in stats.items():
            name = PRODUCT_NAMES[pid]
            print(f"  {name}: {count} 个 bug")
        print(f"  合计: {sum(stats.values())} 个 bug")
        if dry_run:
            print("\n  以上为预览，执行 python migrate_zentao_bugs.py 正式迁移")

    except Exception as e:
        pg_conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        zt_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Zentao bugs to VortFlow")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
