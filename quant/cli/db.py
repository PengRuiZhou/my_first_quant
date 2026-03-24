"""数据库操作命令"""

from quant.cli.console import console


def db(command: str) -> None:
    """数据库操作

    Commands:
        create: 创建所有表
        drop: 删除所有表
    """
    from quant.core import get_settings
    from quant.data.models import Base, get_engine

    settings = get_settings()
    engine = get_engine(settings.db.url)

    if command == "create":
        Base.metadata.create_all(engine)
        console.print("[green]数据库表创建成功[/green]")
    elif command == "drop":
        Base.metadata.drop_all(engine)
        console.print("[yellow]数据库表已删除[/yellow]")
    else:
        console.print(f"[red]未知命令: {command}[/red]")
