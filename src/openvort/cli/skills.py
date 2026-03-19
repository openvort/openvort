"""Skills management commands."""

from pathlib import Path

import click


@click.group()
def skills():
    """管理 Skill（知识注入）"""
    pass


@skills.command("list")
def skills_list():
    """列出所有内置 Skill"""
    from openvort.skill.loader import _parse_skill_file
    # Path adjusted: cli/skills.py -> parent.parent -> openvort/
    builtin_dir = Path(__file__).parent.parent / "skills"
    if not builtin_dir.exists():
        click.echo("未发现任何 Skill")
        return

    count = 0
    for skill_dir in sorted(builtin_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        parsed = _parse_skill_file(skill_file)
        if parsed:
            status = "✅ 启用" if parsed["enabled"] else "❌ 禁用"
            click.echo(f"  {parsed['name']:20s} {parsed['description'][:40]:40s} {status}")
            count += 1

    click.echo(f"\n共 {count} 个内置 Skill")
    click.echo("公共和个人 Skill 请通过 Web 管理面板管理")
