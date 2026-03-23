"""
Seed script: create a demo tech company org structure (~50 people).

Usage:
    python scripts/seed_demo_org.py

Directly inserts into the database (no API auth required).
"""

import uuid

import psycopg2


DB_URL = "postgresql://yangqiang@localhost:5432/openvort_local"


def _uuid():
    return uuid.uuid4().hex


conn = psycopg2.connect(DB_URL)
conn.autocommit = False
cur = conn.cursor()


# ---- lookup existing admin ----
cur.execute("SELECT id FROM members WHERE name = 'admin' AND is_account = true LIMIT 1")
row = cur.fetchone()
if not row:
    print("Admin member not found!")
    raise SystemExit(1)
ADMIN_ID = row[0]
print(f"Found admin member: {ADMIN_ID[:8]}...")


# ---------------------------------------------------------------------------
# Department definitions (hierarchical)
# ---------------------------------------------------------------------------
ROOT_DEPARTMENTS = [
    "总经理办公室",
    "技术中心",
    "产品中心",
    "市场销售部",
    "人力行政部",
    "财务部",
]

CHILD_DEPARTMENTS = {
    "技术中心": ["架构组", "后端开发组", "前端开发组", "测试组", "运维组", "数据团队"],
    "产品中心": ["产品设计组", "UI/UX设计组"],
    "市场销售部": ["市场组", "销售组"],
}

# ---------------------------------------------------------------------------
# Member definitions: (name, email, phone, position, dept, is_account, role)
# ---------------------------------------------------------------------------
MEMBERS = [
    # --- 总经理办公室 ---
    ("林小美", "linxiaomei@vorttech.com", "13800100002", "总经理助理", "总经理办公室", True, ""),

    # --- 技术中心 ---
    ("张伟", "zhangwei@vorttech.com", "13800100003", "CTO / 技术副总裁", "技术中心", True, "manager"),
    ("韩磊", "hanlei@vorttech.com", "13800100004", "首席架构师", "架构组", True, ""),
    ("秦峰", "qinfeng@vorttech.com", "13800100005", "架构师", "架构组", False, ""),
    ("李明", "liming@vorttech.com", "13800100006", "后端开发组长", "后端开发组", True, ""),
    ("王磊", "wanglei@vorttech.com", "13800100007", "高级后端工程师", "后端开发组", False, ""),
    ("刘洋", "liuyang@vorttech.com", "13800100008", "高级后端工程师", "后端开发组", False, ""),
    ("陈浩", "chenhao@vorttech.com", "13800100009", "后端工程师", "后端开发组", False, ""),
    ("赵鑫", "zhaoxin@vorttech.com", "13800100010", "后端工程师", "后端开发组", False, ""),
    ("孙婷", "sunting@vorttech.com", "13800100011", "前端开发组长", "前端开发组", True, ""),
    ("黄杰", "huangjie@vorttech.com", "13800100012", "高级前端工程师", "前端开发组", False, ""),
    ("吴佳", "wujia@vorttech.com", "13800100013", "高级前端工程师", "前端开发组", False, ""),
    ("徐晨", "xuchen@vorttech.com", "13800100014", "前端工程师", "前端开发组", False, ""),
    ("马超", "machao@vorttech.com", "13800100015", "前端工程师", "前端开发组", False, ""),
    ("朱丽", "zhuli@vorttech.com", "13800100016", "测试组长", "测试组", True, ""),
    ("何强", "heqiang@vorttech.com", "13800100017", "高级测试工程师", "测试组", False, ""),
    ("胡敏", "humin@vorttech.com", "13800100018", "测试工程师", "测试组", False, ""),
    ("郭伟", "guowei@vorttech.com", "13800100019", "测试工程师", "测试组", False, ""),
    ("高远", "gaoyuan@vorttech.com", "13800100020", "运维组长", "运维组", True, ""),
    ("梁志刚", "liangzhigang@vorttech.com", "13800100021", "运维工程师", "运维组", False, ""),
    ("邓伟", "dengwei@vorttech.com", "13800100022", "运维工程师", "运维组", False, ""),
    ("范晓东", "fanxiaodong@vorttech.com", "13800100023", "数据负责人", "数据团队", True, ""),
    ("蔡文斌", "caiwenbin@vorttech.com", "13800100024", "数据工程师", "数据团队", False, ""),
    ("宋雅", "songya@vorttech.com", "13800100025", "数据分析师", "数据团队", False, ""),

    # --- 产品中心 ---
    ("王芳", "wangfang@vorttech.com", "13800100026", "产品副总裁", "产品中心", True, "manager"),
    ("刘静", "liujing@vorttech.com", "13800100027", "高级产品经理", "产品设计组", True, ""),
    ("陈蕾", "chenlei@vorttech.com", "13800100028", "产品经理", "产品设计组", False, ""),
    ("杨洁", "yangjie@vorttech.com", "13800100029", "产品经理", "产品设计组", False, ""),
    ("张慧", "zhanghui@vorttech.com", "13800100030", "产品助理", "产品设计组", False, ""),
    ("李娜", "lina@vorttech.com", "13800100031", "设计主管", "UI/UX设计组", True, ""),
    ("赵雪", "zhaoxue@vorttech.com", "13800100032", "UI设计师", "UI/UX设计组", False, ""),
    ("周莹", "zhouying@vorttech.com", "13800100033", "UX设计师", "UI/UX设计组", False, ""),

    # --- 市场销售部 ---
    ("陈刚", "chengang@vorttech.com", "13800100034", "市场销售VP", "市场销售部", True, "manager"),
    ("张蕾", "zhanglei@vorttech.com", "13800100035", "市场经理", "市场组", True, ""),
    ("王欢", "wanghuan@vorttech.com", "13800100036", "市场专员", "市场组", False, ""),
    ("刘洁", "liujie@vorttech.com", "13800100037", "市场专员", "市场组", False, ""),
    ("李强", "liqiang@vorttech.com", "13800100038", "市场专员", "市场组", False, ""),
    ("赵磊", "zhaolei@vorttech.com", "13800100039", "销售经理", "销售组", True, ""),
    ("钱进", "qianjin@vorttech.com", "13800100040", "销售代表", "销售组", False, ""),
    ("孙鹏", "sunpeng@vorttech.com", "13800100041", "销售代表", "销售组", False, ""),

    # --- 人力行政部 ---
    ("周颖", "zhouying2@vorttech.com", "13800100042", "人力行政总监", "人力行政部", True, "manager"),
    ("吴倩", "wuqian@vorttech.com", "13800100043", "HR经理", "人力行政部", True, ""),
    ("郑丽", "zhengli@vorttech.com", "13800100044", "招聘专员", "人力行政部", False, ""),
    ("冯敏", "fengmin@vorttech.com", "13800100045", "行政经理", "人力行政部", True, ""),
    ("蒋涛", "jiangtao@vorttech.com", "13800100046", "行政专员", "人力行政部", False, ""),

    # --- 财务部 ---
    ("黄明", "huangming@vorttech.com", "13800100047", "财务总监", "财务部", True, "manager"),
    ("曹静", "caojing@vorttech.com", "13800100048", "财务经理", "财务部", True, ""),
    ("彭雪", "pengxue@vorttech.com", "13800100049", "会计", "财务部", False, ""),
    ("谢洋", "xieyang@vorttech.com", "13800100050", "出纳", "财务部", False, ""),
]

# ---------------------------------------------------------------------------
# Reporting relations: (reporter_name, supervisor_name)
# ---------------------------------------------------------------------------
REPORTING_RELATIONS = [
    ("张伟", "杨强"), ("王芳", "杨强"), ("陈刚", "杨强"),
    ("周颖", "杨强"), ("黄明", "杨强"), ("林小美", "杨强"),
    ("韩磊", "张伟"), ("李明", "张伟"), ("孙婷", "张伟"),
    ("朱丽", "张伟"), ("高远", "张伟"), ("范晓东", "张伟"),
    ("秦峰", "韩磊"),
    ("王磊", "李明"), ("刘洋", "李明"), ("陈浩", "李明"), ("赵鑫", "李明"),
    ("黄杰", "孙婷"), ("吴佳", "孙婷"), ("徐晨", "孙婷"), ("马超", "孙婷"),
    ("何强", "朱丽"), ("胡敏", "朱丽"), ("郭伟", "朱丽"),
    ("梁志刚", "高远"), ("邓伟", "高远"),
    ("蔡文斌", "范晓东"), ("宋雅", "范晓东"),
    ("刘静", "王芳"), ("李娜", "王芳"),
    ("陈蕾", "刘静"), ("杨洁", "刘静"), ("张慧", "刘静"),
    ("赵雪", "李娜"), ("周莹", "李娜"),
    ("张蕾", "陈刚"), ("赵磊", "陈刚"),
    ("王欢", "张蕾"), ("刘洁", "张蕾"), ("李强", "张蕾"),
    ("钱进", "赵磊"), ("孙鹏", "赵磊"),
    ("吴倩", "周颖"), ("郑丽", "周颖"), ("冯敏", "周颖"), ("蒋涛", "周颖"),
    ("曹静", "黄明"), ("彭雪", "黄明"), ("谢洋", "黄明"),
]


def create_departments():
    """Create all departments and return {name: id} mapping."""
    dept_ids = {}
    print("\n=== Creating departments ===")

    for name in ROOT_DEPARTMENTS:
        cur.execute(
            "INSERT INTO departments (name, platform, platform_dept_id, \"order\") "
            "VALUES (%s, 'manual', '', 0) RETURNING id",
            (name,),
        )
        did = cur.fetchone()[0]
        dept_ids[name] = did
        print(f"  + {name} (id={did})")

    for parent_name, children in CHILD_DEPARTMENTS.items():
        parent_id = dept_ids[parent_name]
        for idx, child_name in enumerate(children):
            cur.execute(
                "INSERT INTO departments (name, parent_id, platform, platform_dept_id, \"order\") "
                "VALUES (%s, %s, 'manual', '', %s) RETURNING id",
                (child_name, parent_id, idx),
            )
            did = cur.fetchone()[0]
            dept_ids[child_name] = did
            print(f"  + {parent_name} / {child_name} (id={did})")

    return dept_ids


def update_admin(dept_ids):
    """Rename existing admin member to 杨强 with full profile."""
    print("\n=== Updating admin -> 杨强 ===")
    cur.execute(
        "UPDATE members SET name = %s, email = %s, phone = %s, position = %s WHERE id = %s",
        ("杨强", "yangqiang@vorttech.com", "13800100001", "总经理", ADMIN_ID),
    )
    gm_dept_id = dept_ids["总经理办公室"]
    cur.execute(
        "INSERT INTO member_departments (member_id, department_id, is_primary) VALUES (%s, %s, true) "
        "ON CONFLICT (member_id, department_id) DO NOTHING",
        (ADMIN_ID, gm_dept_id),
    )
    print(f"  Updated: admin -> 杨强 (总经理)")


def create_members(dept_ids):
    """Create all members and return {name: member_id} mapping."""
    member_ids = {"杨强": ADMIN_ID}
    print("\n=== Creating members ===")

    # Look up existing role IDs
    cur.execute("SELECT id, name FROM roles")
    role_map = {name: rid for rid, name in cur.fetchall()}

    for name, email, phone, position, dept_name, is_account, role in MEMBERS:
        mid = _uuid()
        cur.execute(
            "INSERT INTO members "
            "(id, name, email, phone, position, is_account, status, avatar_url, bio, password_hash, notification_prefs) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'active', '', '', '', '{}')",
            (mid, name, email, phone, position, is_account),
        )
        member_ids[name] = mid

        dept_id = dept_ids.get(dept_name)
        if dept_id:
            cur.execute(
                "INSERT INTO member_departments (member_id, department_id, is_primary) "
                "VALUES (%s, %s, true) ON CONFLICT (member_id, department_id) DO NOTHING",
                (mid, dept_id),
            )

        if role and role in role_map:
            cur.execute(
                "INSERT INTO member_roles (member_id, role_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (mid, role_map[role]),
            )

        tag = f" [{role}]" if role else ""
        acct = " [account]" if is_account else ""
        print(f"  + {name} ({position}) -> {dept_name}{acct}{tag}")

    return member_ids


def create_reporting_relations(member_ids):
    """Set up reporting (supervisor) relationships."""
    print("\n=== Creating reporting relations ===")
    ok = 0
    for reporter_name, supervisor_name in REPORTING_RELATIONS:
        rid = member_ids.get(reporter_name)
        sid = member_ids.get(supervisor_name)
        if not rid or not sid:
            print(f"  ! Missing: {reporter_name} or {supervisor_name}")
            continue
        try:
            cur.execute(
                "INSERT INTO reporting_relations (reporter_id, supervisor_id, relation_type, is_primary) "
                "VALUES (%s, %s, 'direct', true) ON CONFLICT (reporter_id, supervisor_id) DO NOTHING",
                (rid, sid),
            )
            ok += 1
        except Exception as e:
            print(f"  ! Failed {reporter_name} -> {supervisor_name}: {e}")
            conn.rollback()
    print(f"  Created {ok}/{len(REPORTING_RELATIONS)} reporting relations")


def main():
    print("=" * 52)
    print("  OpenVort Demo Org Seed Script")
    print("  ~50 people tech company (direct DB insert)")
    print("=" * 52)

    try:
        dept_ids = create_departments()
        print(f"\n  Total departments: {len(dept_ids)}")

        update_admin(dept_ids)

        member_ids = create_members(dept_ids)
        print(f"\n  Total members: {len(member_ids)}")

        create_reporting_relations(member_ids)

        conn.commit()
        print("\n" + "=" * 52)
        print(f"  Done! {len(member_ids)} members in {len(dept_ids)} departments")
        print("=" * 52)

    except Exception as e:
        conn.rollback()
        print(f"\n  ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
