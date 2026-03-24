"""数据获取命令

提供 quant fetch 命令，从数据源获取各类数据并存储到数据库。
"""

import asyncio

from typer import Argument, Option

from quant.cli.console import console


def fetch(
    data_type: str = Argument(
        ...,
        help="数据类型: stock_list/daily/index/basic/calendar/financial",
    ),
    start_date: str | None = Option(
        None, "--start", "-s", help="开始日期 (YYYYMMDD)"
    ),
    end_date: str | None = Option(
        None, "--end", "-e", help="结束日期 (YYYYMMDD)"
    ),
    source: str = Option(
        "tushare", "--source", "-src", help="数据源: tushare/akshare"
    ),
) -> None:
    """获取数据

    支持的数据类型:
    - stock_list: 股票列表
    - daily: 日线行情
    - index: 指数行情
    - basic: 每日指标
    - calendar: 交易日历
    - financial: 财务指标
    """
    _run_fetch(data_type, start_date, end_date, source)


def _run_fetch(
    data_type: str,
    start_date: str | None,
    end_date: str | None,
    source: str,
) -> None:
    """执行数据获取"""
    from quant.data.etl.cleaners import DuplicateCleaner, MissingValueCleaner
    from quant.data.etl.pipeline import ETLPipeline
    from quant.data.sources.tushare_client import TushareClient
    from quant.data.storage.repository import DataRepository

    async def _fetch_async():
        # 初始化数据源和仓库
        data_source = TushareClient()
        repository = DataRepository()

        # 创建 ETL 管道
        pipeline = (
            ETLPipeline()
            .add_cleaner(DuplicateCleaner())
            .add_cleaner(MissingValueCleaner(strategy="ffill", limit=5))
        )

        console.print(f"[blue]正在从 {source} 获取 {data_type} 数据...[/blue]")

        try:
            if data_type == "stock_list":
                df = await data_source.get_stock_list()
                count = await repository.upsert_stock_info(df)
                console.print(f"[green]股票列表更新完成，插入 {count} 条记录[/green]")

            elif data_type == "daily":
                df = await data_source.get_daily_quotes(
                    start_date=start_date, end_date=end_date
                )
                if not df.empty:
                    df = pipeline.run(df)
                count = await repository.upsert_daily_quotes(df)
                console.print(f"[green]日线行情更新完成，插入 {count} 条记录[/green]")

            elif data_type == "index":
                df = await data_source.get_index_quotes(
                    start_date=start_date, end_date=end_date
                )
                count = await repository.upsert_index_quotes(df)
                console.print(f"[green]指数行情更新完成，插入 {count} 条记录[/green]")

            elif data_type == "basic":
                df = await data_source.get_daily_basic(
                    start_date=start_date, end_date=end_date
                )
                count = await repository.upsert_daily_basic(df)
                console.print(f"[green]每日指标更新完成，插入 {count} 条记录[/green]")

            elif data_type == "calendar":
                exchange = "SSE"
                df = await data_source.get_trade_calendar(
                    exchange=exchange, start_date=start_date, end_date=end_date
                )
                count = await repository.upsert_trade_calendar(df)
                console.print(f"[green]交易日历更新完成，插入 {count} 条记录[/green]")

            elif data_type == "financial":
                df = await data_source.get_financial_indicator(
                    start_date=start_date, end_date=end_date
                )
                count = await repository.upsert_financial_indicator(df)
                console.print(f"[green]财务指标更新完成，插入 {count} 条记录[/green]")

            else:
                console.print(f"[red]未知数据类型: {data_type}[/red]")
                console.print("支持的数据类型: stock_list, daily, index, basic, calendar, financial")

        except Exception as e:
            console.print(f"[red]获取数据失败: {e}[/red]")
            raise

    asyncio.run(_fetch_async())
