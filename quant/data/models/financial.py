"""财务数据模型"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class FinancialIndicator(Base, TimestampMixin):
    """财务指标表"""

    __tablename__ = "financial_indicator"

    # 主键
    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="TS代码")
    ann_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="公告日期")
    end_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="报告期")

    # 盈利能力
    roe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="ROE(%)")
    roe_dt: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="ROE(摊薄)(%)")
    roa: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="ROA(%)")
    netprofit_margin: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="销售净利率(%)")
    grossprofit_margin: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="销售毛利率(%)")

    # 营运能力
    assets_turn: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="总资产周转率")
    inv_turn: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="存货周转率")
    ar_turn: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="应收账款周转率")

    # 偿债能力
    debt_to_assets: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="资产负债率(%)")
    current_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="流动比率")
    quick_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="速动比率")

    # 成长能力
    or_yoy: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="营业收入同比增长率(%)")
    op_yoy: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="营业利润同比增长率(%)")
    ebt_yoy: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="利润总额同比增长率(%)")
    netprofit_yoy: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="归属母公司净利润同比增长率(%)")

    # 每股指标
    eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="每股收益EPS(元)")
    dt_eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="稀释每股收益(元)")
    bvps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="每股净资产(元)")
    cfps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="每股经营现金流(元)")

    # 估值指标
    pe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市盈率PE")
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市盈率TTM")
    pb: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市净率PB")
    ps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市销率PS")
    dv_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="股息率(%)")
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), comment="总市值(万元)")
    circ_mv: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), comment="流通市值(万元)")

    __table_args__ = (
        Index("ix_financial_indicator_end_date", "end_date"),
        Index("ix_financial_indicator_ts_code_end_date", "ts_code", "end_date"),
    )


class DailyBasic(Base, TimestampMixin):
    """每日基本面指标表"""

    __tablename__ = "daily_basic"

    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="TS代码")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日期")

    close: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="收盘价")
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="换手率(%)")
    turnover_rate_f: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="换手率(自由流通股)")
    volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="量比")
    pe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市盈率(总市值/净利润)")
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市盈率TTM")
    pb: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市净率")
    ps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市销率")
    ps_ttm: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市销率TTM")
    pcf: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="市现率")
    dv_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), comment="股息率(%)")
    total_share: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), comment="总股本(万股)")
    float_share: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), comment="流通股本(万股)")
    free_share: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), comment="自由流通股本(万股)")
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), comment="总市值(万元)")
    circ_mv: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), comment="流通市值(万元)")

    __table_args__ = (
        Index("ix_daily_basic_trade_date", "trade_date"),
    )
