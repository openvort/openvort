"""Marketplace commands: search, install, list, uninstall, update, publish, sync."""

from pathlib import Path

import click

from openvort.cli import _run_async


@click.group()
def marketplace():
    """扩展市场（从 openvort.com 安装 Skill/Plugin）"""
    pass


@marketplace.command("search")
@click.argument("query", default="")
@click.option("--type", "-t", "ext_type", default="all", help="Filter: all/skill/plugin")
@click.option("--limit", "-n", default=10, help="Max results")
def marketplace_search(query, ext_type, limit):
    """搜索扩展市场"""
    _run_async(_marketplace_search(query, ext_type, limit))


async def _marketplace_search(query: str, ext_type: str, limit: int):
    from openvort.marketplace.client import MarketplaceClient

    client = MarketplaceClient()

    try:
        result = await client.search(query=query, type=ext_type, limit=limit)
        items = result.get("items", [])
        total = result.get("total", 0)
        if not items:
            click.echo("未找到相关扩展")
            return

        click.echo(f"找到 {total} 个扩展:\n")
        for item in items:
            t = "Plugin" if item.get("type") == "plugin" else "Skill"
            name = item.get("displayName", item.get("name", "?"))
            author = item.get("author", "?")
            ver = item.get("version", "?")
            dl = item.get("downloads", 0)
            click.echo(f"  [{t:6s}] {name:30s} by {author:16s} v{ver}  ({dl} downloads)")
    finally:
        await client.close()


@marketplace.command("install")
@click.argument("ext_type", type=click.Choice(["skill", "plugin"]))
@click.argument("ref")
def marketplace_install(ext_type, ref):
    """安装扩展 (openvort marketplace install skill author/slug)"""
    _run_async(_marketplace_install(ext_type, ref))


async def _marketplace_install(ext_type: str, ref: str):
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient()
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    parts = ref.split("/", 1)
    author = parts[0] if len(parts) > 1 else ""
    slug = parts[-1]

    try:
        if ext_type == "skill":
            result = await installer.install_skill(slug, author=author)
            method = " (bundle)" if result.get("has_bundle") else ""
            click.echo(f"Skill 安装成功{method}: {result['name']} v{result['version']}")
        else:
            result = await installer.install_plugin(slug, author=author)
            method = result.get("method", "pip")
            name = result.get("packageName", result.get("slug", slug))
            click.echo(f"Plugin 安装成功 ({method}): {name} v{result['version']}")
            if result.get("restart_required"):
                click.echo("  需要重启 OpenVort 服务以加载新插件")
    except Exception as e:
        click.echo(f"安装失败: {e}", err=True)
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


@marketplace.command("list")
def marketplace_list():
    """列出已安装的市场扩展"""
    _run_async(_marketplace_list())


async def _marketplace_list():
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient()
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    try:
        items = await installer.list_installed()
        if not items:
            click.echo("未安装任何市场扩展")
            return

        click.echo(f"已安装 {len(items)} 个市场扩展:\n")
        for item in items:
            status = "启用" if item.get("enabled") else "禁用"
            click.echo(
                f"  {item['name']:24s} {item.get('author', ''):16s}/"
                f"{item.get('slug', ''):20s} v{item.get('version', '?')}  [{status}]"
            )
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


@marketplace.command("uninstall")
@click.argument("slug")
def marketplace_uninstall(slug):
    """卸载市场扩展"""
    _run_async(_marketplace_uninstall(slug))


async def _marketplace_uninstall(slug: str):
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient()
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    try:
        result = await installer.uninstall_skill(slug)
        click.echo(f"已卸载: {result['name']} ({slug})")
    except ValueError as e:
        click.echo(f"卸载失败: {e}", err=True)
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


@marketplace.command("update")
def marketplace_update():
    """检查并更新市场扩展"""
    _run_async(_marketplace_update())


async def _marketplace_update():
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient()
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    try:
        updates = await installer.check_updates()
        if not updates:
            click.echo("所有市场扩展均为最新版本")
            return

        click.echo(f"发现 {len(updates)} 个可更新:\n")
        for u in updates:
            extra = " (hash changed)" if u.get("hash_changed") else ""
            click.echo(f"  [{u.get('type', 'skill'):6s}] {u['name']:24s} {u['local_version']} -> {u['remote_version']}{extra}")

        if click.confirm("\n是否全部更新?"):
            for u in updates:
                try:
                    if u.get("type") == "plugin":
                        result = await installer.install_plugin(u["slug"])
                    else:
                        result = await installer.install_skill(u["slug"])
                    click.echo(f"  已更新: {result.get('name', u['slug'])} v{result.get('version', '?')}")
                except Exception as e:
                    click.echo(f"  更新 {u['slug']} 失败: {e}")
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


@marketplace.command("publish")
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("--type", "-t", "ext_type", default="auto", help="Extension type: auto/skill/plugin")
@click.option("--slug", "-s", default="", help="Extension slug (default: folder name)")
@click.option("--username", "-u", default="", help="Marketplace username")
@click.option("--password", "-p", default="", help="Marketplace password (or set OPENVORT_MARKETPLACE_TOKEN)")
def marketplace_publish(folder, ext_type, slug, username, password):
    """发布本地文件夹到扩展市场 (openvort marketplace publish ./my-skill)"""
    _run_async(_marketplace_publish(folder, ext_type, slug, username, password))


async def _marketplace_publish(folder: str, ext_type: str, slug: str, username: str, password: str):
    import os
    import tempfile
    import zipfile
    import hashlib
    from pathlib import Path
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient

    settings = get_settings()
    folder_path = Path(folder).resolve()
    slug = slug or folder_path.name.lower().replace("_", "-").replace(" ", "-")

    # Auto-detect type
    if ext_type == "auto":
        skill_md = _find_publish_file(folder_path, "SKILL.md")
        pyproject = folder_path / "pyproject.toml"
        setup_py = folder_path / "setup.py"
        if skill_md:
            ext_type = "skill"
        elif pyproject.exists() or setup_py.exists():
            ext_type = "plugin"
        else:
            ext_type = "skill"
        click.echo(f"自动检测类型: {ext_type}")

    # Read metadata
    skill_md_path = _find_publish_file(folder_path, "SKILL.md")
    readme_path = _find_publish_file(folder_path, "README.md")
    manifest_path = folder_path / "manifest.json"

    content = ""
    readme = ""
    manifest: dict = {}

    if skill_md_path:
        content = skill_md_path.read_text(encoding="utf-8")
        click.echo(f"  读取 SKILL.md ({len(content)} chars)")
    if readme_path:
        readme = readme_path.read_text(encoding="utf-8")
        click.echo(f"  读取 README.md ({len(readme)} chars)")
    if manifest_path.exists():
        import json
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        click.echo(f"  读取 manifest.json")

    # Package to zip
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in folder_path.rglob("*"):
            if p.is_file():
                rel = p.relative_to(folder_path)
                # Skip common unwanted files
                parts = rel.parts
                if any(part.startswith(".") for part in parts):
                    continue
                if any(part in ("__pycache__", "node_modules", ".git", ".venv", "venv") for part in parts):
                    continue
                zf.write(p, rel)

    zip_size = tmp_path.stat().st_size
    zip_hash = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
    click.echo(f"  打包完成: {zip_size / 1024:.1f} KB, SHA-256: {zip_hash[:16]}...")

    # Auth
    token = ""
    if username and password:
        import base64
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
    elif os.environ.get("OPENVORT_MARKETPLACE_TOKEN"):
        token = os.environ["OPENVORT_MARKETPLACE_TOKEN"]

    if not token:
        username = click.prompt("Marketplace 用户名")
        password = click.prompt("Marketplace 密码", hide_input=True)
        import base64
        token = base64.b64encode(f"{username}:{password}".encode()).decode()

    client = MarketplaceClient(token=token)

    try:
        click.echo("上传 Bundle...")
        bundle_info = await client.upload_bundle(slug, ext_type, tmp_path)
        click.echo(f"  Bundle 上传成功: {bundle_info.get('bundleUrl', '')}")

        # Build extension body
        display_name = manifest.get("displayName", slug.replace("-", " ").title())
        body = {
            "type": ext_type,
            "slug": slug,
            "name": slug,
            "displayName": display_name,
            "description": manifest.get("description", ""),
            "readme": readme,
            "content": content,
            "version": manifest.get("version", "1.0.0"),
            "icon": manifest.get("icon", "i-heroicons-academic-cap" if ext_type == "skill" else "i-heroicons-puzzle-piece"),
            "category": manifest.get("category", "general"),
            "tags": manifest.get("tags", []),
            "license": manifest.get("license", "MIT-0"),
            "homepage": manifest.get("homepage", ""),
            "repository": manifest.get("repository", ""),
            "bundleUrl": bundle_info.get("bundleUrl"),
            "bundleHash": bundle_info.get("bundleHash"),
            "bundleSize": bundle_info.get("bundleSize"),
        }

        if ext_type == "skill":
            body["skillType"] = manifest.get("skillType", "workflow")
        elif ext_type == "plugin":
            body["packageName"] = manifest.get("packageName", "")
            body["entryPoint"] = manifest.get("entryPoint", "")
            body["pythonRequires"] = manifest.get("pythonRequires", "")
            body["dependencies"] = manifest.get("dependencies", [])
            body["toolsCount"] = manifest.get("toolsCount", 0)
            body["promptsCount"] = manifest.get("promptsCount", 0)
            body["configSchema"] = manifest.get("configSchema", [])

        body["compatVersion"] = manifest.get("compatVersion", "")

        click.echo("发布扩展...")
        result = await client.publish_extension(body)
        click.echo(f"\n发布成功! {result.get('author', '')}/{result.get('slug', slug)}")
        click.echo(f"  版本: v{result.get('version', '1.0.0')}")
        click.echo(f"  查看: https://openvort.com/{result.get('author', '')}/{result.get('slug', slug)}")
    except Exception as e:
        click.echo(f"发布失败: {e}", err=True)
        raise SystemExit(1)
    finally:
        await client.close()
        tmp_path.unlink(missing_ok=True)


@marketplace.command("sync")
@click.option("--all", "sync_all", is_flag=True, help="Sync all installed marketplace extensions")
def marketplace_sync(sync_all):
    """同步已安装的市场扩展（检查更新并自动安装）"""
    _run_async(_marketplace_sync(sync_all))


async def _marketplace_sync(sync_all: bool):
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient()
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    try:
        updates = await installer.check_updates()
        if not updates:
            click.echo("所有扩展已是最新版本")
            return

        click.echo(f"发现 {len(updates)} 个更新:\n")
        for u in updates:
            extra = " [content changed]" if u.get("hash_changed") else ""
            click.echo(f"  [{u.get('type', 'skill'):6s}] {u['name']:24s} {u['local_version']} -> {u['remote_version']}{extra}")

        if sync_all or click.confirm("\n是否全部更新?"):
            for u in updates:
                try:
                    if u.get("type") == "plugin":
                        result = await installer.install_plugin(u["slug"])
                    else:
                        result = await installer.install_skill(u["slug"])
                    click.echo(f"  已同步: {result.get('name', u['slug'])} v{result.get('version', '?')}")
                except Exception as e:
                    click.echo(f"  同步 {u['slug']} 失败: {e}")
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


def _find_publish_file(folder: Path, name: str) -> Path | None:
    """Find a file by name (case-insensitive) in the folder root."""
    lower = name.lower()
    for p in folder.iterdir():
        if p.is_file() and p.name.lower() == lower:
            return p
    return None
