# Stage 3: 数据支撑模块设计文档

## 概述

本文档定义量化交易框架的数据支撑模块（Stage 3）的详细设计，包括数据源、ETL 清洗、存储和调度四个子层。

## 需求摘要

| 维度 | 选择 |
|------|------|
| 数据源策略 | 双源并行（Tushare + AKShare），交叉验证 |
| 定时调度 | APScheduler |
| ETL 范围 | 基础清洗/异常值处理/复权处理/股票状态过滤 |
| 初始数据 | 股票列表/指数行情/股票日线/每日指标 |

## 架构设计

### 目录结构

```
quant/data/
├── __init__.py
├── sources/                 # 数据源层
│   ├── __init__.py
│   ├── base.py              # 抽象接口 (BaseDataSource)
│   ├── tushare_client.py    # Tushare 实现
│   ├── akshare_client.py    # AKShare 实现
│   └── validator.py         # 双源交叉验证
├── etl/                     # ETL 清洗层
│   ├── __init__.py
│   ├── base.py              # 清洗器基类
│   ├── cleaners.py          # 缺失值/异常值/去重
│   ├── adjust.py            # 复权处理
│   ├── filters.py           # 状态过滤
│   └── pipeline.py          # ETL 管道编排
├── storage/                 # 存储层（新增）
│   ├── __init__.py
│   ├── repository.py        # 数据仓库 (CRUD)
│   └── scheduler.py         # APScheduler 调度
└── models/                  # 数据模型（已有）
    ├── __init__.py
    ├── base.py
    ├── stock.py
    ├── market.py
    ├── financial.py
    └── factor.py
```

### 数据流

```
Tushare ──┐
          ├──> validator.py ──> pipeline.py ──> repository.py ──> PostgreSQL
AKShare ──┘                         │
                                    ▼
                            scheduler.py (定时触发)
```

---

## 模块 1: 数据源层 (sources/)

### 1.1 抽象接口 (base.py)

```python
from abc import ABC, abstractmethod
from typing import Literal
import pandas as pd

class BaseDataSource(ABC):
    """数据源抽象基类"""

    # ===== 基础信息 =====
    @abstractmethod
    async def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表 -> StockInfo"""

    @abstractmethod
    async def get_index_list(self) -> pd.DataFrame:
        """获取指数列表 -> IndexInfo"""

    # ===== 行情数据 =====
    @abstractmethod
    async def get_daily_quotes(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取日线行情 -> DailyQuote"""

    @abstractmethod
    async def get_index_quotes(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取指数行情 -> IndexDailyQuote"""

    # ===== 市场数据 =====
    @abstractmethod
    async def get_trade_calendar(
        self,
        exchange: str = "SSE",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取交易日历 -> TradeCalendar"""

    @abstractmethod
    async def get_daily_basic(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
    ) -> pd.DataFrame:
        """获取每日指标 -> DailyBasic"""

    # ===== 财务数据 =====
    @abstractmethod
    async def get_financial_indicator(
        self,
        ts_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取财务指标 -> FinancialIndicator"""
```

### 1.2 Tushare 适配器 (tushare_client.py)

- 继承 `BaseDataSource`
- 使用 tushare pro API
- 内置字段映射（Tushare 字段 -> 数据库字段）
- 支持重试和超时配置

### 1.3 AKShare 适配器 (akshare_client.py)

- 继承 `BaseDataSource`
- 使用 akshare API
- 字段映射（AKShare 字段 -> 数据库字段）
- 注意：AKShare 接口与 Tushare 差异较大，需要适配

### 1.4 交叉验证器 (validator.py)

```python
class DataValidator:
    """双源数据验证器"""

    def __init__(self, tolerance: float = 0.01):
        """
        Args:
            tolerance: 数值型字段容差（默认 1%）
        """
        self.tolerance = tolerance

    def cross_validate(
        self,
        df_tushare: pd.DataFrame,
        df_akshare: pd.DataFrame,
        on: list[str] = ["ts_code", "trade_date"]
    ) -> pd.DataFrame:
        """
        交叉验证并合并数据

        策略:
        - 数值型: 差值在容差内取均值，否则标记异常
        - 字符串: 必须完全一致
        - 单源缺失: 使用另一源填充
        """

    def get_validation_report(self) -> dict:
        """获取验证报告（差异统计）"""
```

---

## 模块 2: ETL 清洗层 (etl/)

### 2.1 清洗器基类 (base.py)

```python
from abc import ABC, abstractmethod
import pandas as pd

class BaseCleaner(ABC):
    """清洗器基类"""

    @abstractmethod
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行清洗"""

    @property
    @abstractmethod
    def name(self) -> str:
        """清洗器名称"""
```

### 2.2 基础清洗器 (cleaners.py)

#### MissingValueCleaner

```python
class MissingValueCleaner(BaseCleaner):
    """缺失值处理"""
    name = "missing_value"

    def __init__(self, strategy: str = "ffill", limit: int = 5):
        """
        Args:
            strategy: ffill/bfill/drop/fillna
            limit: 填充最大连续数
        """

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        # 按股票分组，前向填充（最多 limit 天）
```

#### DuplicateCleaner

```python
class DuplicateCleaner(BaseCleaner):
    """去重处理"""
    name = "duplicate"

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        # 按 (ts_code, trade_date) 去重，保留最后一条
```

#### OutlierCleaner

```python
class OutlierCleaner(BaseCleaner):
    """异常值处理"""
    name = "outlier"

    def __init__(self, method: str = "winsorize", limits: tuple = (0.01, 0.99)):
        """
        Args:
            method: winsorize/zscore/remove
            limits: 缩尾处理的分位数边界
        """

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        # 涨跌幅超 ±30% 标记异常（排除新股/复牌）
        # 价格为负数 -> 设置为 NaN
```

### 2.3 复权处理 (adjust.py)

```python
class PriceAdjuster:
    """复权处理器"""

    def __init__(self, method: Literal["qfq", "hfq", "none"] = "qfq"):
        """
        Args:
            method: qfq(前复权) / hfq(后复权) / none(不复权)
        """

    def adjust(self, df: pd.DataFrame, adj_factor: pd.DataFrame) -> pd.DataFrame:
        """
        应用复权因子
        - 前复权: price * adj_factor / latest_adj_factor
        - 后复权: price * adj_factor
        """

    def recalculate_pct_chg(self, df: pd.DataFrame) -> pd.DataFrame:
        """复权后重算涨跌幅"""
```

### 2.4 状态过滤器 (filters.py)

```python
class StockStatusFilter:
    """股票状态过滤器"""

    def __init__(self):
        self.st_stocks: set[str] = set()      # ST 股票
        self.suspended: set[str] = set()      # 停牌股票
        self.delist: set[str] = set()         # 退市股票

    def update_status(self, stock_info: pd.DataFrame) -> None:
        """更新股票状态（从股票名称和字段判断）"""

    def filter(
        self,
        df: pd.DataFrame,
        exclude_st: bool = True,
        exclude_suspended: bool = True,
        exclude_delist: bool = True,
        min_turnover: float = 0.0,
    ) -> pd.DataFrame:
        """
        过滤不符合条件的股票

        Args:
            df: 输入数据（需包含 ts_code 列）
            exclude_st: 排除 ST 股票
            exclude_suspended: 排除停牌股票
            exclude_delist: 排除退市股票
            min_turnover: 最小换手率阈值
        """
```

### 2.5 ETL 管道 (pipeline.py)

```python
class ETLPipeline:
    """ETL 管道"""

    def __init__(self):
        self.cleaners: list[BaseCleaner] = []
        self.adjuster: PriceAdjuster | None = None
        self.filters: StockStatusFilter | None = None

    def add_cleaner(self, cleaner: BaseCleaner) -> "ETLPipeline":
        """添加清洗器"""
        self.cleaners.append(cleaner)
        return self

    def set_adjuster(self, method: str) -> "ETLPipeline":
        """设置复权方式"""
        self.adjuster = PriceAdjuster(method)
        return self

    def set_filter(self, **kwargs) -> "ETLPipeline":
        """设置过滤器"""
        self.filters = StockStatusFilter(**kwargs)
        return self

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        执行 ETL 管道

        顺序:
        1. 去重
        2. 缺失值处理
        3. 异常值处理
        4. 复权
        5. 状态过滤
        """

# 预设管道
def create_default_pipeline() -> ETLPipeline:
    """创建默认 ETL 管道"""
    return (
        ETLPipeline()
        .add_cleaner(DuplicateCleaner())
        .add_cleaner(MissingValueCleaner())
        .add_cleaner(OutlierCleaner())
        .set_adjuster("qfq")
        .set_filter(exclude_st=True, min_turnover=0.01)
    )
```

---

## 模块 3: 存储层 (storage/)

### 3.1 数据仓库 (repository.py)

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class DataRepository:
    """数据仓库 - 封装所有数据库操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ===== 批量操作 =====
    async def bulk_insert(
        self,
        model_class: type,
        df: pd.DataFrame,
        on_conflict: Literal["ignore", "update"] = "ignore"
    ) -> int:
        """
        批量插入数据

        - 使用 executemany 或 COPY
        - 支持 UPSERT（ON CONFLICT DO NOTHING / DO UPDATE）

        Returns:
            插入/更新的行数
        """

    # ===== 股票信息 =====
    async def get_stock_list(self, active_only: bool = True) -> pd.DataFrame:
        """获取股票列表"""

    async def upsert_stock_info(self, df: pd.DataFrame) -> int:
        """更新/插入股票信息"""

    # ===== 行情数据 =====
    async def get_daily_quotes(
        self,
        ts_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """查询日线行情"""

    async def upsert_daily_quotes(self, df: pd.DataFrame) -> int:
        """更新/插入日线行情"""

    # ===== 指数数据 =====
    async def get_index_quotes(
        self,
        ts_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """查询指数行情"""

    async def upsert_index_quotes(self, df: pd.DataFrame) -> int:
        """更新/插入指数行情"""

    # ===== 交易日历 =====
    async def get_trade_dates(
        self,
        exchange: str = "SSE",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[str]:
        """获取交易日列表"""

    async def get_latest_trade_date(self, exchange: str = "SSE") -> str | None:
        """获取最新交易日"""

    async def upsert_trade_calendar(self, df: pd.DataFrame) -> int:
        """更新/插入交易日历"""

    # ===== 每日指标 =====
    async def upsert_daily_basic(self, df: pd.DataFrame) -> int:
        """更新/插入每日指标"""

    # ===== 财务数据 =====
    async def upsert_financial_indicator(self, df: pd.DataFrame) -> int:
        """更新/插入财务指标"""
```

### 3.2 调度器 (scheduler.py)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

class DataScheduler:
    """数据更新调度器"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.sources: dict[str, BaseDataSource] = {}
        self.repo: DataRepository | None = None
        self.pipeline: ETLPipeline | None = None

    def add_job(
        self,
        job_id: str,
        func: Callable,
        cron: str | None = None,
        interval: int | None = None,
    ) -> None:
        """
        添加定时任务

        Args:
            job_id: 任务唯一标识
            func: 异步任务函数
            cron: Cron 表达式，如 "0 18 * * 1-5" (工作日18:00)
            interval: 间隔秒数
        """

    def setup_default_jobs(self) -> None:
        """设置默认任务"""
        # 每日 18:00 更新行情
        self.add_job(
            "update_daily_quotes",
            self._update_daily_quotes,
            cron="0 18 * * 1-5"
        )
        # 每周六 10:00 更新股票列表
        self.add_job(
            "update_stock_list",
            self._update_stock_list,
            cron="0 10 * * 6"
        )
        # 每周六 10:30 更新交易日历
        self.add_job(
            "update_trade_calendar",
            self._update_trade_calendar,
            cron="30 10 * * 6"
        )

    async def _update_daily_quotes(self) -> None:
        """更新日线行情"""
        # 1. 获取最新交易日
        # 2. 从数据源获取数据
        # 3. ETL 清洗
        # 4. 写入数据库

    async def _update_stock_list(self) -> None:
        """更新股票列表"""

    async def _update_trade_calendar(self) -> None:
        """更新交易日历"""

    def start(self) -> None:
        """启动调度器"""
        self.scheduler.start()

    def stop(self) -> None:
        """停止调度器"""
        self.scheduler.shutdown()

    def get_jobs(self) -> list[dict]:
        """获取所有任务状态"""
```

---

## 模块 4: CLI 扩展

在 `quant/cli.py` 中新增命令：

```python
# quant/cli.py

@cli.command()
def fetch(
    data_type: str = typer.Argument(
        ...,
        help="数据类型: stock_list/index_list/daily/index/basic/calendar/financial"
    ),
    start_date: str | None = typer.Option(None, "--start", "-s", help="开始日期 YYYYMMDD"),
    end_date: str | None = typer.Option(None, "--end", "-e", help="结束日期 YYYYMMDD"),
    source: str = typer.Option("both", "--source", help="数据源: tushare/akshare/both"),
) -> None:
    """手动拉取数据"""
    pass

@cli.command()
def scheduler(
    action: str = typer.Argument(..., help="操作: start/stop/status/list"),
) -> None:
    """管理数据调度器"""
    pass

@cli.command()
def init_data(
    years: int = typer.Option(3, "--years", "-y", help="初始化历史数据年数"),
) -> None:
    """初始化数据库（拉取历史数据）"""
    pass
```

---

## 测试策略

### 单元测试

- 每个清洗器的 `clean()` 方法
- 复权计算正确性
- 过滤器逻辑
- 数据仓库 CRUD 操作

### 集成测试

- 完整 ETL 管道
- 数据源到数据库的端到端流程
- 调度器任务执行

### 测试数据

- 使用 mock 数据模拟 API 响应
- 准备边界情况数据（缺失值、异常值）

---

## 依赖清单

| 依赖 | 用途 | 版本 |
|------|------|------|
| tushare | Tushare 数据源 | >=1.4.0 |
| akshare | AKShare 数据源 | >=1.10.0 |
| apscheduler | 定时调度 | >=3.10.0 |
| sqlalchemy | ORM | >=2.0.0 |
| pandas | 数据处理 | >=2.0.0 |
| asyncpg | 异步 PostgreSQL | >=0.29.0 |

---

## 实现顺序

1. **数据源层** - base.py → tushare_client.py → akshare_client.py → validator.py
2. **ETL 层** - base.py → cleaners.py → adjust.py → filters.py → pipeline.py
3. **存储层** - repository.py → scheduler.py
4. **CLI 扩展** - fetch/scheduler/init_data 命令
5. **测试** - 单元测试 → 集成测试
