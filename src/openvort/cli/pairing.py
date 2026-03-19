"""DM pairing management commands."""

import click


@click.group()
def pairing():
    """DM 配对管理"""
    pass


@pairing.command("approve")
@click.argument("code")
def pairing_approve(code):
    """批准配对码"""
    from openvort.core.messaging.pairing import PairingManager
    manager = PairingManager()
    ok, msg = manager.approve(code, approved_by="cli")
    click.echo(f"{'✅' if ok else '❌'} {msg}")


@pairing.command("reject")
@click.argument("code")
def pairing_reject(code):
    """拒绝配对码"""
    from openvort.core.messaging.pairing import PairingManager
    manager = PairingManager()
    ok, msg = manager.reject(code)
    click.echo(f"{'✅' if ok else '❌'} {msg}")


@pairing.command("list")
def pairing_list():
    """列出待审批的配对请求"""
    from openvort.core.messaging.pairing import PairingManager
    manager = PairingManager()
    pending = manager.list_pending()
    if not pending:
        click.echo("没有待审批的配对请求")
        return
    click.echo(f"待审批 {len(pending)} 条:\n")
    for p in pending:
        click.echo(f"  🔑 {p['code']}  {p['channel']}:{p['user_id']}  (剩余 {p['remaining_seconds']}s)")


@pairing.command("allowlist")
def pairing_allowlist():
    """查看白名单"""
    from openvort.core.messaging.pairing import PairingManager
    manager = PairingManager()
    items = manager.list_allowlist()
    if not items:
        click.echo("白名单为空")
        return
    click.echo(f"白名单 {len(items)} 条:\n")
    for item in items:
        click.echo(f"  {item['channel']}:{item['user_id']}  (by {item.get('approved_by', '?')})")
