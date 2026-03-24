"""Scheduler command for CLI."""

import asyncio
import os
from pathlib import Path

from rich.table import Table
from typer import Argument, Option

from quant.cli.console import console

# Constants for scheduler files
_SCHEDULER_DIR = ".quant/scheduler"
_PID_FILE = f"{_SCHEDULER_DIR}/scheduler.pid"
_LOG_FILE = f"{_SCHEDULER_DIR}/scheduler.log"
_SCRIPT_FILE = f"{_SCHEDULER_DIR}/runner.py"


def _get_scheduler_paths() -> tuple[str, str, str, str]:
    """Get scheduler-related file paths.

    Returns:
        (scheduler_dir, pid_file, log_file, script_file)
    """
    # Use .quant/scheduler under project root
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
    """Check if a process is running.

    Args:
        pid: Process ID

    Returns:
        Whether the process is running
    """
    if not pid:
        return False

    try:
        # Use kill -0 to check if process exists (cross-platform compatible)
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def scheduler(
    action: str = Argument(
        ...,
        help="Action: start/stop/status/run/list",
    ),
    job_id: str | None = Option(
        None, "--job", "-j", help="Job ID (for run command)"
    ),
) -> None:
    """Scheduler management.

    Actions:
        start: Start the scheduler
        stop: Stop the scheduler
        status: View scheduler status
        run <job_id>: Manually run a specific job
        list: List all jobs
    """
    _run_scheduler(action, job_id)


def _run_scheduler(action: str, job_id: str | None) -> None:
    """Execute scheduler action."""
    if action == "start":
        _scheduler_start()
    elif action == "stop":
        _scheduler_stop()
    elif action == "status":
        _scheduler_status()
    elif action == "run":
        if not job_id:
            console.print("[red]Please specify job ID: --job <job_id>[/red]")
            return
        _scheduler_run(job_id)
    elif action == "list":
        _scheduler_list()
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Supported actions: start, stop, status, run, list")


def _scheduler_start() -> None:
    """Start scheduler (background process)."""
    _, pid_file, log_file, script_file = _get_scheduler_paths()

    # Check if already running
    if os.path.exists(pid_file):
        with open(pid_file) as f:
            pid = f.read().strip()
        if pid and _is_process_running(pid):
            console.print(f"[yellow]Scheduler already running (PID: {pid})[/yellow]")
            console.print(f"Log file: {log_file}")
            return

    console.print("[blue]Starting scheduler...[/blue]")
    console.print("[yellow]Note: Scheduler will run in background, use 'quant scheduler stop' to stop[/yellow]")

    # Create startup script
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

    # Keep running
    try:
        while scheduler.is_running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
'''

    # Write script file
    with open(script_file, "w") as f:
        f.write(script)

    # Start in background
    os.system(f"nohup python {script_file} > {log_file} 2>&1 & echo $! > {pid_file}")

    with open(pid_file) as f:
        pid = f.read().strip()

    console.print(f"[green]Scheduler started (PID: {pid})[/green]")
    console.print(f"Log file: {log_file}")


def _scheduler_stop() -> None:
    """Stop scheduler."""
    _, pid_file, _, _ = _get_scheduler_paths()

    if not os.path.exists(pid_file):
        console.print("[yellow]Scheduler is not running[/yellow]")
        return

    with open(pid_file) as f:
        pid = f.read().strip()

    if pid:
        os.system(f"kill {pid} 2>/dev/null")
        os.remove(pid_file)
        console.print(f"[green]Scheduler stopped (PID: {pid})[/green]")
    else:
        console.print("[yellow]Cannot read scheduler PID[/yellow]")


def _scheduler_status() -> None:
    """View scheduler status."""
    _, pid_file, log_file, _ = _get_scheduler_paths()

    if not os.path.exists(pid_file):
        console.print("[yellow]Scheduler is not running[/yellow]")
        return

    with open(pid_file) as f:
        pid = f.read().strip()

    # Check if process exists
    if pid and _is_process_running(pid):
        console.print(f"[green]Scheduler running (PID: {pid})[/green]")
        console.print(f"Log file: {log_file}")
    else:
        console.print("[yellow]Scheduler stopped (PID file exists but process not found)[/yellow]")
        # Clean up stale PID file
        if os.path.exists(pid_file):
            os.remove(pid_file)
        return

    # Show last few lines of log
    if os.path.exists(log_file):
        console.print("\n[blue]Recent logs:[/blue]")
        os.system(f"tail -10 {log_file}")


def _scheduler_run(job_id: str) -> None:
    """Manually run a job."""
    from quant.data.sources.tushare_client import TushareClient
    from quant.data.storage.repository import DataRepository
    from quant.data.storage.scheduler import DataScheduler

    async def _run():
        scheduler = DataScheduler(
            repository=DataRepository(),
            data_source=TushareClient(),
        )
        console.print(f"[blue]Manually running job: {job_id}[/blue]")
        success = await scheduler.run_job(job_id)
        if success:
            console.print(f"[green]Job {job_id} completed[/green]")
        else:
            console.print(f"[red]Job {job_id} failed or not found[/red]")

    asyncio.run(_run())


def _scheduler_list() -> None:
    """List all jobs."""
    table = Table(title="Scheduled Jobs")
    table.add_column("Job ID", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Cron Expression", style="yellow")

    jobs = [
        ("update_daily_quotes", "Daily quotes update", "0 18 * * *"),
        ("update_daily_basic", "Daily basic update", "30 18 * * *"),
        ("update_stock_list", "Stock list update", "0 10 * * 6"),
        ("update_trade_calendar", "Trade calendar update", "30 10 * * 6"),
    ]

    for job_id, name, cron in jobs:
        table.add_row(job_id, name, cron)

    console.print(table)
