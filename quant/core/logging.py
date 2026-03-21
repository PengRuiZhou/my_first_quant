"""日志配置模块

使用 loguru 进行日志管理。
"""

import sys
from pathlib import Path

from loguru import logger

from .config import get_settings


def setup_logging() -> None:
    """配置日志"""
    settings = get_settings()

    # 移除默认处理器
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True,
    )

    # 文件输出
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "quant_{time:YYYY-MM-DD}.log",
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="00:00",  # 每天轮转
        retention="30 days",  # 保留30天
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
    )

    # 错误日志单独存储
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="00:00",
        retention="90 days",
        compression="zip",
        encoding="utf-8",
    )

    if settings.debug:
        logger.debug("Debug mode enabled")
