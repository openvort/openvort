"""Seed VortGit demo repos linked to the VortMall project.

Idempotent — uses SEED_MARK in description for cleanup.
Requires: seed_demo_org.py + seed_vortflow_test_data.py run first.

Usage:
    python scripts/seed_vortgit_repos.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from openvort.config.settings import Settings
from openvort.contacts.models import Member
from openvort.db.engine import close_db, get_session_factory, init_db
from openvort.plugins.vortflow.models import FlowProject
from openvort.plugins.vortgit.models import GitProvider, GitRepo, GitRepoMember

SEED_MARK = "[SEED_VORTGIT]"

GITHUB_ORG = "vortmall"

PROVIDER_SEED = {
    "name": "VortMall GitHub",
    "platform": "github",
    "api_base": "https://api.github.com",
}

REPOS = [
    {
        "name": "vortmall-gateway",
        "full_name": f"{GITHUB_ORG}/vortmall-gateway",
        "description": "API 网关 — 统一鉴权、限流、灰度路由",
        "language": "Go",
        "repo_type": "backend",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-gateway.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-gateway.git",
    },
    {
        "name": "vortmall-order-service",
        "full_name": f"{GITHUB_ORG}/vortmall-order-service",
        "description": "订单服务 — 下单、支付回调、超时取消、退款",
        "language": "Java",
        "repo_type": "backend",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-order-service.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-order-service.git",
    },
    {
        "name": "vortmall-product-service",
        "full_name": f"{GITHUB_ORG}/vortmall-product-service",
        "description": "商品服务 — SKU 管理、库存预占、搜索索引",
        "language": "Java",
        "repo_type": "backend",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-product-service.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-product-service.git",
    },
    {
        "name": "vortmall-user-service",
        "full_name": f"{GITHUB_ORG}/vortmall-user-service",
        "description": "用户服务 — 注册登录、会员成长值、积分体系",
        "language": "Java",
        "repo_type": "backend",
        "default_branch": "develop",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-user-service.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-user-service.git",
    },
    {
        "name": "vortmall-payment-service",
        "full_name": f"{GITHUB_ORG}/vortmall-payment-service",
        "description": "支付服务 — 多渠道支付、分账结算、对账补偿",
        "language": "Java",
        "repo_type": "backend",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-payment-service.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-payment-service.git",
    },
    {
        "name": "vortmall-marketing-service",
        "full_name": f"{GITHUB_ORG}/vortmall-marketing-service",
        "description": "营销服务 — 优惠券、满减活动、秒杀、积分商城",
        "language": "Java",
        "repo_type": "backend",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-marketing-service.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-marketing-service.git",
    },
    {
        "name": "vortmall-web",
        "full_name": f"{GITHUB_ORG}/vortmall-web",
        "description": "买家端 Web — Vue 3 + TypeScript SPA",
        "language": "TypeScript",
        "repo_type": "frontend",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-web.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-web.git",
    },
    {
        "name": "vortmall-admin",
        "full_name": f"{GITHUB_ORG}/vortmall-admin",
        "description": "商家后台 — React + Ant Design Pro 管理面板",
        "language": "TypeScript",
        "repo_type": "frontend",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-admin.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-admin.git",
    },
    {
        "name": "vortmall-mobile",
        "full_name": f"{GITHUB_ORG}/vortmall-mobile",
        "description": "买家端 App — Flutter 跨平台（iOS + Android）",
        "language": "Dart",
        "repo_type": "mobile",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-mobile.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-mobile.git",
    },
    {
        "name": "vortmall-infra",
        "full_name": f"{GITHUB_ORG}/vortmall-infra",
        "description": "基础设施 — Terraform + K8s manifests + CI/CD pipelines",
        "language": "HCL",
        "repo_type": "infra",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-infra.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-infra.git",
    },
    {
        "name": "vortmall-docs",
        "full_name": f"{GITHUB_ORG}/vortmall-docs",
        "description": "项目文档 — 架构设计、API 文档、运维手册",
        "language": "Markdown",
        "repo_type": "docs",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-docs.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-docs.git",
    },
    {
        "name": "vortmall-common",
        "full_name": f"{GITHUB_ORG}/vortmall-common",
        "description": "公共库 — 通用工具类、DTO 定义、异常体系",
        "language": "Java",
        "repo_type": "backend",
        "default_branch": "main",
        "clone_url": f"https://github.com/{GITHUB_ORG}/vortmall-common.git",
        "ssh_url": f"git@github.com:{GITHUB_ORG}/vortmall-common.git",
    },
]

ACCESS_LEVELS = ["admin", "write", "write", "read"]


def _uuid() -> str:
    return uuid.uuid4().hex


async def main() -> None:
    settings = Settings()
    await init_db(settings.database_url)
    sf = get_session_factory()

    async with sf() as session:
        members = (
            await session.execute(select(Member).order_by(Member.created_at.asc()))
        ).scalars().all()
        member_ids = [m.id for m in members]
        member_names = {m.id: m.name for m in members}
        print(f"Found {len(member_ids)} members")

        project = (
            await session.execute(
                select(FlowProject)
                .where(FlowProject.name.ilike("%VortMall%"))
                .order_by(FlowProject.created_at.desc())
            )
        ).scalars().first()
        if not project:
            print("VortMall project not found — run seed_vortflow_test_data.py first")
            await close_db()
            return
        print(f"Using project: {project.name} ({project.id})")

        # --- Cleanup previous seed data ---
        seeded_repos = (
            await session.execute(
                select(GitRepo.id).where(GitRepo.description.ilike(f"%{SEED_MARK}%"))
            )
        ).scalars().all()

        if seeded_repos:
            await session.execute(
                delete(GitRepoMember).where(GitRepoMember.repo_id.in_(seeded_repos))
            )
            await session.execute(
                delete(GitRepo).where(GitRepo.id.in_(seeded_repos))
            )
            print(f"Cleaned {len(seeded_repos)} previous seeded repos")

        seeded_provider = await session.scalar(
            select(GitProvider).where(GitProvider.name == PROVIDER_SEED["name"])
        )
        if seeded_provider:
            remaining = await session.scalar(
                select(func.count()).where(GitRepo.provider_id == seeded_provider.id)
            )
            if not remaining:
                await session.delete(seeded_provider)
                print("Cleaned previous seeded provider")
            else:
                print(f"Kept provider (still has {remaining} non-seed repos)")

        await session.flush()

        # --- Create provider ---
        provider = await session.scalar(
            select(GitProvider).where(GitProvider.name == PROVIDER_SEED["name"])
        )
        if not provider:
            provider = GitProvider(
                id=_uuid(),
                name=PROVIDER_SEED["name"],
                platform=PROVIDER_SEED["platform"],
                api_base=PROVIDER_SEED["api_base"],
                access_token="",
                is_default=False,
            )
            session.add(provider)
            await session.flush()
            print(f"Created provider: {provider.name} ({provider.id})")
        else:
            print(f"Reusing provider: {provider.name} ({provider.id})")

        # --- Create repos ---
        now = datetime.utcnow()
        repos: list[GitRepo] = []
        for i, spec in enumerate(REPOS):
            created = now - timedelta(days=len(REPOS) - i, hours=i * 3)
            synced = now - timedelta(hours=i * 2 + 1)
            repo = GitRepo(
                id=_uuid(),
                provider_id=provider.id,
                project_id=project.id,
                name=spec["name"],
                full_name=spec["full_name"],
                clone_url=spec["clone_url"],
                ssh_url=spec["ssh_url"],
                default_branch=spec["default_branch"],
                description=f"{spec['description']}\n{SEED_MARK}",
                language=spec["language"],
                repo_type=spec["repo_type"],
                is_private=True,
                webhook_secret=uuid.uuid4().hex[:16],
                last_synced_at=synced,
                created_at=created,
            )
            session.add(repo)
            repos.append(repo)

        await session.flush()
        print(f"Inserted {len(repos)} repos")

        # --- Assign members to repos ---
        total_members_added = 0
        if member_ids:
            for ri, repo in enumerate(repos):
                count = min(3 + (ri % 4), len(member_ids))
                for mi in range(count):
                    mid = member_ids[(ri + mi) % len(member_ids)]
                    level = ACCESS_LEVELS[mi % len(ACCESS_LEVELS)]
                    rm = GitRepoMember(
                        id=_uuid(),
                        repo_id=repo.id,
                        member_id=mid,
                        access_level=level,
                        platform_username=member_names.get(mid, ""),
                    )
                    session.add(rm)
                    total_members_added += 1

        await session.commit()
        print(f"Assigned {total_members_added} repo-member bindings")
        print(f"\nSeed completed: provider=1, repos={len(repos)}")
        print(f"All repos linked to project: {project.name}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
