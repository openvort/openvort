from __future__ import annotations

import asyncio
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
    "rejected",
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
    "【需求】支持商家后台批量导入 SKU 并自动校验条码重复",
    "【需求】订单中心新增按渠道维度的成交额趋势看板",
    "【需求】会员中心支持成长值规则按活动模板配置",
    "【需求】结算中心支持分账结果失败自动补偿任务",
    "【需求】营销中心新增满减与优惠券叠加规则配置",
    "【需求】商品中心支持多规格图片按颜色维度管理",
    "【需求】风控中心接入异常下单实时拦截策略",
    "【需求】运费模板支持区域阶梯计价和偏远地区附加费",
    "【需求】门店自提支持核销码失效时间自定义",
    "【需求】售后工单中心支持按退款原因统计看板",
]
TASK_TITLES = [
    "【任务】拆分订单服务结算逻辑到 settlement-service 并补齐单测",
    "【任务】接入 Redis 缓存热点商品详情并增加失效回源机制",
    "【任务】重构库存预占释放流程，支持 MQ 消息幂等处理",
    "【任务】网关统一鉴权拦截器升级，补齐租户与角色校验",
    "【任务】支付回调处理链路增加签名校验和重放攻击防护",
    "【任务】改造搜索接口分页参数，兼容游标与页码双模式",
    "【任务】搭建订单超时取消定时任务监控告警面板",
    "【任务】优化购物车合并逻辑，解决登录后重复项累加问题",
    "【任务】完善商品上下架事件通知链路并增加重试机制",
    "【任务】重写优惠券核销接口并支持批次并发锁",
]
BUG_TITLES = [
    "【缺陷】秒杀高并发场景下库存扣减偶发出现负数",
    "【缺陷】提交订单后优惠券状态未及时更新导致可重复使用",
    "【缺陷】支付成功后订单状态偶发停留在待支付",
    "【缺陷】多门店分销场景结算金额计算结果与预期不一致",
    "【缺陷】退款成功后积分未回退且会员成长值未修正",
    "【缺陷】购物车跨端同步时商品勾选状态丢失",
    "【缺陷】商品详情页切换规格后价格展示未实时刷新",
    "【缺陷】商家后台导出订单在大数据量时出现超时失败",
    "【缺陷】订单备注包含 emoji 时保存后乱码",
    "【缺陷】促销活动边界时间判断错误导致提前结束",
]


def pick_member(member_ids: list[str], index: int) -> str | None:
    if not member_ids:
        return None
    return member_ids[index % len(member_ids)]


async def main() -> None:
    settings = Settings()
    await init_db(settings.database_url)
    sf = get_session_factory()

    async with sf() as session:
        members = (await session.execute(select(Member).order_by(Member.created_at.asc()))).scalars().all()
        member_ids = [m.id for m in members]

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

        # Clear previous seeded records to keep reruns idempotent.
        await session.execute(delete(FlowBug).where(FlowBug.description.ilike(f"%{SEED_MARK}%")))
        await session.execute(delete(FlowTask).where(FlowTask.description.ilike(f"%{SEED_MARK}%")))
        await session.execute(delete(FlowStory).where(FlowStory.description.ilike(f"%{SEED_MARK}%")))
        await session.flush()

        stories: list[FlowStory] = []
        for i in range(50):
            story = FlowStory(
                project_id=project.id,
                title=f"{DEMAND_TITLES[i % len(DEMAND_TITLES)]}（测试{i + 1:02d}）",
                description=f"{SEED_MARK} 需求测试数据 #{i + 1}",
                state=STORY_STATES[i % len(STORY_STATES)],
                priority=(i % 4) + 1,
                submitter_id=pick_member(member_ids, i),
                pm_id=pick_member(member_ids, i + 1),
                reviewer_id=pick_member(member_ids, i + 2),
                deadline=datetime.utcnow() + timedelta(days=(i % 30) + 1),
            )
            session.add(story)
            stories.append(story)
        await session.flush()

        tasks: list[FlowTask] = []
        task_types = ["frontend", "backend", "fullstack", "test"]
        for i in range(50):
            task = FlowTask(
                story_id=stories[i].id,
                title=f"{TASK_TITLES[i % len(TASK_TITLES)]}（测试{i + 1:02d}）",
                description=f"{SEED_MARK} 任务测试数据 #{i + 1}",
                task_type=task_types[i % len(task_types)],
                state=TASK_STATES[i % len(TASK_STATES)],
                assignee_id=pick_member(member_ids, i + 3),
                estimate_hours=float((i % 5 + 1) * 2),
                actual_hours=float((i % 3) * 1.5),
                deadline=datetime.utcnow() + timedelta(days=(i % 20) + 1),
            )
            session.add(task)
            tasks.append(task)
        await session.flush()

        for i in range(50):
            bug = FlowBug(
                story_id=stories[i].id,
                task_id=tasks[i].id,
                title=f"{BUG_TITLES[i % len(BUG_TITLES)]}（测试{i + 1:02d}）",
                description=f"{SEED_MARK} 缺陷测试数据 #{i + 1}",
                severity=(i % 4) + 1,
                state=BUG_STATES[i % len(BUG_STATES)],
                reporter_id=pick_member(member_ids, i + 4),
                assignee_id=pick_member(member_ids, i + 5),
                developer_id=pick_member(member_ids, i + 6),
            )
            session.add(bug)

        await session.commit()

        print(f"Seed completed: stories=50, tasks=50, bugs=50, project={project.name}({project.id})")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
