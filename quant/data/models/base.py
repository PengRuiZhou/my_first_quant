"""数据库基础配置

提供 SQLAlchemy Base 和数据库连接管理。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有模型的基类"""

    pass


class TimestampMixin:
    """时间戳混入类"""

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )


def get_engine(db_url: str, **kwargs: Any):
    """创建数据库引擎

    Args:
        db_url: 数据库连接字符串
        **kwargs: 传递给 create_engine 的额外参数

    Returns:
        SQLAlchemy Engine
    """
    return create_engine(db_url, **kwargs)
