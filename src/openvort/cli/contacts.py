"""Contacts management commands."""

import click

from openvort.cli import _run_async


@click.group()
def contacts():
    """通讯录管理"""
    pass


@contacts.command("sync")
@click.option("--platform", default=None, help="指定平台（wecom/zentao/...），不指定则同步全部")
def contacts_sync(platform):
    """从外部平台同步通讯录"""
    _run_async(_contacts_sync(platform))


async def _contacts_sync(platform: str | None):
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory
    from openvort.plugin import PluginLoader, PluginRegistry
    from openvort.utils.logging import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)

    await init_db(settings.database_url)

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    # 收集所有 SyncProvider
    providers = []
    for ch in registry.list_channels():
        p = ch.get_sync_provider()
        if p and (platform is None or p.platform == platform):
            providers.append(p)

    # 从 loader 收集 plugin 的 provider（需要访问 plugin 实例）
    for plugin_instance in loader.get_plugins():
        p = plugin_instance.get_sync_provider()
        if p and (platform is None or p.platform == platform):
            providers.append(p)

    if not providers:
        click.echo(f"未找到可用的同步源{f' (platform={platform})' if platform else ''}")
        return

    service = ContactService(get_session_factory(), settings.contacts.auto_match_threshold)

    for provider in providers:
        click.echo(f"同步 {provider.platform} ...")
        try:
            stats = await service.sync_from_provider(provider)
            click.echo(
                f"  ✅ 新建 {stats['created']}, 更新 {stats['updated']}, "
                f"自动关联 {stats['matched']}, 待确认 {stats['pending']}, "
                f"跳过 {stats.get('skipped', 0)}"
            )
        except Exception as e:
            click.echo(f"  ❌ 同步失败: {e}")

    from openvort.db import close_db
    await close_db()


@contacts.command("list")
@click.option("--status", default="active", help="成员状态过滤 (active/inactive)")
def contacts_list(status):
    """列出通讯录成员"""
    _run_async(_contacts_list(status))


async def _contacts_list(status: str):
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory

    settings = get_settings()
    await init_db(settings.database_url)

    service = ContactService(get_session_factory())
    members = await service.list_members(status=status)

    if not members:
        click.echo("通讯录为空")
        return

    click.echo(f"共 {len(members)} 位成员:\n")
    for m in members:
        identities = await service.get_member_identities(m.id)
        platforms = ", ".join(f"{i.platform}:{i.platform_user_id}" for i in identities)
        click.echo(f"  {m.name:12s} {m.email or '-':24s} {m.phone or '-':14s} [{platforms}]")

    from openvort.db import close_db
    await close_db()


@contacts.command("match")
def contacts_match():
    """查看待确认的匹配建议"""
    _run_async(_contacts_match())


async def _contacts_match():
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory

    settings = get_settings()
    await init_db(settings.database_url)

    service = ContactService(get_session_factory())
    suggestions = await service.list_pending_suggestions()

    if not suggestions:
        click.echo("没有待确认的匹配建议")
        return

    click.echo(f"共 {len(suggestions)} 条待确认:\n")
    for s in suggestions:
        click.echo(
            f"  [{s.id}] {s.match_type} (置信度 {s.confidence:.2f}) "
            f"identity#{s.source_identity_id} -> member#{s.target_member_id[:8]}"
        )

    click.echo("\n使用 `openvort contacts accept <id>` 或 `openvort contacts reject <id>` 处理")

    from openvort.db import close_db
    await close_db()


@contacts.command("accept")
@click.argument("suggestion_id", type=int)
def contacts_accept(suggestion_id):
    """接受匹配建议"""
    _run_async(_contacts_accept(suggestion_id))


async def _contacts_accept(suggestion_id: int):
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory

    settings = get_settings()
    await init_db(settings.database_url)

    service = ContactService(get_session_factory())
    ok = await service.accept_suggestion(suggestion_id, resolved_by="cli")

    click.echo(f"{'✅ 已接受' if ok else '❌ 操作失败（建议不存在或已处理）'}")

    from openvort.db import close_db
    await close_db()


@contacts.command("reject")
@click.argument("suggestion_id", type=int)
def contacts_reject(suggestion_id):
    """拒绝匹配建议"""
    _run_async(_contacts_reject(suggestion_id))


async def _contacts_reject(suggestion_id: int):
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory

    settings = get_settings()
    await init_db(settings.database_url)

    service = ContactService(get_session_factory())
    ok = await service.reject_suggestion(suggestion_id, resolved_by="cli")

    click.echo(f"{'✅ 已拒绝' if ok else '❌ 操作失败（建议不存在或已处理）'}")

    from openvort.db import close_db
    await close_db()
