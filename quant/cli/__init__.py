"""CLI 主入口

命令行工具的主入口，注册所有子命令。
"""

import typer

from quant.cli import backtest, db, fetch, init_data, scheduler, version

# 主应用
app = typer.Typer(
    name="quant",
    help="A股量化交易框架",
    add_completion=False,
)

# 注册命令
# 使用 name= 参数处理命令名与函数名不一致的情况
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
