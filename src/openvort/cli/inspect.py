"""Inspection commands: tools and plugins listing."""

import click


@click.group()
def tools():
    """管理 AI 工具"""
    pass


@tools.command("list")
def tools_list():
    """列出已注册的工具"""
    from openvort.plugin import PluginLoader, PluginRegistry

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    ts = registry.list_tools()
    if not ts:
        click.echo("未发现任何 Tool 插件")
        return

    click.echo(f"已注册 {len(ts)} 个 Tool:\n")
    for t in ts:
        click.echo(f"  {t.name:30s} {t.description[:60]}")


@click.group()
def plugins():
    """管理插件"""
    pass


@plugins.command("list")
def plugins_list():
    """列出所有 Plugin（内置 + pip + 本地）"""
    from openvort.plugin import PluginLoader, PluginRegistry

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    all_plugins = registry.list_plugins()
    if not all_plugins:
        click.echo("未发现任何 Plugin")
        return

    click.echo(f"已注册 {len(all_plugins)} 个 Plugin:\n")
    for p in all_plugins:
        source_label = {"builtin": "内置", "pip": "pip", "local": "本地"}.get(p.source, p.source)
        tools_count = len(p.get_tools())
        click.echo(
            f"  {p.name:16s} {p.display_name:16s} "
            f"[{source_label:4s}] {tools_count} 个 Tool"
        )
