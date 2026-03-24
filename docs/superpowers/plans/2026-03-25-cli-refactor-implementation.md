# CLI 模块化重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `quant/cli.py` 拆分为模块化的 `quant/cli/` 包结构，提高可维护性和扩展性。

**Architecture:** 按命令拆分为独立模块，共享 `console` 对象放在单独文件中避免循环导入，主入口在 `__init__.py` 中注册所有命令。

**Tech Stack:** Python 3.12+, typer, rich

---

## 文件结构

```
quant/cli/
├── __init__.py      # 主入口，注册所有命令 (~30 行)
├── console.py       # 共享 Console 对象 (~5 行)
├── version.py       # version + init 命令 (~30 行)
├── db.py            # db 命令 (~25 行)
├── fetch.py         # fetch 命令 (~85 行)
├── scheduler.py     # scheduler 命令 (~200 行)
├── init_data.py     # init_data 命令 (~35 行)
└── backtest.py      # backtest 命令 (~15 行)
```

---

### Task 1: 创建 console.py - 共享 Console 对象

**Files:**
- Create: `quant/cli/console.py`

- [ ] **Step 1: 创建 quant/cli 目录**

```bash
mkdir -p quant/cli
```

- [ ] **Step 2: 创建 console.py**

```python
"""共享 Console 对象

避免循环导入：子模块从 quant.cli.console 导入 console，
而不是从 quant.cli 或 quant.cli.__init__ 导入。
"""

from rich.console import Console

console = Console()
```

- [ ] **Step 3: 验证导入无错误**

```bash
python -c "from quant.cli.console import console; print(console)"
```

Expected: `<console width=...>`

- [ ] **Step 4: Commit**

```bash
git add quant/cli/console.py
git commit -m "feat(cli): add shared console module"
```

---

### Task 2: 创建 version.py - 版本和初始化命令

**Files:**
- Create: `quant/cli/version.py`

- [ ] **Step 1: 创建 version.py**

```python
"""版本和初始化命令"""

from quant.cli.console import console


def version() -> None:
    """显示版本信息"""
    from quant import __version__

    console.print(f"[green]quant[/green] version: [bold]{__version__}[/bold]")


def init() -> None:
    """初始化项目（创建配置文件）"""
    import shutil
    from pathlib import Path

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
```

- [ ] **Step 2: 验证导入无错误**

```bash
python -c "from quant.cli.version import version, init; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add quant/cli/version.py
git commit -m "feat(cli): add version and init commands"
```

---

### Task 3: 创建 db.py - 数据库操作命令

**Files:**
- Create: `quant/cli/db.py`

- [ ] **Step 1: 创建 db.py**

```python
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
```

- [ ] **Step 2: 验证导入无错误**

```bash
python -c "from quant.cli.db import db; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add quant/cli/db.py
git commit -m "feat(cli): add db command"
```

---

### Task 4: 创建 fetch.py - 数据获取命令

**Files:**
- Create: `quant/cli/fetch.py`

- [ ] **Step 1: 创建 fetch.py**

```python
"""数据获取命令"""

import asyncio

from typer import Argument, Option

from quant.cli.console import console


def fetch(
    data_type: str = Argument(
        ...,
        help="数据类型: stock_list/daily/index/basic/calendar/financial",
    ),
    start_date: str | None = Option(None, "--start", "-s", help="开始日期 (YYYYMMDD)"),
    end_date: str | None = Option(None, "--end", "-e", help="结束日期 (YYYYMMDD)"),
    source: str = Option("tushare", "--source", "-src", help="数据源: tushare/akshare"),
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
```

- [ ] **Step 2: 验证导入无错误**

```bash
python -c "from quant.cli.fetch import fetch; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add quant/cli/fetch.py
git commit -m "feat(cli): add fetch command"
```

---

### Task 5: 创建 scheduler.py - 调度器管理命令

**Files:**
- Create: `quant/cli/scheduler.py`

- [ ] **Step 1: 创建 scheduler.py**

```python
"""调度器管理命令"""

import asyncio
import os

from rich.table import Table
from typer import Argument, Option

from quant.cli.console import console

# 日志和 PID 文件路径
_SCHEDULER_DIR = ".quant/scheduler"
_PID_FILE = f"{_SCHEDULER_DIR}/scheduler.pid"
_LOG_FILE = f"{_SCHEDULER_DIR}/scheduler.log"
_SCRIPT_FILE = f"{_SCHEDULER_DIR}/runner.py"


def _get_scheduler_paths() -> tuple[str, str, str, str]:
    """获取调度器相关文件路径

    Returns:
        (scheduler_dir, pid_file, log_file, script_file)
    """
    from pathlib import Path

    # 使用项目根目录下的 .quant/scheduler
    project_root = Path.cwd()
    scheduler_dir = project_root / _SCHEDULER_DIR
    scheduler_dir.mkdir(parents=True, exist_ok=True)

    return (
        str(scheduler_dir),
        str(project_root / _PID_FILE),
        str(project_root / _LOG_FILE),
        str(project_root / _SCRIPT_FILE),
    )


def _is_process_running(pid: str) -> bool:
    """检查进程是否在运行

    Args:
        pid: 进程 ID

    Returns:
        进程是否在运行
    """
    if not pid:
        return False

    try:
        # 使用 kill -0 检查进程是否存在（跨平台兼容）
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def scheduler(
    action: str = Argument(
        ...,
        help="操作: start/stop/status/run/list",
    ),
    job_id: str | None = Option(None, "--job", "-j", help="任务ID (用于 run 命令)"),
) -> None:
    """调度器管理

    Actions:
        start: 启动调度器
        stop: 停止调度器
        status: 查看调度器状态
        run <job_id>: 手动运行指定任务
        list: 列出所有任务
    """
    _run_scheduler(action, job_id)


def _run_scheduler(action: str, job_id: str | None) -> None:
    """执行调度器操作"""

    if action == "start":
        _scheduler_start()
    elif action == "stop":
        _scheduler_stop()
    elif action == "status":
        _scheduler_status()
    elif action == "run":
        if not job_id:
            console.print("[red]请指定任务ID: --job <job_id>[/red]")
            return
        _scheduler_run(job_id)
    elif action == "list":
        _scheduler_list()
    else:
        console.print(f"[red]未知操作: {action}[/red]")
        console.print("支持的操作: start, stop, status, run, list")


def _scheduler_start() -> None:
    """启动调度器 (后台进程)"""
    _, pid_file, log_file, script_file = _get_scheduler_paths()

    # 检查是否已运行
    if os.path.exists(pid_file):
        with open(pid_file) as f:
            pid = f.read().strip()
        if pid and _is_process_running(pid):
            console.print(f"[yellow]调度器已在运行 (PID: {pid})[/yellow]")
            console.print(f"日志文件: {log_file}")
            return

    console.print("[blue]启动调度器...[/blue]")
    console.print("[yellow]提示: 调度器将在后台运行，使用 'quant scheduler stop' 停止[/yellow]")

    # 创建启动脚本
    script = f'''
import asyncio
import sys
sys.path.insert(0, "{os.getcwd()}")

from quant.data.storage.scheduler import DataScheduler
from quant.data.storage.repository import DataRepository
from quant.data.sources.tushare_client import TushareClient

async def main():
    scheduler = DataScheduler(
        repository=DataRepository(),
        data_source=TushareClient(),
    )
    scheduler.setup_default_jobs()
    scheduler.start()

    # 保持运行
    try:
        while scheduler.is_running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
'''

    # 写入脚本文件
    with open(script_file, "w") as f:
        f.write(script)

    # 后台启动
    os.system(f"nohup python {script_file} > {log_file} 2>&1 & echo $! > {pid_file}")

    with open(pid_file) as f:
        pid = f.read().strip()

    console.print(f"[green]调度器已启动 (PID: {pid})[/green]")
    console.print(f"日志文件: {log_file}")


def _scheduler_stop() -> None:
    """停止调度器"""
    _, pid_file, _, _ = _get_scheduler_paths()

    if not os.path.exists(pid_file):
        console.print("[yellow]调度器未在运行[/yellow]")
        return

    with open(pid_file) as f:
        pid = f.read().strip()

    if pid:
        os.system(f"kill {pid} 2>/dev/null")
        os.remove(pid_file)
        console.print(f"[green]调度器已停止 (PID: {pid})[/green]")
    else:
        console.print("[yellow]无法读取调度器 PID[/yellow]")


def _scheduler_status() -> None:
    """查看调度器状态"""
    _, pid_file, log_file, _ = _get_scheduler_paths()

    if not os.path.exists(pid_file):
        console.print("[yellow]调度器未在运行[/yellow]")
        return

    with open(pid_file) as f:
        pid = f.read().strip()

    # 检查进程是否存在
    if pid and _is_process_running(pid):
        console.print(f"[green]调度器运行中 (PID: {pid})[/green]")
        console.print(f"日志文件: {log_file}")
    else:
        console.print("[yellow]调度器已停止 (PID 文件存在但进程不在)[/yellow]")
        # 清理过期的 PID 文件
        if os.path.exists(pid_file):
            os.remove(pid_file)
        return

    # 显示日志最后几行
    if os.path.exists(log_file):
        console.print("\n[blue]最近日志:[/blue]")
        os.system(f"tail -10 {log_file}")


def _scheduler_run(job_id: str) -> None:
    """手动运行任务"""
    from quant.data.sources.tushare_client import TushareClient
    from quant.data.storage.repository import DataRepository
    from quant.data.storage.scheduler import DataScheduler

    async def _run():
        scheduler = DataScheduler(
            repository=DataRepository(),
            data_source=TushareClient(),
        )
        console.print(f"[blue]手动运行任务: {job_id}[/blue]")
        success = await scheduler.run_job(job_id)
        if success:
            console.print(f"[green]任务 {job_id} 执行完成[/green]")
        else:
            console.print(f"[red]任务 {job_id} 执行失败或不存在[/red]")

    asyncio.run(_run())


def _scheduler_list() -> None:
    """列出所有任务"""
    table = Table(title="调度任务列表")
    table.add_column("任务ID", style="cyan")
    table.add_column("描述", style="green")
    table.add_column("Cron 表达式", style="yellow")

    jobs = [
        ("update_daily_quotes", "每日行情更新", "0 18 * * *"),
        ("update_daily_basic", "每日指标更新", "30 18 * * *"),
        ("update_stock_list", "股票列表更新", "0 10 * * 6"),
        ("update_trade_calendar", "交易日历更新", "30 10 * * 6"),
    ]

    for job_id, name, cron in jobs:
        table.add_row(job_id, name, cron)

    console.print(table)
```

- [ ] **Step 2: 验证导入无错误**

```bash
python -c "from quant.cli.scheduler import scheduler; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add quant/cli/scheduler.py
git commit -m "feat(cli): add scheduler command"
```

---

### Task 6: 创建 init_data.py - 历史数据初始化命令

**Files:**
- Create: `quant/cli/init_data.py`

- [ ] **Step 1: 创建 init_data.py**

```python
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
```

- [ ] **Step 2: 验证导入无错误**

```bash
python -c "from quant.cli.init_data import init_data; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add quant/cli/init_data.py
git commit -m "feat(cli): add init-data command"
```

---

### Task 7: 创建 backtest.py - 回测命令

**Files:**
- Create: `quant/cli/backtest.py`

- [ ] **Step 1: 创建 backtest.py**

```python
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
```

- [ ] **Step 2: 验证导入无错误**

```bash
python -c "from quant.cli.backtest import backtest; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add quant/cli/backtest.py
git commit -m "feat(cli): add backtest command placeholder"
```

---

### Task 8: 创建 __init__.py - 主入口

**Files:**
- Create: `quant/cli/__init__.py`

- [ ] **Step 1: 创建 __init__.py**

```python
"""CLI 主入口"""

import typer

from quant.cli import backtest, db, fetch, init_data, scheduler, version

# 主应用
app = typer.Typer(
    name="quant",
    help="A股量化交易框架",
    add_completion=False,
)

# 注册命令（使用 name= 参数处理命令名与函数名不一致的情况）
app.command()(version.version)
app.command()(version.init)
app.command()(db.db)
app.command(name="fetch")(fetch.fetch)
app.command()(scheduler.scheduler)
app.command(name="init-data")(init_data.init_data)
app.command()(backtest.backtest)


def main() -> None:
    """CLI 入口"""
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证 CLI 可正常加载**

```bash
python -c "from quant.cli import main, app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add quant/cli/__init__.py
git commit -m "feat(cli): add main entry point with all commands registered"
```

---

### Task 9: 删除旧文件并验证

**Files:**
- Delete: `quant/cli.py`

- [ ] **Step 1: 删除旧的 cli.py 文件**

```bash
rm quant/cli.py
```

> **重要**: 必须删除此文件，否则 Python 会优先导入文件而非包。

- [ ] **Step 2: 验证 CLI 命令正常工作**

```bash
quant --help
```

Expected: 显示所有命令列表（version, init, db, fetch, scheduler, init-data, backtest）

- [ ] **Step 3: 验证具体命令**

```bash
quant version
```

Expected: `quant version: x.x.x`

- [ ] **Step 4: 运行测试**

```bash
pytest
```

Expected: 所有测试通过

- [ ] **Step 5: 代码风格检查**

```bash
black quant/cli/ && ruff check quant/cli/ && mypy quant/cli/
```

Expected: 无错误

- [ ] **Step 6: Commit 删除旧文件**

```bash
git add -A && git commit -m "refactor(cli): remove old cli.py in favor of modular package"
```

---

### Task 10: 更新文档

**Files:**
- Modify: `docs/superpowers/specs/2026-03-25-cli-refactor-design.md`

- [ ] **Step 1: 更新设计文档，标记为已完成**

在设计文档末尾添加：

```markdown
## 实现状态

**状态**: ✅ 已完成

**完成时间**: 2026-03-25
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-03-25-cli-refactor-design.md
git commit -m "docs(cli): mark refactor design as completed"
```

---

## 验收标准

- [ ] `quant --help` 显示完整命令列表
- [ ] `quant version` 正常输出
- [ ] `quant scheduler list` 正常显示任务列表
- [ ] 所有测试通过
- [ ] 代码风格检查通过
