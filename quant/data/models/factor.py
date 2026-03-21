"""因子数据模型"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class FactorDefinition(Base, TimestampMixin):
    """因子定义表"""

    __tablename__ = "factor_definition"

    factor_id: Mapped[str] = mapped_column(String(50), primary_key=True, comment="因子ID")
    name: Mapped[str] = mapped_column(String(100), comment="因子名称")
    category: Mapped[str] = mapped_column(String(50), index=True, comment="因子类别")
    sub_category: Mapped[str | None] = mapped_column(String(50), comment="子类别")
    description: Mapped[str | None] = mapped_column(Text, comment="因子描述")
    formula: Mapped[str | None] = mapped_column(Text, comment="计算公式")
    data_source: Mapped[str | None] = mapped_column(String(50), comment="数据来源")
    freq: Mapped[str] = mapped_column(String(10), default="D", comment="更新频率")
    is_active: Mapped[bool] = mapped_column(default=True, comment="是否启用")


class FactorData(Base):
    """因子数据表（按日期存储）"""

    __tablename__ = "factor_data"

    factor_id: Mapped[str] = mapped_column(String(50), primary_key=True, comment="因子ID")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日期")
    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="TS代码")
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="因子值")

    __table_args__ = (
        Index("ix_factor_data_trade_date", "trade_date"),
        Index("ix_factor_data_factor_date", "factor_id", "trade_date"),
    )


class FactorStatistics(Base, TimestampMixin):
    """因子统计表"""

    __tablename__ = "factor_statistics"

    factor_id: Mapped[str] = mapped_column(String(50), primary_key=True, comment="因子ID")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日期")

    # 基础统计
    count: Mapped[int] = mapped_column(comment="样本数")
    mean: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="均值")
    std: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="标准差")
    min: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="最小值")
    max: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="最大值")
    median: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="中位数")

    # 分位数
    pct_25: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="25%分位数")
    pct_75: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="75%分位数")
    skewness: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="偏度")
    kurtosis: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), comment="峰度")

    # 缺失率
    null_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="缺失率")
