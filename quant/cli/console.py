"""共享 Console 对象

避免循环导入：子模块从 quant.cli.console 导入 console，
而不是从 quant.cli 或 quant.cli.__init__ 导入。
"""

from rich.console import Console

console = Console()
