"""回测命令"""

from typer import Argument, Option

from quant.cli.console import console


def backtest(
    strategy: str = Argument(..., help="策略名称"),
    start_date: str = Option(None, "--start", "-s", help="开始日期"),
    end_date: str = Option(None, "--end", "-e", help="结束日期"),
    capital: float = Option(1_000_000, "--capital", "-c", help="初始资金"),
) -> None:
    """运行回测"""
    console.print(f"[blue]正在回测策略: {strategy}[/blue]")
    # TODO: 实现回测逻辑
    console.print("[yellow]功能开发中...[/yellow]")
