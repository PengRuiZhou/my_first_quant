"""股票基础信息模型"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .market import DailyQuote


class StockInfo(Base, TimestampMixin):
    """股票基础信息表"""

    __tablename__ = "stock_info"

    # 主键
    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="TS代码")

    # 基本信息
    symbol: Mapped[str] = mapped_column(String(6), index=True, comment="股票代码")
    name: Mapped[str] = mapped_column(String(20), comment="股票名称")
    area: Mapped[str | None] = mapped_column(String(10), comment="地域")
    industry: Mapped[str | None] = mapped_column(String(20), index=True, comment="所属行业")
    market: Mapped[str | None] = mapped_column(String(10), comment="市场类型")

    # 上市信息
    list_date: Mapped[date | None] = mapped_column(comment="上市日期")
    delist_date: Mapped[date | None] = mapped_column(comment="退市日期")
    is_active: Mapped[bool] = mapped_column(default=True, index=True, comment="是否在市")

    # 公司信息
    full_name: Mapped[str | None] = mapped_column(String(100), comment="公司全称")
    cnspell: Mapped[str | None] = mapped_column(String(20), comment="拼音缩写")
    exchange: Mapped[str | None] = mapped_column(String(10), comment="交易所代码")
    curr_type: Mapped[str | None] = mapped_column(String(10), comment="交易货币")

    # 关系
    daily_quotes: Mapped[list["DailyQuote"]] = relationship(
        "DailyQuote", back_populates="stock", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<StockInfo({self.ts_code}: {self.name})>"


class StockIndustry(Base):
    """股票行业分类表（申万一级）"""

    __tablename__ = "stock_industry"

    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="TS代码")
    industry: Mapped[str] = mapped_column(String(20), index=True, comment="申万行业")
    industry_code: Mapped[str | None] = mapped_column(String(10), comment="行业代码")


class IndexInfo(Base, TimestampMixin):
    """指数基础信息表"""

    __tablename__ = "index_info"

    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="TS代码")
    name: Mapped[str] = mapped_column(String(20), comment="指数名称")
    full_name: Mapped[str | None] = mapped_column(String(50), comment="指数全称")
    market: Mapped[str | None] = mapped_column(String(10), comment="市场")
    publisher: Mapped[str | None] = mapped_column(String(20), comment="发布方")
    base_date: Mapped[date | None] = mapped_column(comment="基期")
    base_point: Mapped[float | None] = mapped_column(comment="基点")
    list_date: Mapped[date | None] = mapped_column(comment="发布日期")
    weight_rule: Mapped[str | None] = mapped_column(String(20), comment="加权方式")
    desc: Mapped[str | None] = mapped_column(Text, comment="描述")
