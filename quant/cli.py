"""命令行接口"""

import typer
from rich.console import Console

app = typer.Typer(
    name="quant",
    help="A股量化交易框架",
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """显示版本信息"""
    from quant import __version__
    console.print(f"[green]quant[/green] version: [bold]{__version__}[/bold]")


@app.command()
def init() -> None:
    """初始化项目（创建配置文件）"""
    from pathlib import Path
    import shutil

    env_example = Path(".env.example")
    env_file = Path(".env")

    if env_file.exists():
        console.print("[yellow].env 文件已存在[/yellow]")
        return

    if env_example.exists():
        shutil.copy(env_example, env_file)
        console.print("[green]已创建 .env 文件，请填写配置[/green]")
    else:
        console.print("[red].env.example 文件不存在[/red]")


@app.command()
def db(command: str) -> None:
    """数据库操作

    Commands:
        create: 创建所有表
        drop: 删除所有表
        migrate: 运行迁移
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


@app.command()
def fetch(
    source: str = typer.Argument(..., help="数据源: tushare/akshare"),
    data_type: str = typer.Argument(..., help="数据类型: stock/daily/financial"),
    start_date: str = typer.Option(None, "--start", "-s", help="开始日期"),
    end_date: str = typer.Option(None, "--end", "-e", help="结束日期"),
) -> None:
    """获取数据"""
    console.print(f"[blue]正在从 {source} 获取 {data_type} 数据...[/blue]")
    # TODO: 实现数据获取逻辑
    console.print("[yellow]功能开发中...[/yellow]")


@app.command()
def backtest(
    strategy: str = typer.Argument(..., help="策略名称"),
    start_date: str = typer.Option(None, "--start", "-s", help="开始日期"),
    end_date: str = typer.Option(None, "--end", "-e", help="结束日期"),
    capital: float = typer.Option(1_000_000, "--capital", "-c", help="初始资金"),
) -> None:
    """运行回测"""
    console.print(f"[blue]正在回测策略: {strategy}[/blue]")
    # TODO: 实现回测逻辑
    console.print("[yellow]功能开发中...[/yellow]")


def main() -> None:
    """CLI 入口"""
    app()


if __name__ == "__main__":
    main()
