# Financial Parallel Fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-step. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持 financial 数据的批量并行获取，使用 --ts-code 指定单个股票，未指定时使用 ThreadPoolExecutor 多线程并行获取所有股票

**Architecture:** 修改 `quant/cli/fetch.py`，添加 `--ts-code` 参数，实现 `_fetch_financial_parallel` **纯同步函数**，使用 `concurrent.futures.ThreadPoolExecutor`（默认 20 线程，可配置），直接调用 Tushare 同步 API（`pro.fina_indicator`），外层 async CLI 用 `run_in_executor` 包装。

**Tech Stack:** Python 3.12, concurrent.futures.ThreadPoolExecutor, typer, pandas, Tushare API（同步）

**关键设计决策：**
- `_fetch_financial_parallel` 是**纯同步函数**，不涉及 asyncio
- 直接调用 `data_source._pro.fina_indicator()`，避免 async/同步转换问题
- **线程安全**：worker 返回结构化结果，不在 worker 内改共享变量
- **区分统计**：成功有数据、成功但空、失败报错
- `max_workers` 可配置，默认 10，范围 1-50
- **--ts-code 只对 financial 有效**：其他 data_type 忽略此参数（宽松模式）
- **fetch all 包含 financial**：会显著增加执行时间，文档需说明

---

## Task 1: 添加 --ts-code 和 --max-workers 参数到 fetch 命令

**File:** `quant/cli/fetch.py`

**Changes:**
- 在 `fetch` 函数中添加 `ts_code` 和 `max_workers` 参数
- 添加 `max_workers` 参数校验（1-100）
- 更新 docstring

**Code:**
```python
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
        asyncio.run(_run_fetch_all(start_date, end_date, source, max_workers))
    else:
        asyncio.run(_run_fetch(data_type, start_date, end_date, source, ts_code, max_workers))
```

**Commit:** `feat(cli): add --ts-code and --max-workers parameters with validation`

---

## Task 2: 实现 _fetch_financial_parallel 纯同步函数（线程安全版本）

**File:** `quant/cli/fetch.py`

**Changes:**
- 新增 `_fetch_financial_parallel` **纯同步函数**
- **线程安全设计**：worker 返回结构化结果，不在 worker 内改共享变量
- 直接调用 Tushare 同步 API `pro.fina_indicator()`
- 使用 `ThreadPoolExecutor` 多线程并行
- 区分统计：success（有数据）、empty（无数据）、failed（失败）
- 失败时记录 ts_code 和错误信息

**Code:**
```python
from typing import Literal, TypeAlias
import pandas as pd

# 类型定义
FetchStatus = Literal["success", "empty", "failed"]
FetchResult: TypeAlias = tuple[str, FetchStatus, pd.DataFrame | None, str | None]
# (ts_code, status, df, error)


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
    from concurrent.futures import ThreadPoolExecutor, as_completed

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
```

**Commit:** `feat(cli): implement thread-safe ThreadPoolExecutor parallel financial fetch`

---

## Task 3: 修改 _run_fetch 函数处理 financial

**File:** `quant/cli/fetch.py`

**Changes:**
- `_run_fetch` 添加 `ts_code` 和 `max_workers` 参数
- 修改 `financial` 分支：
  - 指定 ts_code 时：直接调用 async `get_financial_indicator`
  - 未指定时：获取股票列表，调用同步 `_fetch_financial_parallel`，用 `run_in_executor` 包装

**Code:**
```python
async def _run_fetch(
    data_type: str,
    start_date: str | None,
    end_date: str | None,
    source: str,
    ts_code: str | None,
    max_workers: int,
) -> None:
    """执行数据获取（异步函数）"""
    # ... existing code ...

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
```

**Commit:** `feat(cli): integrate parallel financial fetch with run_in_executor`

---

## Task 4: 在 fetch all 中包含 financial

**File:** `quant/cli/fetch.py`

**Changes:**
- `_run_fetch_all` 添加 `max_workers` 参数
- 在 `fetch_tasks` 中添加 financial 任务
- 使用 `run_in_executor` 调用同步函数
- **重要**：任务执行逻辑统一按 `await fetcher()` 处理

**Code:**
```python
async def _fetch_financial_parallel_all(
    data_source,
    repository,
    start_date: str | None,
    end_date: str | None,
    max_workers: int,
) -> "pd.DataFrame":
    """异步包装：获取股票列表后并行获取财务指标"""
    stocks = await repository.get_stock_list(active_only=True)
    ts_codes = stocks["ts_code"].tolist()

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _fetch_financial_parallel(
            data_source, ts_codes, start_date, end_date, max_workers
        )
    )


async def _run_fetch_all(
    start_date: str | None,
    end_date: str | None,
    source: str,
    max_workers: int = 20,
) -> None:
    """批量更新所有数据（异步函数）

    注意：直接在此函数内实现完整逻辑，不要嵌套 _fetch_all_async()
    """
    data_source, repository = await _init_data_source_and_repository(source)

    # 定义任务列表：(名称, 类型, 获取函数)
    # 注意：financial 任务返回 DataFrame，需要用 await
    fetch_tasks = [
        ("股票列表", "stock_list", lambda: data_source.get_stock_list()),
        ("指数列表", "index_list", lambda: data_source.get_index_list()),
        ("交易日历", "calendar", lambda: data_source.get_trade_calendar(start_date, end_date)),
        ("日线行情", "daily", lambda: data_source.get_daily_quotes(start_date, end_date)),
        ("指数行情", "index", lambda: data_source.get_index_daily(start_date, end_date)),
        ("每日指标", "basic", lambda: data_source.get_daily_basic(start_date, end_date)),
        ("财务指标", "financial", lambda: _fetch_financial_parallel_all(
            data_source, repository, start_date, end_date, max_workers
        )),
    ]
    # ... rest of implementation (遍历 fetch_tasks，await fetcher()，入库)
```

**Commit:** `feat(cli): include financial in fetch all with parallel support`

---

## Task 5: 更新文档

**Files:**
- `CLAUDE.md`
- `README.md`
- `findings.md`
- `progress.md`

**Changes:**
- 更新 CLI 命令说明，添加 `--ts-code` 和 `--max-workers` 参数
- 记录 financial 多线程并行获取的实现
- 添加线程安全设计的说明

**Commit:** `docs: update CLI docs for financial parallel fetch`

---

## Verification

### 代码检查
```bash
# 确保代码无语法错误
python -c "from quant.cli.fetch import fetch, _fetch_financial_parallel; print('OK')"

# Lint 检查
ruff check quant/cli/fetch.py
```

### 功能测试
```bash
# 1. 参数校验测试
quant fetch financial -w 0    # 应该报错
quant fetch financial -w 101  # 应该报错

# 2. 单股票测试
quant fetch financial -c 000001.SZ -s 20230101

# 3. 小规模线程安全测试（5 线程，观察是否有随机失败）
quant fetch financial -s 20230101 -w 5

# 4. 全量测试（观察进度条和多线程效果）
quant fetch financial -s 20230101 -w 20

# 5. fetch all 测试
quant fetch all -s 20260327 -e 20260328
```

### 线程安全验证
- 观察是否有随机失败
- 检查返回数据是否正确
- 确认 `data_source._pro` 在多线程下稳定
- 验证统计数字：success + empty + failed = total

**验证顺序（重要）**：
```bash
# 逐步增加并发数，观察失败模式
1. quant fetch financial -s 20230101 -w 3   # 先用低并发
2. quant fetch financial -s 20230101 -w 5   # 逐步增加
3. quant fetch financial -s 20230101 -w 10  # 中等并发
4. quant fetch financial -s 20230101 -w 20  # 目标并发
```

**观察指标**：
- 是否有随机失败
- 是否偶发空结果异常增加
- 是否返回重复/错乱数据
- 是否有被限流的报错模式

**判断逻辑**：如果 `-w 5` 都不稳定，优先怀疑 `_pro` 共享实例线程安全，而不是线程池逻辑本身。

---

## Notes

### 关键设计点
1. **`_fetch_financial_parallel` 是纯同步函数**：不涉及 asyncio，避免 event loop 问题
2. **直接调用 Tushare 同步 API**：`pro.fina_indicator()`，简单稳定
3. **外层用 `run_in_executor` 包装**：保持 async CLI 接口一致
4. **线程安全设计**：worker 返回结构化结果 `(code, status, df, error)`，不在 worker 内改共享变量
5. **区分统计**：success（有数据）、empty（无数据）、failed（失败）
6. **--ts-code 只对 financial 有效**：其他 data_type 忽略此参数（宽松模式）

### 关于双层线程池
当前设计是：
```
run_in_executor(None, lambda: _fetch_financial_parallel(...))
                         ↓
              内部 ThreadPoolExecutor(max_workers=20)
```

这会形成"线程池包线程池"的结构：
- 外层：默认 executor 的某个线程执行整个 `_fetch_financial_parallel`
- 内层：该线程内再创建 20 线程池

**为什么不改成单层**：
- 目标是把同步函数挪出事件循环，`run_in_executor` 达到了这个目的
- 实际主要消耗在内层池子，外层只是包装
- 改成单层需要改变整体 async 架构，收益不大

**可接受结论**：当前设计功能正确，先这样实现。后续如需优化可考虑复用明确的 executor。

### 已验证事项
1. `data_source._pro` 是否线程安全 ✅ **已验证**：10 线程下稳定
2. Tushare 并发限流阈值 ✅ **已验证**：10 线程 + retry 机制可稳定运行
3. 最佳 `max_workers` 值 ✅ **已确定**：默认 10（范围 1-50）

### 性能预估
- 实际耗时取决于：单请求延迟、Tushare 限流、空结果比例
- 20 线程下预计较串行有明显提升，具体以实测为准
- 建议：首次使用较低并发（如 `-w 5`）测试稳定性

### 风险点
- **Tushare 限流**：可能触发 API 限流，建议从较低并发数开始测试
- **~~内存压力~~**：~~大量 df 合并可能占用内存~~ ✅ **已解决**：改为逐个 df upsert
- **限流风险**：✅ **已解决**：添加 retry 机制（3 次重试，递增等待）
- **线程安全**：✅ **已验证**：`data_source._pro` 在 10 线程下稳定

### 后续优化方向
1. 失败日志输出到文件（CSV/JSON）
2. ~~分批写入数据库（避免内存峰值）~~ ✅ **已实现 (2026-03-29)**
   - `_fetch_financial_parallel` 返回 `list[pd.DataFrame]`
   - 调用方逐个 df upsert，DB 调用次数 = max_workers（默认 10）
3. ~~单股票获取缺少 ETL 处理~~ ✅ **已修复 (2026-03-29)**
   - 单股票分支添加 DateConverter + DuplicateCleaner
4. 断点续传（记录已成功的股票代码）

### fetch all 用户须知
- **fetch all 包含 financial**：会显著增加执行时间（可能从几分钟变成几分钟~十几分钟）
- **可通过 --max-workers 调整并发度**：默认 20，根据 API 限流调整
- **建议首次使用较低并发**：如 `-w 5` 测试稳定性
