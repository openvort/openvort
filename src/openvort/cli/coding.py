"""AI coding environment management commands."""

import click

from openvort.cli import _run_async


@click.group()
def coding():
    """AI 编码环境管理"""
    pass


@coding.command("setup")
def coding_setup():
    """配置 AI 编码环境（拉取 Docker 镜像 + 配置 API Key + 验证）"""
    _run_async(_coding_setup())


async def _coding_setup():
    from openvort.core.execution.coding_env import CodingEnvironment, EnvMode
    from openvort.plugins.vortgit.config import VortGitSettings

    click.echo("🔧 AI 编码环境配置\n")

    env = CodingEnvironment()
    settings = VortGitSettings()

    # 1. Local CLI tools check
    click.echo("── 本地 CLI 工具检测 ──")
    from openvort.plugins.vortgit.cli_runner import BUILTIN_CLI_TOOLS
    import shutil
    local_found = False
    for name, spec in BUILTIN_CLI_TOOLS.items():
        path = shutil.which(spec.binary)
        if path:
            click.echo(f"  ✅ {spec.display_name}: {path}")
            local_found = True
        else:
            click.echo(f"  ⚠️  {spec.display_name}: 未安装 ({spec.install_cmd})")

    # 2. Docker check (optional if local tools found)
    click.echo("\n── Docker 检测 ──")
    docker_ready = False
    if env._is_docker_available():
        click.echo("  ✅ Docker 已安装")
        image = settings.cli_docker_image
        click.echo(f"  📦 镜像: {image}")
        pulled = await env._is_image_pulled(image)
        if pulled:
            click.echo("  ✅ 镜像已存在")
            docker_ready = True
        else:
            click.echo("  ⏳ 正在拉取（可能需要几分钟）...")
            result = await env.pull_image()
            if result.success:
                click.echo("  ✅ 镜像拉取完成")
                docker_ready = True
            else:
                click.echo(f"  ❌ 镜像拉取失败: {result.stderr[:200]}")
    else:
        click.echo("  ⚠️  Docker 未安装（可选，已安装本地 CLI 工具即可）")

    if not local_found and not docker_ready:
        click.echo("\n❌ 无可用的编码环境。请安装 CLI 工具或 Docker：")
        click.echo("   pip install aider-chat")
        click.echo("   npm install -g @anthropic-ai/claude-code")
        return

    # 3. API Key check
    click.echo("\n── API Key 配置 ──")
    click.echo("  ℹ️  API Key 通过 Web 管理界面的「模型库」配置")
    if settings.claude_code_api_key:
        click.echo("  ✅ Claude Code API Key: 已配置（环境变量）")
    if settings.aider_api_key:
        click.echo("  ✅ Aider API Key: 已配置（环境变量）")

    # 4. Verify
    click.echo("\n── 环境验证 ──")
    status = await env.get_status()
    mode = status.mode
    if mode != EnvMode.UNAVAILABLE:
        click.echo(f"  ✅ 执行模式: {mode.value}")
    else:
        click.echo("  ❌ 环境不可用，请检查上述问题")
        return

    # 5. Test execution
    click.echo("  🧪 测试执行...", nl=False)
    test_result = await env.execute(["echo", "openvort-coding-ok"])
    if test_result.success and "openvort-coding-ok" in test_result.stdout:
        click.echo(" ✅")
    else:
        click.echo(f" ❌ {test_result.stderr[:100]}")
        return

    click.echo("\n" + "=" * 40)
    click.echo("✅ AI 编码环境准备就绪！")
    click.echo("   团队成员现在可以通过对话触发代码修改了。")


@coding.command("status")
def coding_status():
    """查看 AI 编码环境状态"""
    _run_async(_coding_status())


async def _coding_status():
    from openvort.core.execution.coding_env import CodingEnvironment, EnvMode
    from openvort.plugins.vortgit.cli_runner import CLIRunner

    click.echo("🔍 AI 编码环境状态\n")

    env = CodingEnvironment()
    status = await env.get_status()

    click.echo("── 运行环境 ──")
    click.echo(f"  模式: {status.mode.value}")
    click.echo(f"  在 Docker 中运行: {'是' if status.running_in_docker else '否'}")
    click.echo(f"  Docker 可用: {'是' if status.docker_available else '否'}")
    click.echo(f"  Docker Socket: {'是' if status.docker_socket else '否'}")

    click.echo(f"\n── 编码沙箱镜像 ──")
    click.echo(f"  镜像: {status.coding_image_name}")
    click.echo(f"  已拉取: {'是' if status.coding_image_pulled else '否'}")

    click.echo(f"\n── CLI 编码工具 ──")
    runner = CLIRunner(env)
    for spec in runner.list_tools():
        ts = status.cli_tools.get(spec.name)
        if ts and ts.installed:
            click.echo(f"  ✅ {spec.display_name}: {ts.version or '已安装'}")
        else:
            click.echo(f"  ❌ {spec.display_name}: 未安装")
            click.echo(f"     安装: {spec.install_cmd}")

    click.echo(f"\n── API Key ──")
    for name, configured in status.api_keys.items():
        icon = "✅" if configured else "⚠️"
        label = "已配置" if configured else "未配置"
        click.echo(f"  {icon} {name}: {label}")

    if status.mode == EnvMode.UNAVAILABLE:
        click.echo(f"\n⚠️  编码环境不可用。运行: openvort coding setup")
