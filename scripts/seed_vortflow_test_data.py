from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from openvort.config.settings import Settings
from openvort.contacts.models import Member
from openvort.db.engine import close_db, get_session_factory, init_db
from openvort.plugins.vortflow.models import FlowBug, FlowProject, FlowStory, FlowTask

SEED_MARK = "[SEED_VORTFLOW_MALL]"

STORY_STATES = [
    "intake",
    "review",
    "pm_refine",
    "design",
    "breakdown",
    "dev_assign",
    "in_progress",
    "testing",
    "bugfix",
    "done",
]
TASK_STATES = ["todo", "in_progress", "done", "closed"]
BUG_STATES = ["open", "confirmed", "fixing", "resolved", "verified", "closed"]

DEMAND_TITLES = [
    "支持商家后台批量导入 SKU 并自动校验条码重复",
    "订单中心新增按渠道维度的成交额趋势看板",
    "会员中心支持成长值规则按活动模板配置",
    "结算中心支持分账结果失败自动补偿任务",
    "营销中心新增满减与优惠券叠加规则配置",
    "商品中心支持多规格图片按颜色维度管理",
    "风控中心接入异常下单实时拦截策略",
    "运费模板支持区域阶梯计价和偏远地区附加费",
    "门店自提支持核销码失效时间自定义",
    "售后工单中心支持按退款原因统计看板",
    "商品搜索支持拼音首字母和模糊匹配",
    "供应链管理增加采购建议和自动补货功能",
    "积分商城支持积分+现金混合支付模式",
    "物流追踪页面支持地图可视化和时效预估",
    "商品评价模块增加图片审核和敏感词过滤",
]
TASK_TITLES = [
    "拆分订单服务结算逻辑到 settlement-service 并补齐单测",
    "接入 Redis 缓存热点商品详情并增加失效回源机制",
    "重构库存预占释放流程，支持 MQ 消息幂等处理",
    "网关统一鉴权拦截器升级，补齐租户与角色校验",
    "支付回调处理链路增加签名校验和重放攻击防护",
    "改造搜索接口分页参数，兼容游标与页码双模式",
    "搭建订单超时取消定时任务监控告警面板",
    "优化购物车合并逻辑，解决登录后重复项累加问题",
    "完善商品上下架事件通知链路并增加重试机制",
    "重写优惠券核销接口并支持批次并发锁",
    "搭建灰度发布基础设施，支持按用户ID分流",
    "商品详情接口增加本地缓存和 CDN 预热",
    "设计订单状态机并补全异常流转告警",
    "实现基于 WebSocket 的实时库存变更推送",
    "编写 E2E 测试覆盖核心下单到退款全链路",
]
BUG_TITLES = [
    "秒杀高并发场景下库存扣减偶发出现负数",
    "提交订单后优惠券状态未及时更新导致可重复使用",
    "支付成功后订单状态偶发停留在待支付",
    "多门店分销场景结算金额计算结果与预期不一致",
    "退款成功后积分未回退且会员成长值未修正",
    "购物车跨端同步时商品勾选状态丢失",
    "商品详情页切换规格后价格展示未实时刷新",
    "商家后台导出订单在大数据量时出现超时失败",
    "订单备注包含 emoji 时保存后乱码",
    "促销活动边界时间判断错误导致提前结束",
    "搜索结果排序在翻页后出现重复条目",
    "退货审核通过后物流单号未自动回填",
    "用户修改收货地址后已下单的配送信息未同步",
    "后台商品列表筛选条件清空后仍保留上次结果",
    "会员等级升级通知短信发送延迟超过30分钟",
]

TAG_POOL = [
    "客户需求", "运营需求", "高优先", "稳定性", "UI优化",
    "订单域", "支付域", "库存域", "促销域", "用户域",
    "S1", "S2", "S3", "S4", "性能优化",
]


def pick_member(member_ids: list[str], index: int) -> str | None:
    if not member_ids:
        return None
    return member_ids[index % len(member_ids)]


def pick_tags(index: int) -> str:
    t1 = TAG_POOL[index % len(TAG_POOL)]
    t2 = TAG_POOL[(index * 3 + 5) % len(TAG_POOL)]
    tags = [t1] if t1 == t2 else [t1, t2]
    return json.dumps(tags, ensure_ascii=False)


def pick_collaborators(member_ids: list[str], index: int) -> str:
    if len(member_ids) < 3:
        return "[]"
    c1 = member_ids[(index + 2) % len(member_ids)]
    c2 = member_ids[(index + 5) % len(member_ids)]
    collabs = [c1] if c1 == c2 else [c1, c2]
    return json.dumps(collabs, ensure_ascii=False)


async def main() -> None:
    settings = Settings()
    await init_db(settings.database_url)
    sf = get_session_factory()

    async with sf() as session:
        members = (await session.execute(select(Member).order_by(Member.created_at.asc()))).scalars().all()
        member_ids = [m.id for m in members]
        member_names = {m.id: m.name for m in members}
        print(f"Found {len(member_ids)} members: {', '.join(member_names.get(mid, mid) for mid in member_ids[:8])}")

        project = (
            await session.execute(
                select(FlowProject).where(FlowProject.name.ilike("%VortMall%")).order_by(FlowProject.created_at.desc())
            )
        ).scalars().first()
        if not project:
            project = FlowProject(
                name="VortMall 微服务商城项目",
                description=f"{SEED_MARK} VortFlow 测试项目",
                product="VortMall",
                iteration="Sprint 2026-03",
                version="v1.0.0",
                owner_id=pick_member(member_ids, 0),
            )
            session.add(project)
            await session.flush()
            print(f"Created project: {project.name} ({project.id})")
        else:
            print(f"Using existing project: {project.name} ({project.id})")

        # Clear previous seeded records for idempotency (order matters: bugs -> tasks -> stories)
        seeded_story_ids = (await session.execute(
            select(FlowStory.id).where(FlowStory.description.ilike(f"%{SEED_MARK}%"))
        )).scalars().all()
        seeded_task_ids = (await session.execute(
            select(FlowTask.id).where(FlowTask.description.ilike(f"%{SEED_MARK}%"))
        )).scalars().all()

        if seeded_story_ids:
            await session.execute(delete(FlowBug).where(FlowBug.story_id.in_(seeded_story_ids)))
        if seeded_task_ids:
            await session.execute(delete(FlowBug).where(FlowBug.task_id.in_(seeded_task_ids)))
        await session.execute(delete(FlowBug).where(FlowBug.description.ilike(f"%{SEED_MARK}%")))

        if seeded_story_ids:
            await session.execute(delete(FlowTask).where(FlowTask.story_id.in_(seeded_story_ids)))
        await session.execute(delete(FlowTask).where(FlowTask.description.ilike(f"%{SEED_MARK}%")))

        await session.execute(delete(FlowStory).where(FlowStory.description.ilike(f"%{SEED_MARK}%")))
        await session.flush()

        now = datetime.utcnow()
        stories: list[FlowStory] = []
        for i in range(30):
            created = now - timedelta(hours=i * 8 + 3, minutes=i * 7)
            story = FlowStory(
                project_id=project.id,
                title=DEMAND_TITLES[i % len(DEMAND_TITLES)],
                description=f"{SEED_MARK} 需求测试数据 #{i + 1}\n\n"
                            f"## 背景\n作为产品经理，需要此功能提升用户体验。\n\n"
                            f"## 验收标准\n- 功能正常\n- 性能达标\n- 通过测试",
                state=STORY_STATES[i % len(STORY_STATES)],
                priority=(i % 4) + 1,
                submitter_id=pick_member(member_ids, i),
                pm_id=pick_member(member_ids, i + 1),
                reviewer_id=pick_member(member_ids, i + 2),
                tags_json=pick_tags(i),
                collaborators_json=pick_collaborators(member_ids, i),
                deadline=now + timedelta(days=(i % 30) + 3),
                created_at=created,
            )
            session.add(story)
            stories.append(story)
        await session.flush()
        print(f"Inserted {len(stories)} stories")

        tasks: list[FlowTask] = []
        task_types = ["frontend", "backend", "fullstack", "test"]
        for i in range(30):
            parent_story = stories[i % len(stories)]
            created = now - timedelta(hours=i * 6 + 1, minutes=i * 11)
            task = FlowTask(
                story_id=parent_story.id,
                title=TASK_TITLES[i % len(TASK_TITLES)],
                description=f"{SEED_MARK} 任务测试数据 #{i + 1}\n\n"
                            f"## 实现方案\n按技术设计文档实施。\n\n"
                            f"## 自测清单\n- [ ] 单元测试\n- [ ] 接口联调\n- [ ] 代码审查",
                task_type=task_types[i % len(task_types)],
                state=TASK_STATES[i % len(TASK_STATES)],
                assignee_id=pick_member(member_ids, i + 3),
                creator_id=pick_member(member_ids, i),
                tags_json=pick_tags(i + 5),
                collaborators_json=pick_collaborators(member_ids, i + 3),
                estimate_hours=float((i % 5 + 1) * 2),
                actual_hours=float((i % 3) * 1.5) if TASK_STATES[i % len(TASK_STATES)] in ("done", "closed") else None,
                deadline=now + timedelta(days=(i % 20) + 1),
                created_at=created,
            )
            session.add(task)
            tasks.append(task)
        await session.flush()
        print(f"Inserted {len(tasks)} tasks")

        bugs: list[FlowBug] = []
        for i in range(30):
            parent_story = stories[i % len(stories)]
            parent_task = tasks[i % len(tasks)]
            created = now - timedelta(hours=i * 4 + 2, minutes=i * 13)
            bug = FlowBug(
                story_id=parent_story.id,
                task_id=parent_task.id,
                title=BUG_TITLES[i % len(BUG_TITLES)],
                description=f"{SEED_MARK} 缺陷测试数据 #{i + 1}\n\n"
                            f"## 复现步骤\n1. 打开页面\n2. 执行操作\n3. 观察结果\n\n"
                            f"## 期望结果\n功能正常运行\n\n"
                            f"## 实际结果\n出现异常行为",
                severity=(i % 4) + 1,
                state=BUG_STATES[i % len(BUG_STATES)],
                reporter_id=pick_member(member_ids, i + 4),
                assignee_id=pick_member(member_ids, i + 5),
                developer_id=pick_member(member_ids, i + 6),
                tags_json=pick_tags(i + 10),
                collaborators_json=pick_collaborators(member_ids, i + 7),
                created_at=created,
            )
            session.add(bug)
            bugs.append(bug)

        await session.commit()
        print(f"\nSeed completed: stories={len(stories)}, tasks={len(tasks)}, bugs={len(bugs)}")
        print(f"Project: {project.name} ({project.id})")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
