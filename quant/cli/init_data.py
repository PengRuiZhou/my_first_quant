"""历史数据初始化命令"""

import asyncio

from rich.table import Table
from typer import Option

from quant.cli.console import console


def init_data(
    years: int = Option(3, "--years", "-y", help="初始化历史数据年数"),
) -> None:
    """初始化历史数据

    获取指定年数的历史数据，包括:
    - 股票列表
    - 交易日历
    - 日线行情
    - 每日指标
    - 指数行情
    """
    from quant.data.sources.tushare_client import TushareClient
    from quant.data.storage.repository import DataRepository
    from quant.data.storage.scheduler import DataScheduler

    console.print(f"[blue]开始初始化 {years} 年历史数据...[/blue]")

    async def _init():
        scheduler = DataScheduler(
            repository=DataRepository(),
            data_source=TushareClient(),
        )

        with console.status("[bold green]获取数据中...[/bold green]"):
            stats = await scheduler.init_historical_data(years=years)

        # 显示结果
        table = Table(title="初始化结果")
        table.add_column("数据类型", style="cyan")
        table.add_column("记录数", style="green")

        for data_type, count in stats.items():
            table.add_row(data_type, str(count))

        console.print(table)
        console.print("[green]历史数据初始化完成！[/green]")

    asyncio.run(_init())
