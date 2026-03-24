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
