"""行情数据模型"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .stock import StockInfo


class DailyQuote(Base, TimestampMixin):
    """日线行情表"""

    __tablename__ = "daily_quote"

    # 复合主键
    ts_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("stock_info.ts_code"), primary_key=True, comment="TS代码"
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日期")

    # OHLCV
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="昨收价")
    open: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="开盘价")
    high: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="最高价")
    low: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="最低价")
    close: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="收盘价")
    change: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="涨跌额")
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="涨跌幅(%)")

    # 成交量
    vol: Mapped[Decimal | None] = mapped_column(Numeric(20, 3), comment="成交量(手)")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 3), comment="成交额(千元)")

    # 换手率
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="换手率(%)")

    # 关系
    stock: Mapped["StockInfo"] = relationship("StockInfo", back_populates="daily_quotes")

    # 索引
    __table_args__ = (
        Index("ix_daily_quote_trade_date", "trade_date"),
        Index("ix_daily_quote_ts_code_trade_date", "ts_code", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyQuote({self.ts_code} @ {self.trade_date}: {self.close})>"


class IndexDailyQuote(Base, TimestampMixin):
    """指数日线行情表"""

    __tablename__ = "index_daily_quote"

    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="TS代码")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日期")

    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="昨收价")
    open: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="开盘价")
    high: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="最高价")
    low: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="最低价")
    close: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="收盘价")
    change: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="涨跌额")
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="涨跌幅(%)")
    vol: Mapped[Decimal | None] = mapped_column(Numeric(20, 3), comment="成交量(手)")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 3), comment="成交额(千元)")

    __table_args__ = (
        Index("ix_index_daily_quote_trade_date", "trade_date"),
    )


class TradeCalendar(Base):
    """交易日历表"""

    __tablename__ = "trade_calendar"

    exchange: Mapped[str] = mapped_column(String(10), primary_key=True, comment="交易所")
    cal_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="日历日期")
    is_open: Mapped[bool] = mapped_column(comment="是否交易")
    pretrade_date: Mapped[date | None] = mapped_column(Date, comment="上一交易日")
