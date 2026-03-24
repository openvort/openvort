"""Doctor command: system diagnostics."""

import click

from openvort.cli import _run_async


@click.command()
def doctor_cmd():
    """诊断系统配置和连接状态"""
    _run_async(_doctor())


async def _doctor():
    from openvort.config.settings import get_settings
    from openvort.utils.logging import setup_logging

    settings = get_settings()
    setup_logging("WARNING")

    click.echo("🩺 OpenVort Doctor\n")
    issues = []

    # 1. LLM 配置检查
    click.echo("── LLM 配置 ──")
    if not settings.llm.api_key:
        issues.append("LLM API Key 未配置")
        click.echo("  ❌ API Key 未配置")
    else:
        click.echo(f"  ✅ Provider: {settings.llm.provider}")
        click.echo(f"  ✅ Model: {settings.llm.model}")
        # 尝试连接
        try:
            from openvort.core.engine.llm import create_provider
            provider = create_provider(
                settings.llm.provider, settings.llm.api_key,
                settings.llm.api_base, timeout=10,
            )
            click.echo("  ✅ API 连接正常")
            await provider.close()
        except Exception as e:
            issues.append(f"LLM API 连接失败: {e}")
            click.echo(f"  ❌ API 连接失败: {e}")

    # 2. 数据库检查
    click.echo("\n── 数据库 (PostgreSQL) ──")
    db_url = settings.database_url
    click.echo(f"  URL: {db_url.split('@')[-1] if '@' in db_url else db_url.split('://')[0]}")
    try:
        from openvort.db import init_db, get_session
        await init_db(db_url)
        async with get_session() as session:
            from sqlalchemy import text
            row = await session.execute(text("SELECT version()"))
            pg_version = row.scalar()
            click.echo(f"  ✅ 连接正常: {pg_version}")
    except Exception as e:
        issues.append(f"数据库连接失败: {e}")
        click.echo(f"  ❌ 连接失败: {e}")
        click.echo("     提示: docker compose -f docker-compose.dev.yml up -d 可启动本地 PostgreSQL")

    # 3. 通道配置检查
    click.echo("\n── 通道配置 ──")
    from openvort.plugin import PluginLoader, PluginRegistry
    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    channels = registry.list_channels()
    if not channels:
        click.echo("  ⚠️ 未发现任何 Channel 插件")
    for ch in channels:
        if ch.is_configured():
            click.echo(f"  ✅ {ch.name} ({ch.display_name}) — 已配置")
            try:
                result = await ch.test_connection()
                if result.get("ok"):
                    click.echo(f"     连接测试: ✅ {result.get('message', '')}")
                else:
                    issues.append(f"{ch.name} 连接失败: {result.get('message', '')}")
                    click.echo(f"     连接测试: ❌ {result.get('message', '')}")
            except Exception as e:
                click.echo(f"     连接测试: ⚠️ 跳过 ({e})")
        else:
            click.echo(f"  ⚠️ {ch.name} ({ch.display_name}) — 未配置")

    # 4. 安全策略检查
    click.echo("\n── 安全策略 ──")
    if not settings.contacts.admin_user_ids:
        issues.append("未配置管理员 user_id")
        click.echo("  ⚠️ 未配置管理员 user_id (OPENVORT_CONTACTS_ADMIN_USER_IDS)")
    else:
        click.echo(f"  ✅ 管理员: {settings.contacts.admin_user_ids}")

    if settings.web.enabled:
        weak_passwords = {"openvort", "admin", "password", "123456", "12345678"}
        dp = settings.web.default_password
        if dp in weak_passwords or len(dp) < 8:
            issues.append("Web 面板管理员初始密码过弱")
            click.echo(f"  ⚠️ Web 面板管理员初始密码过弱（建议修改 OPENVORT_WEB_DEFAULT_PASSWORD 为 8 位以上强密码）")
        else:
            click.echo("  ✅ Web 面板管理员初始密码已自定义")

    # 6. 插件检查
    click.echo("\n── 插件 ──")
    plugins = registry.list_plugins()
    tools = registry.list_tools()
    click.echo(f"  ✅ {len(plugins)} 个 Plugin, {len(tools)} 个 Tool")

    # 7. AI 编码环境
    click.echo("\n── AI 编码环境 ──")
    try:
        from openvort.core.execution.coding_env import CodingEnvironment, EnvMode
        env = CodingEnvironment()
        status = await env.get_status()
        if status.mode != EnvMode.UNAVAILABLE:
            click.echo(f"  ✅ 模式: {status.mode.value}")
            for name, ts in status.cli_tools.items():
                if ts.installed:
                    click.echo(f"     {name}: {ts.version or '已安装'}")
            for name, configured in status.api_keys.items():
                if configured:
                    click.echo(f"     {name} API Key: 已配置")
        else:
            click.echo("  ⚠️ 未配置（可选功能）")
            click.echo("     配置后运行: openvort coding setup")
    except Exception as e:
        click.echo(f"  ⚠️ 检测跳过: {e}")

    # 总结
    click.echo("\n" + "=" * 40)
    if issues:
        click.echo(f"⚠️ 发现 {len(issues)} 个问题:\n")
        for i, issue in enumerate(issues, 1):
            click.echo(f"  {i}. {issue}")
    else:
        click.echo("✅ 一切正常！")

    try:
        from openvort.db import close_db
        await close_db()
    except Exception:
        pass
