"""
One-time migration: link VortFlow bugs to iterations based on Zentao execution data.

Steps:
  1. Read VortFlow bug_id → Zentao bug_id mapping from flow_events
  2. Read Zentao bug → execution (iteration) associations
  3. Match or create VortFlow iterations
  4. Insert flow_iteration_bugs records

Usage:
    python migrate_zentao_bug_iterations.py --dry-run   # preview
    python migrate_zentao_bug_iterations.py              # execute
"""
from __future__ import annotations

import argparse
import uuid
from datetime import date, datetime

import pymysql
from pymysql.cursors import DictCursor
import psycopg2
from psycopg2.extras import DictCursor as PgDictCursor, execute_values
import json

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

PRODUCT_MAP = {
    3: "6bbf08e858df4adc87860cc8e68ed520",   # VortMall
    5: "ed32023ab2fb4b7094d1005050f27338",   # 佰消安
    6: "2404c11bde544c00a7b75284568f1ee5",   # Tigshop-Java
    7: "7fcd9624b1da49bea387101ef5958f2a",   # Tigshop-PHP
}

# Zentao parent project → VortFlow project
ZT_PARENT_TO_VF_PROJECT = {
    6: "6bbf08e858df4adc87860cc8e68ed520",   # VortMall项目
    9: "ed32023ab2fb4b7094d1005050f27338",   # 佰消安项目
    11: "2404c11bde544c00a7b75284568f1ee5",  # Tigshop-Java项目
}

ZT_STATUS_TO_VF = {
    "wait": "planning",
    "doing": "active",
    "done": "completed",
    "closed": "completed",
    "suspended": "planning",
}

_ZERO_DATE = date(1, 1, 1)


def _uuid() -> str:
    return uuid.uuid4().hex


def _safe_datetime(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return None if v.year < 1900 else v
    if isinstance(v, date):
        return None if v.year < 1900 else datetime(v.year, v.month, v.day)
    return None


def migrate(dry_run: bool):
    zt_conn = pymysql.connect(**ZENTAO_CONN)
    pg_conn = psycopg2.connect(**PG_CONN)
    pg_conn.autocommit = False

    try:
        pg_cur = pg_conn.cursor(cursor_factory=PgDictCursor)
        zt_cur = zt_conn.cursor()

        # ── Step 1: VortFlow bug_id → Zentao bug_id mapping ──
        print("\n[1/5] 读取 VortFlow → 禅道 bug ID 映射...")
        pg_cur.execute("""
            SELECT entity_id, detail FROM flow_events
            WHERE entity_type = 'bug' AND action = 'created'
              AND detail LIKE '%zentao%'
        """)
        vf_to_zt = {}
        zt_to_vf = {}
        for ev in pg_cur.fetchall():
            detail = json.loads(ev["detail"])
            zt_id = detail.get("zentao_id")
            if zt_id:
                vf_to_zt[ev["entity_id"]] = zt_id
                zt_to_vf[zt_id] = ev["entity_id"]
        print(f"  映射数量: {len(vf_to_zt)}")

        # ── Step 2: Zentao bug → execution mapping ──
        print("\n[2/5] 读取禅道 bug → 迭代关联...")
        product_ids = ",".join(str(p) for p in PRODUCT_MAP.keys())
        zt_cur.execute(f"""
            SELECT id, execution FROM zt_bug
            WHERE deleted = '0' AND product IN ({product_ids}) AND execution > 0
        """)
        zt_bug_exec = {}
        for r in zt_cur.fetchall():
            zt_bug_exec[r["id"]] = r["execution"]
        print(f"  有迭代关联的 bug: {len(zt_bug_exec)}")

        # ── Step 3: Zentao execution details ──
        print("\n[3/5] 读取禅道迭代详情...")
        zt_cur.execute(f"""
            SELECT id, name, parent, status, begin, end
            FROM zt_project
            WHERE type = 'sprint' AND deleted = '0'
              AND id IN (
                SELECT DISTINCT execution FROM zt_bug
                WHERE deleted = '0' AND product IN ({product_ids}) AND execution > 0
              )
        """)
        zt_executions = {}
        for r in zt_cur.fetchall():
            zt_executions[r["id"]] = r
        print(f"  禅道迭代数: {len(zt_executions)}")

        # ── Step 4: Match or create VortFlow iterations ──
        print("\n[4/5] 匹配/创建 VortFlow 迭代...")
        pg_cur.execute("SELECT id, project_id, name FROM flow_iterations")
        existing = {}
        for it in pg_cur.fetchall():
            key = (it["project_id"], it["name"])
            existing[key] = it["id"]

        # Zentao execution_id → VortFlow iteration_id
        exec_to_vf_iter = {}
        created_count = 0
        matched_count = 0
        new_iter_rows = []

        for zt_exec_id, zt_exec in zt_executions.items():
            vf_project_id = ZT_PARENT_TO_VF_PROJECT.get(zt_exec["parent"])
            if not vf_project_id:
                print(f"  [SKIP] 禅道迭代 '{zt_exec['name']}' (parent={zt_exec['parent']}) 无法映射到 VortFlow 项目")
                continue

            key = (vf_project_id, zt_exec["name"])
            if key in existing:
                exec_to_vf_iter[zt_exec_id] = existing[key]
                matched_count += 1
                print(f"  [MATCH] '{zt_exec['name']}' → {existing[key][:8]}...")
            else:
                new_id = _uuid()
                vf_status = ZT_STATUS_TO_VF.get(zt_exec["status"], "planning")
                start_date = _safe_datetime(zt_exec["begin"])
                end_date = _safe_datetime(zt_exec["end"])

                new_iter_rows.append((
                    new_id, vf_project_id, zt_exec["name"], "",
                    None, start_date, end_date, vf_status, None,
                ))
                exec_to_vf_iter[zt_exec_id] = new_id
                existing[key] = new_id
                created_count += 1
                print(f"  [CREATE] '{zt_exec['name']}' → {new_id[:8]}... (project={vf_project_id[:8]}...)")

        print(f"  已匹配: {matched_count}, 新建: {created_count}")

        if new_iter_rows and not dry_run:
            execute_values(pg_cur, """
                INSERT INTO flow_iterations
                    (id, project_id, name, goal, owner_id, start_date, end_date, status, estimate_hours)
                VALUES %s
            """, new_iter_rows)

        # ── Step 5: Insert flow_iteration_bugs ──
        print("\n[5/5] 写入 bug-迭代关联...")

        pg_cur.execute("SELECT iteration_id, bug_id FROM flow_iteration_bugs")
        existing_links = {(r["iteration_id"], r["bug_id"]) for r in pg_cur.fetchall()}
        print(f"  已有关联: {len(existing_links)} 条")

        link_rows = []
        skipped_no_mapping = 0
        skipped_no_iter = 0
        skipped_exists = 0

        for zt_bug_id, zt_exec_id in zt_bug_exec.items():
            vf_bug_id = zt_to_vf.get(zt_bug_id)
            if not vf_bug_id:
                skipped_no_mapping += 1
                continue

            vf_iter_id = exec_to_vf_iter.get(zt_exec_id)
            if not vf_iter_id:
                skipped_no_iter += 1
                continue

            if (vf_iter_id, vf_bug_id) in existing_links:
                skipped_exists += 1
                continue

            link_rows.append((_uuid(), vf_iter_id, vf_bug_id, 0))

        print(f"  新增关联: {len(link_rows)} 条")
        print(f"  跳过（无 bug 映射）: {skipped_no_mapping}")
        print(f"  跳过（无迭代映射）: {skipped_no_iter}")
        print(f"  跳过（已存在）: {skipped_exists}")

        if link_rows and not dry_run:
            execute_values(pg_cur, """
                INSERT INTO flow_iteration_bugs (id, iteration_id, bug_id, bug_order)
                VALUES %s
            """, link_rows, page_size=500)

        if not dry_run:
            pg_conn.commit()
            print("\n写入完成!")
        else:
            print("\n[DRY-RUN] 跳过写入，执行 python migrate_zentao_bug_iterations.py 正式迁移")

        # Summary
        print("\n" + "=" * 50)
        print("迁移摘要:")
        print(f"  迭代 — 已匹配: {matched_count}, 新建: {created_count}")
        print(f"  关联 — 新增: {len(link_rows)}, 跳过: {skipped_no_mapping + skipped_no_iter + skipped_exists}")

    except Exception as e:
        pg_conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        zt_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Zentao bug-iteration links to VortFlow")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
