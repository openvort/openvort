"""Channel management commands."""

import click

from openvort.cli import _run_async


@click.group()
def channels():
    """管理 IM 通道"""
    pass


@channels.command("list")
def channels_list():
    """列出已配置的通道"""
    from openvort.plugin import PluginLoader, PluginRegistry

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    chs = registry.list_channels()
    if not chs:
        click.echo("未发现任何 Channel 插件")
        return

    click.echo(f"已注册 {len(chs)} 个 Channel:\n")
    for ch in chs:
        status = "✅ 已配置" if ch.is_configured() else "❌ 未配置"
        click.echo(f"  {ch.name:12s} {ch.display_name:10s} {status}")


@channels.command("test")
@click.argument("channel_name")
def channels_test(channel_name):
    """测试通道连通性"""
    _run_async(_test_channel(channel_name))


async def _test_channel(name: str):
    from openvort.plugin import PluginLoader, PluginRegistry

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    ch = registry.get_channel(name)
    if not ch:
        click.echo(f"未找到 Channel: {name}")
        return

    if not ch.is_configured():
        click.echo(f"Channel '{name}' 未配置，请在 .env 或环境变量中设置对应的配置项")
        return

    click.echo(f"测试 {name} 连通性...")
    if hasattr(ch, "api"):
        ok = await ch.api.health_check()
        click.echo(f"  {'✅ 连接成功' if ok else '❌ 连接失败'}")
    else:
        click.echo("  ⚠️ 该 Channel 不支持连通性测试")
