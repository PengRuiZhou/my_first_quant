# Data Models 数据模型详解

本文档详细解析 `quant/data/models/` 模块的设计与实现，重点关注 SQLAlchemy 2.0 的现代用法。

## 1. 模块概述

数据模型层定义了数据库表结构，使用 SQLAlchemy 2.0 的声明式映射。

### 文件结构

```
quant/data/models/
├── __init__.py       # 模块导出
├── base.py           # 基类定义
├── stock.py          # 股票相关模型
├── market.py         # 行情相关模型
├── financial.py      # 财务相关模型
└── factor.py         # 因子相关模型
```

### 模型清单

| 模型 | 表名 | 用途 |
|------|------|------|
| StockInfo | stock_info | 股票基础信息 |
| StockIndustry | stock_industry | 股票行业分类 |
| IndexInfo | index_info | 指数基础信息 |
| DailyQuote | daily_quote | 日线行情 |
| IndexDailyQuote | index_daily_quote | 指数日线行情 |
| TradeCalendar | trade_calendar | 交易日历 |
| DailyBasic | daily_basic | 每日指标 |
| FinancialIndicator | financial_indicator | 财务指标 |
| FactorDefinition | factor_definition | 因子定义 |
| FactorData | factor_data | 因子数据 |
| FactorStatistics | factor_statistics | 因子统计 |

## 2. 基类定义

### 2.1 DeclarativeBase

```python
# quant/data/models/base.py

from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类

    所有模型都继承自此类。
    DeclarativeBase 是 SQLAlchemy 2.0 的新基类，
    替代了旧版的 declarative_base()。
    """
    pass
```

### 2.2 TimestampMixin

```python
from sqlalchemy import DateTime

class TimestampMixin:
    """时间戳混入类

    为模型添加 created_at 和 updated_at 字段。
    使用混入类可以在多个模型间复用字段定义。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间"
    )
```

### 2.3 类型注解优势

SQLAlchemy 2.0 使用 `Mapped[T]` 进行类型注解：

```python
# SQLAlchemy 1.x（旧版）
class StockInfo(Base):
    __tablename__ = "stock_info"
    ts_code = Column(String(10), primary_key=True)
    name = Column(String(20))

# SQLAlchemy 2.0（新版）
class StockInfo(Base):
    __tablename__ = "stock_info"
    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
```

**优势**：
- 类型安全：IDE 和 mypy 可以检查类型
- 自动推断：`Mapped[str]` 自动映射到 VARCHAR
- 更清晰：字段类型一目了然

## 3. 股票相关模型

### 3.1 StockInfo

```python
# quant/data/models/stock.py

from datetime import date
from typing import TYPE_CHECKING
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .market import DailyQuote

class StockInfo(Base, TimestampMixin):
    """股票基础信息表"""

    __tablename__ = "stock_info"

    # 主键
    ts_code: Mapped[str] = mapped_column(
        String(10),
        primary_key=True,
        comment="TS代码"
    )

    # 基本信息
    symbol: Mapped[str] = mapped_column(
        String(6),
        index=True,  # 创建索引
        comment="股票代码"
    )
    name: Mapped[str] = mapped_column(String(20), comment="股票名称")
    area: Mapped[str | None] = mapped_column(String(10), comment="地域")
    industry: Mapped[str | None] = mapped_column(
        String(20),
        index=True,  # 创建索引
        comment="所属行业"
    )
    market: Mapped[str | None] = mapped_column(String(10), comment="市场类型")

    # 上市信息
    list_date: Mapped[date | None] = mapped_column(comment="上市日期")
    delist_date: Mapped[date | None] = mapped_column(comment="退市日期")
    is_active: Mapped[bool] = mapped_column(
        default=True,
        index=True,  # 创建索引
        comment="是否在市"
    )

    # 公司信息
    full_name: Mapped[str | None] = mapped_column(String(100), comment="公司全称")
    cnspell: Mapped[str | None] = mapped_column(String(20), comment="拼音缩写")
    exchange: Mapped[str | None] = mapped_column(String(10), comment="交易所代码")
    curr_type: Mapped[str | None] = mapped_column(String(10), comment="交易货币")

    # 关系
    daily_quotes: Mapped[list["DailyQuote"]] = relationship(
        "DailyQuote",
        back_populates="stock",
        lazy="dynamic"  # 延迟加载，返回 Query 对象
    )

    def __repr__(self) -> str:
        return f"<StockInfo({self.ts_code}: {self.name})>"
```

**关键点**：

1. **可空类型**：`Mapped[str | None]` 表示字段可为 NULL
2. **索引**：`index=True` 为常用查询字段创建索引
3. **关系**：`relationship` 定义表间关联
4. **TYPE_CHECKING**：避免循环导入

### 3.2 StockIndustry

```python
class StockIndustry(Base):
    """股票行业分类表（申万一级）"""

    __tablename__ = "stock_industry"

    ts_code: Mapped[str] = mapped_column(
        String(10),
        primary_key=True,
        comment="TS代码"
    )
    industry: Mapped[str] = mapped_column(
        String(20),
        index=True,
        comment="申万行业"
    )
    industry_code: Mapped[str | None] = mapped_column(String(10), comment="行业代码")
```

### 3.3 IndexInfo

```python
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
```

## 4. 行情相关模型

### 4.1 DailyQuote

```python
# quant/data/models/market.py

from decimal import Decimal
from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

class DailyQuote(Base, TimestampMixin):
    """日线行情表"""

    __tablename__ = "daily_quote"

    # 复合主键
    ts_code: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("stock_info.ts_code"),  # 外键
        primary_key=True,
        comment="TS代码"
    )
    trade_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
        comment="交易日期"
    )

    # OHLCV（使用 Decimal 保证精度）
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
    stock: Mapped["StockInfo"] = relationship(
        "StockInfo",
        back_populates="daily_quotes"
    )

    # 复合索引
    __table_args__ = (
        Index("ix_daily_quote_trade_date", "trade_date"),
        Index("ix_daily_quote_ts_code_trade_date", "ts_code", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyQuote({self.ts_code} @ {self.trade_date}: {self.close})>"
```

**关键点**：

1. **复合主键**：`(ts_code, trade_date)` 组合唯一
2. **外键约束**：`ForeignKey` 关联到 stock_info 表
3. **Decimal 类型**：金融数据使用 `Decimal` 避免浮点精度问题
4. **复合索引**：为常用查询组合创建索引

### 4.2 IndexDailyQuote

```python
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
```

### 4.3 TradeCalendar

```python
class TradeCalendar(Base):
    """交易日历表"""

    __tablename__ = "trade_calendar"

    exchange: Mapped[str] = mapped_column(
        String(10),
        primary_key=True,
        comment="交易所"
    )
    cal_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
        comment="日历日期"
    )
    is_open: Mapped[bool] = mapped_column(comment="是否交易")
    pretrade_date: Mapped[date | None] = mapped_column(Date, comment="上一交易日")
```

## 5. 财务相关模型

### 5.1 DailyBasic

```python
# quant/data/models/financial.py

class DailyBasic(Base, TimestampMixin):
    """每日指标表

    包含 PE、PB、市值等每日更新的指标。
    """

    __tablename__ = "daily_basic"

    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="TS代码")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日期")

    close: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="收盘价")
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="换手率")
    turnover_rate_f: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="换手率（自由流通股）")
    volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="量比")

    # 估值指标
    pe: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="市盈率")
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="市盈率TTM")
    pb: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="市净率")
    ps: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="市销率")

    # 市值
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric(20, 3), comment="总市值")
    circ_mv: Mapped[Decimal | None] = mapped_column(Numeric(20, 3), comment="流通市值")
```

### 5.2 FinancialIndicator

```python
class FinancialIndicator(Base, TimestampMixin):
    """财务指标表

    包含 ROE、ROA、利润率等财务指标。
    """

    __tablename__ = "financial_indicator"

    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="TS代码")
    ann_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="公告日期")
    end_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="报告期")

    # 盈利能力
    roe: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="ROE")
    roe_dt: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="ROE（扣非）")
    roa: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="ROA")
    netprofit_margin: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="净利率")
    grossprofit_margin: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="毛利率")

    # 偿债能力
    debt_to_assets: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="资产负债率")
    current_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="流动比率")
    quick_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="速动比率")

    # 每股指标
    eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="每股收益")
    bvps: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="每股净资产")
```

## 6. 索引设计原则

### 6.1 主键选择

```python
# 单列主键
ts_code: Mapped[str] = mapped_column(String(10), primary_key=True)

# 复合主键（时间序列数据）
ts_code: Mapped[str] = mapped_column(String(10), primary_key=True)
trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
```

### 6.2 索引策略

```python
# 1. 常用查询字段
symbol: Mapped[str] = mapped_column(String(6), index=True)

# 2. 复合索引（查询顺序）
__table_args__ = (
    Index("ix_daily_quote_trade_date", "trade_date"),
    Index("ix_daily_quote_ts_code_trade_date", "ts_code", "trade_date"),
)
```

### 6.3 外键约束

```python
ts_code: Mapped[str] = mapped_column(
    String(10),
    ForeignKey("stock_info.ts_code"),  # 引用 stock_info 表
    primary_key=True,
)
```

## 7. 模型导出

```python
# quant/data/models/__init__.py

from quant.data.models.base import Base, TimestampMixin, get_engine
from quant.data.models.factor import FactorData, FactorDefinition, FactorStatistics
from quant.data.models.financial import DailyBasic, FinancialIndicator
from quant.data.models.market import DailyQuote, IndexDailyQuote, TradeCalendar
from quant.data.models.stock import IndexInfo, StockInfo, StockIndustry

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "get_engine",
    # Stock
    "StockInfo",
    "StockIndustry",
    "IndexInfo",
    # Market
    "DailyQuote",
    "IndexDailyQuote",
    "TradeCalendar",
    # Financial
    "FinancialIndicator",
    "DailyBasic",
    # Factor
    "FactorDefinition",
    "FactorData",
    "FactorStatistics",
]
```

## 8. 数据类型对照表

| Python 类型 | SQLAlchemy 类型 | 数据库类型 | 用途 |
|-------------|-----------------|------------|------|
| `str` | `String(n)` | VARCHAR(n) | 字符串 |
| `int` | `Integer` | INTEGER | 整数 |
| `float` | `Float` | FLOAT | 浮点数 |
| `Decimal` | `Numeric(p, s)` | DECIMAL(p, s) | 精确数值 |
| `bool` | `Boolean` | BOOLEAN | 布尔值 |
| `date` | `Date` | DATE | 日期 |
| `datetime` | `DateTime` | TIMESTAMP | 时间戳 |
| `str` (长文本) | `Text` | TEXT | 长文本 |

## 9. 最佳实践

### 9.1 使用 Decimal 处理金融数据

```python
# ✅ 正确：使用 Decimal
close: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))

# ❌ 错误：使用 float（精度丢失）
close: Mapped[float | None] = mapped_column(Float)
```

### 9.2 为查询字段添加索引

```python
# 常用查询字段
ts_code: Mapped[str] = mapped_column(String(10), index=True)
trade_date: Mapped[date] = mapped_column(Date, index=True)

# 复合查询
__table_args__ = (
    Index("ix_quotes_code_date", "ts_code", "trade_date"),
)
```

### 9.3 使用 comment 记录字段含义

```python
close: Mapped[Decimal | None] = mapped_column(
    Numeric(10, 3),
    comment="收盘价"  # 会被写入数据库注释
)
```
