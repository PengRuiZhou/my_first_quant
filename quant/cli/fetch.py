"""数据获取命令

提供 quant fetch 命令，从数据源获取各类数据并存储到数据库。
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal

import pandas as pd
import typer
from typer import Argument, Option

from quant.cli.console import console

# 类型定义
FetchStatus = Literal["success", "empty", "failed"]
type FetchResult = tuple[str, FetchStatus, pd.DataFrame | None, str | None]
# (ts_code, status, df, error)


def fetch(
    data_type: str = Argument(
        ...,
        help="数据类型: all/stock_list/index_list/daily/index/basic/calendar/financial",
    ),
    start_date: str | None = Option(None, "--start", "-s", help="开始日期 (YYYYMMDD)"),
    end_date: str | None = Option(None, "--end", "-e", help="结束日期 (YYYYMMDD)"),
    source: str = Option("tushare", "--source", "-src", help="数据源: tushare/akshare"),
    ts_code: str | None = Option(None, "--ts-code", "-c", help="股票代码 (financial 可选，如 000001.SZ)"),
    max_workers: int = Option(20, "--max-workers", "-w", help="并发线程数 (financial 批量时使用，1-100)"),
) -> None:
    """获取数据

    支持的数据类型:
    - all: 更新所有数据（增量更新，含 financial）
    - stock_list: 股票列表
    - index_list: 指数列表
    - daily: 日线行情
    - index: 指数行情
    - basic: 每日指标
    - calendar: 交易日历
    - financial: 财务指标
      - 指定 --ts-code: 获取单个股票
      - 不指定: 并行获取所有股票（使用 --max-workers 控制并发数）

    示例:
      quant fetch financial -c 000001.SZ -s 20230101
      quant fetch financial -s 20230101 -w 10
    """
    # 参数校验
    if max_workers < 1 or max_workers > 100:
        console.print("[red]--max-workers 必须在 1-100 之间[/red]")
        raise typer.Exit(1)

    if data_type == "all":
        _run_fetch_all(start_date, end_date, source, max_workers)
    else:
        asyncio.run(_run_fetch(data_type, start_date, end_date, source, ts_code, max_workers))


def _fetch_financial_parallel(
    data_source,
    ts_codes: list[str],
    start_date: str | None,
    end_date: str | None,
    max_workers: int = 20,
) -> pd.DataFrame:
    """多线程并行获取所有股票的财务指标（纯同步函数）

    使用 ThreadPoolExecutor 真正的多线程并行，适合同步阻塞 I/O。

    线程安全设计：
    - worker 返回结构化结果，不修改共享变量
    - 主线程统一汇总 success / empty / failed
    """
    from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

    # 边界情况：空股票列表
    if not ts_codes:
        console.print("[yellow]没有可获取的股票列表[/yellow]")
        return pd.DataFrame()

    total = len(ts_codes)
    console.print(f"[blue]开始多线程并行获取 {total} 只股票的财务指标（线程数: {max_workers}）...[/blue]")

    # 直接使用 Tushare 同步 API
    pro = data_source._pro
    fields = ",".join(data_source.FINANCIAL_INDICATOR_MAP.keys())

    def fetch_one_sync(code: str) -> FetchResult:
        """单个股票获取（同步，线程安全）

        Returns:
            (ts_code, status, df, error)
            status: "success" | "empty" | "failed"
        """
        try:
            df = pro.fina_indicator(
                ts_code=code,
                start_date=start_date,
                end_date=end_date,
                fields=fields,
            )
            if df is not None and not df.empty:
                return (code, "success", df, None)
            else:
                return (code, "empty", None, None)
        except Exception as e:
            return (code, "failed", None, str(e))

    # 统计结果（主线程收集，线程安全）
    success_dfs: list[pd.DataFrame] = []
    success_count = 0
    empty_count = 0
    failed_codes: list[tuple[str, str]] = []

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("获取财务指标", total=total)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 直接提交所有任务（future_to_code 映射多余，因为 worker 已返回 code）
            futures = [executor.submit(fetch_one_sync, code) for code in ts_codes]

            for future in as_completed(futures):
                code, status, df, error = future.result()

                if status == "success":
                    success_dfs.append(df)
                    success_count += 1
                elif status == "empty":
                    empty_count += 1
                else:  # failed
                    failed_codes.append((code, error or "unknown"))

                progress.update(task, advance=1)

    # 打印结果汇总
    fail_count = len(failed_codes)
    console.print(
        f"[green]✓ 成功: {success_count}[/green], "
        f"[yellow]○ 空数据: {empty_count}[/yellow], "
        f"[red]✗ 失败: {fail_count}[/red]"
    )

    # 打印失败详情（最多显示 10 个）
    if failed_codes:
        console.print("[dim]失败股票代码:[/dim]")
        for code, err in failed_codes[:10]:
            console.print(f"[dim]  {code}: {err[:50]}...[/dim]")
        if len(failed_codes) > 10:
            console.print(f"[dim]  ... 还有 {len(failed_codes) - 10} 个，建议输出到日志文件排查[/dim]")

    # 合并结果并映射列名
    if success_dfs:
        result = pd.concat(success_dfs, ignore_index=True)
        return data_source._rename_columns(result, data_source.FINANCIAL_INDICATOR_MAP)
    return pd.DataFrame()


async def _run_fetch(
    data_type: str,
    start_date: str | None,
    end_date: str | None,
    source: str,
    ts_code: str | None,
    max_workers: int,
) -> None:
    """执行数据获取（异步函数）"""
    from quant.data.etl.cleaners import DuplicateCleaner, MissingValueCleaner
    from quant.data.etl.pipeline import ETLPipeline
    from quant.data.sources.tushare_client import TushareClient
    from quant.data.storage.repository import DataRepository

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

        elif data_type == "index_list":
            df = await data_source.get_index_list()
            count = await repository.upsert_index_info(df)
            console.print(f"[green]指数列表更新完成，插入 {count} 条记录[/green]")

        elif data_type == "daily":
            df = await data_source.get_daily_quotes(start_date=start_date, end_date=end_date)
            if not df.empty:
                df = pipeline.run(df)
            count = await repository.upsert_daily_quotes(df)
            console.print(f"[green]日线行情更新完成，插入 {count} 条记录[/green]")

        elif data_type == "index":
            df = await data_source.get_index_quotes(start_date=start_date, end_date=end_date)
            count = await repository.upsert_index_quotes(df)
            console.print(f"[green]指数行情更新完成，插入 {count} 条记录[/green]")

        elif data_type == "basic":
            df = await data_source.get_daily_basic(start_date=start_date, end_date=end_date)
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
            if ts_code:
                # 单个股票：直接使用 async API
                df = await data_source.get_financial_indicator(
                    ts_code=ts_code, start_date=start_date, end_date=end_date
                )
            else:
                # 批量获取：使用同步线程池 + run_in_executor
                stocks = await repository.get_stock_list(active_only=True)
                ts_codes = stocks["ts_code"].tolist()

                loop = asyncio.get_running_loop()
                df = await loop.run_in_executor(
                    None,
                    lambda: _fetch_financial_parallel(
                        data_source, ts_codes, start_date, end_date, max_workers
                    )
                )

            count = await repository.upsert_financial_indicator(df)
            console.print(f"[green]财务指标更新完成，插入 {count} 条记录[/green]")

        else:
            console.print(f"[red]未知数据类型: {data_type}[/red]")
            console.print(
                "支持的数据类型: all, stock_list, index_list, daily, index, basic, calendar, financial"
            )

    except Exception as e:
        console.print(f"[red]获取数据失败: {e}[/red]")
        raise


def _run_fetch_all(
    start_date: str | None,
    end_date: str | None,
    source: str,
    max_workers: int,
) -> None:
    """批量更新所有数据"""
    from quant.data.etl.cleaners import DuplicateCleaner, MissingValueCleaner
    from quant.data.etl.pipeline import ETLPipeline
    from quant.data.sources.tushare_client import TushareClient
    from quant.data.storage.repository import DataRepository

    async def _fetch_all_async():
        data_source = TushareClient()
        repository = DataRepository()

        pipeline = (
            ETLPipeline()
            .add_cleaner(DuplicateCleaner())
            .add_cleaner(MissingValueCleaner(strategy="ffill", limit=5))
        )

        console.print(f"[blue]开始批量更新所有数据（来源: {source}）...[/blue]")
        results: list[tuple[str, int]] = []

        # 定义要更新的数据类型及其获取函数
        fetch_tasks = [
            ("股票列表", "stock_list", lambda: data_source.get_stock_list()),
            ("指数列表", "index_list", lambda: data_source.get_index_list()),
            ("交易日历", "calendar", lambda: data_source.get_trade_calendar(
                exchange="SSE", start_date=start_date, end_date=end_date
            )),
            ("日线行情", "daily", lambda: data_source.get_daily_quotes(
                start_date=start_date, end_date=end_date
            )),
            ("指数行情", "index", lambda: data_source.get_index_quotes(
                start_date=start_date, end_date=end_date
            )),
            ("每日指标", "basic", lambda: data_source.get_daily_basic(
                start_date=start_date, end_date=end_date
            )),
            ("财务指标", "financial", lambda: data_source.get_financial_indicator(
                start_date=start_date, end_date=end_date
            )),
        ]

        for name, data_type, fetch_func in fetch_tasks:
            try:
                console.print(f"[dim]正在获取 {name}...[/dim]")
                df = await fetch_func()

                if data_type in ("daily", "stock_list") and not df.empty:
                    df = pipeline.run(df)

                # 根据数据类型调用对应的 upsert 方法
                upsert_map = {
                    "stock_list": repository.upsert_stock_info,
                    "index_list": repository.upsert_index_info,
                    "calendar": repository.upsert_trade_calendar,
                    "daily": repository.upsert_daily_quotes,
                    "index": repository.upsert_index_quotes,
                    "basic": repository.upsert_daily_basic,
                    "financial": repository.upsert_financial_indicator,
                }

                count = await upsert_map[data_type](df)
                results.append((name, count))
                console.print(f"[green]✓ {name} 更新完成，插入 {count} 条记录[/green]")

            except Exception as e:
                results.append((name, 0))
                console.print(f"[red]✗ {name} 更新失败: {e}[/red]")

        # 显示汇总
        console.print("\n[bold]更新汇总:[/bold]")
        total = 0
        for name, count in results:
            status = "[green]✓[/green]" if count >= 0 else "[red]✗[/red]"
            console.print(f"  {status} {name}: {count} 条")
            total += count
        console.print(f"\n[cyan]总计: {total} 条记录[/cyan]")

    asyncio.run(_fetch_all_async())
