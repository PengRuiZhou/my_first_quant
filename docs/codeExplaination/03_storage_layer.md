# Storage Layer 存储层详解

本文档详细解析 `quant/data/storage/` 模块的设计与实现，重点关注异步数据库操作和 Repository 模式。

## 1. 模块概述

存储层负责数据的持久化存储，提供：

- **DataRepository**：数据仓库，封装所有 CRUD 操作
- **DataScheduler**：数据调度器，管理定时数据更新任务

### 文件结构

```
quant/data/storage/
├── __init__.py       # 模块导出
├── repository.py     # 数据仓库
└── scheduler.py      # 数据调度器
```

## 2. 异步数据库架构

### 2.1 SQLAlchemy 2.0 异步模式

本项目使用 SQLAlchemy 2.0 的异步 API，配合 asyncpg 驱动：

```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# 创建异步引擎
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    echo=False,
    pool_pre_ping=True,  # 连接池健康检查
)

# 创建会话工厂
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 提交后对象不过期
)
```

### 2.2 异步上下文管理

```python
async with session_factory() as session:
    # 在此上下文中执行数据库操作
    result = await session.execute(stmt)
    await session.commit()
# 退出上下文时自动关闭会话
```

## 3. DataRepository - 数据仓库

### 3.1 类定义

```python
# quant/data/storage/repository.py

from typing import TypeVar
from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ModelType = TypeVar("ModelType", bound=Base)

class DataRepository:
    """数据仓库

    提供所有数据类型的 CRUD 操作。
    使用异步 SQLAlchemy 2.0。
    """

    def __init__(
        self,
        db_url: str | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ):
        """初始化数据仓库

        Args:
            db_url: 数据库连接 URL，默认从配置读取
            session_factory: 会话工厂，用于测试注入
        """
        self.db_url = db_url or get_settings().db.async_url

        if session_factory:
            # 依赖注入（用于测试）
            self._session_factory = session_factory
        else:
            engine = create_async_engine(self.db_url, echo=False, pool_pre_ping=True)
            self._session_factory = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
```

### 3.2 表管理

```python
async def create_tables(self) -> None:
    """创建所有表"""
    engine = create_async_engine(self.db_url)
    async with engine.begin() as conn:
        # run_sync 在异步上下文中执行同步操作
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    logger.info("数据库表创建完成")

async def drop_tables(self) -> None:
    """删除所有表"""
    engine = create_async_engine(self.db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

### 3.3 通用 Upsert 方法

```python
async def _bulk_insert(
    self,
    model_class: type[ModelType],
    df: pd.DataFrame,
    on_conflict: str = "do_nothing",
    index_elements: list[str] | None = None,
) -> int:
    """批量插入数据（支持 Upsert）

    Args:
        model_class: 模型类
        df: 数据 DataFrame
        on_conflict: 冲突处理策略 (do_nothing/do_update)
        index_elements: 冲突检测的索引列

    Returns:
        插入的行数
    """
    if df.empty:
        return 0

    # 转换 DataFrame 为字典列表
    records = df.to_dict(orient="records")

    # 处理 NaN 值（PostgreSQL 不接受 NaN）
    cleaned_records = []
    for record in records:
        cleaned = {k: (None if pd.isna(v) else v) for k, v in record.items()}
        cleaned_records.append(cleaned)

    async with self._session_factory() as session:
        # PostgreSQL 的 INSERT ... ON CONFLICT 语法
        stmt = insert(model_class).values(cleaned_records)

        if on_conflict == "do_update" and index_elements:
            # Upsert: 冲突时更新
            update_cols = {
                c.name: stmt.excluded[c.name]
                for c in model_class.__table__.columns
                if c.name not in index_elements
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_=update_cols,
            )
        else:
            # 冲突时忽略
            stmt = stmt.on_conflict_do_nothing()

        result = await session.execute(stmt)
        await session.commit()

        return getattr(result, "rowcount", 0) or 0
```

**PostgreSQL Upsert 语法解析**：

```sql
INSERT INTO daily_quote (ts_code, trade_date, close, ...)
VALUES (...)
ON CONFLICT (ts_code, trade_date)  -- 冲突检测的索引列
DO UPDATE SET
    close = EXCLUDED.close,  -- EXCLUDED 引用新值
    high = EXCLUDED.high,
    ...
```

### 3.4 查询方法

```python
async def get_daily_quotes(
    self,
    ts_code: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """获取日线行情

    Args:
        ts_code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
    """
    async with self._session_factory() as session:
        stmt = select(DailyQuote)

        # 动态构建查询条件
        conditions = []
        if ts_code:
            conditions.append(DailyQuote.ts_code == ts_code)
        if start_date:
            conditions.append(DailyQuote.trade_date >= start_date)
        if end_date:
            conditions.append(DailyQuote.trade_date <= end_date)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(DailyQuote.trade_date)

        result = await session.execute(stmt)
        rows = result.scalars().all()

        # 转换为 DataFrame
        if not rows:
            return pd.DataFrame()

        data = [
            {
                "ts_code": r.ts_code,
                "trade_date": r.trade_date,
                "open": r.open,
                # ...
            }
            for r in rows
        ]
        return pd.DataFrame(data)
```

### 3.5 删除方法

```python
async def delete_daily_quotes(
    self,
    ts_code: str | None = None,
    before_date: date | None = None,
) -> int:
    """删除日线行情

    Args:
        ts_code: 股票代码
        before_date: 删除此日期之前的数据
    """
    async with self._session_factory() as session:
        stmt = delete(DailyQuote)

        conditions = []
        if ts_code:
            conditions.append(DailyQuote.ts_code == ts_code)
        if before_date:
            conditions.append(DailyQuote.trade_date < before_date)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await session.execute(stmt)
        await session.commit()
        return getattr(result, "rowcount", 0) or 0
```

### 3.6 聚合查询

```python
async def get_daily_quote_count(self, ts_code: str | None = None) -> int:
    """获取日线行情数量"""
    async with self._session_factory() as session:
        stmt = select(func.count()).select_from(DailyQuote)
        if ts_code:
            stmt = stmt.where(DailyQuote.ts_code == ts_code)

        result = await session.execute(stmt)
        return result.scalar() or 0

async def get_latest_trade_date(self, exchange: str = "SSE") -> date | None:
    """获取最新交易日"""
    async with self._session_factory() as session:
        stmt = (
            select(TradeCalendar.cal_date)
            .where(
                TradeCalendar.exchange == exchange,
                TradeCalendar.is_open.is_(True),
            )
            .order_by(TradeCalendar.cal_date.desc())
            .limit(1)
        )

        result = await session.execute(stmt)
        row = result.first()
        return row[0] if row else None
```

## 4. DataScheduler - 数据调度器

### 4.1 类定义

```python
# quant/data/storage/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

class DataScheduler:
    """数据调度器

    管理定时数据更新任务：
    - 每日行情更新
    - 每周股票列表更新
    - 每周交易日历更新
    """

    def __init__(
        self,
        repository: DataRepository | None = None,
        data_source: BaseDataSource | None = None,
    ):
        self.repository = repository or DataRepository()
        self.data_source = data_source or TushareClient()
        self._scheduler = AsyncIOScheduler()  # 异步调度器
        self._is_running = False
```

### 4.2 调度控制

```python
def start(self) -> None:
    """启动调度器"""
    if self._is_running:
        logger.warning("调度器已在运行")
        return

    self._scheduler.start()
    self._is_running = True
    logger.info("数据调度器已启动")

def stop(self, wait: bool = True) -> None:
    """停止调度器

    Args:
        wait: 是否等待当前任务完成
    """
    if not self._is_running:
        logger.warning("调度器未在运行")
        return

    self._scheduler.shutdown(wait=wait)
    self._is_running = False
    logger.info("数据调度器已停止")
```

### 4.3 任务管理

```python
def add_job(
    self,
    job_id: str,
    func: Callable[[], Coroutine[Any, Any, None]],
    cron: str | None = None,
    interval_seconds: int | None = None,
    replace: bool = True,
    name: str | None = None,
) -> Job:
    """添加定时任务

    Args:
        job_id: 任务唯一标识
        func: 异步任务函数
        cron: Cron 表达式（如 "0 18 * * *" 表示每天 18:00）
        interval_seconds: 间隔秒数（与 cron 二选一）
        replace: 是否替换已存在的任务
        name: 任务名称
    """
    if cron:
        parts = cron.split()
        trigger = CronTrigger(
            minute=parts[0] if len(parts) > 0 else "*",
            hour=parts[1] if len(parts) > 1 else "*",
            day=parts[2] if len(parts) > 2 else "*",
            month=parts[3] if len(parts) > 3 else "*",
            day_of_week=parts[4] if len(parts) > 4 else "*",
        )
    elif interval_seconds:
        trigger = IntervalTrigger(seconds=interval_seconds)
    else:
        raise ValueError("必须提供 cron 或 interval_seconds")

    job = self._scheduler.add_job(
        func,
        trigger=trigger,
        id=job_id,
        name=name or job_id,
        replace_existing=replace,
    )
    return job
```

### 4.4 默认任务配置

```python
def setup_default_jobs(self) -> None:
    """设置默认定时任务

    任务列表：
    - 每日 18:00 更新行情数据
    - 每日 18:30 更新每日指标
    - 每周六 10:00 更新股票列表
    - 每周六 10:30 更新交易日历
    """
    # 每日 18:00 更新行情
    self.add_job(
        job_id="update_daily_quotes",
        func=self._update_daily_quotes,
        cron="0 18 * * *",
        name="每日行情更新",
    )

    # 每周六 10:00 更新股票列表
    self.add_job(
        job_id="update_stock_list",
        func=self._update_stock_list,
        cron="0 10 * * 6",  # 周六 10:00
        name="股票列表更新",
    )
```

### 4.5 任务实现（异步）

```python
async def _update_daily_quotes(self) -> None:
    """更新日线行情"""
    try:
        logger.info("开始更新日线行情...")

        # 获取最新交易日
        latest = await self.repository.get_latest_trade_date()
        today = datetime.now().date()

        # 获取数据（异步）
        df = await self.data_source.get_daily_quotes(
            start_date=latest.strftime("%Y%m%d") if latest else None,
            end_date=today.strftime("%Y%m%d"),
        )

        if df.empty:
            logger.info("没有新的行情数据")
            return

        # ETL 处理
        pipeline = create_minimal_pipeline()
        df_clean = pipeline.run(df)

        # 存储（异步）
        count = await self.repository.upsert_daily_quotes(df_clean)
        logger.info(f"日线行情更新完成，插入 {count} 条记录")

    except Exception as e:
        logger.error(f"更新日线行情失败: {e}")
```

### 4.6 初始化历史数据

```python
async def init_historical_data(self, years: int = 3) -> dict[str, int]:
    """初始化历史数据

    Args:
        years: 初始化多少年的数据

    Returns:
        各类型数据的记录数
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=years * 365)

    logger.info(f"开始初始化 {years} 年历史数据...")
    stats: dict[str, int] = {}

    try:
        # 1. 股票列表
        logger.info("获取股票列表...")
        stock_df = await self.data_source.get_stock_list()
        stats["stock_list"] = await self.repository.upsert_stock_info(stock_df)

        # 2. 交易日历
        logger.info("获取交易日历...")
        cal_df = await self.data_source.get_trade_calendar(
            exchange="SSE",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
        stats["trade_calendar"] = await self.repository.upsert_trade_calendar(cal_df)

        # 3. 日线行情
        logger.info("获取日线行情...")
        quotes_df = await self.data_source.get_daily_quotes(
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
        if not quotes_df.empty:
            pipeline = create_minimal_pipeline()
            quotes_df = pipeline.run(quotes_df)
        stats["daily_quotes"] = await self.repository.upsert_daily_quotes(quotes_df)

        # ... 更多数据类型

        logger.info(f"历史数据初始化完成: {stats}")

    except Exception as e:
        logger.error(f"历史数据初始化失败: {e}")
        raise

    return stats
```

## 5. 设计模式总结

| 模式 | 应用 | 优势 |
|------|------|------|
| **Repository 模式** | DataRepository | 封装数据访问逻辑 |
| **工厂模式** | session_factory | 统一创建会话 |
| **依赖注入** | 构造函数参数 | 便于测试和替换 |
| **异步上下文管理** | async with | 自动资源管理 |

## 6. 异步最佳实践

### 6.1 会话管理

```python
# ✅ 正确：使用上下文管理器
async with self._session_factory() as session:
    result = await session.execute(stmt)
    await session.commit()

# ❌ 错误：忘记关闭会话
session = self._session_factory()
result = await session.execute(stmt)
# 忘记 session.close()
```

### 6.2 批量操作

```python
# ✅ 正确：批量插入
await self._bulk_insert(DailyQuote, df, on_conflict="do_update")

# ❌ 低效：逐条插入
for record in records:
    await session.add(DailyQuote(**record))
    await session.commit()
```

### 6.3 事务管理

```python
# ✅ 正确：批量操作后统一提交
async with session_factory() as session:
    for record in records:
        session.add(record)
    await session.commit()  # 一次提交

# ❌ 低效：每条记录都提交
async with session_factory() as session:
    for record in records:
        session.add(record)
        await session.commit()  # 多次提交
```

## 7. CLI 使用示例

```bash
# 启动调度器
quant scheduler start

# 查看任务列表
quant scheduler list

# 手动运行任务
quant scheduler run -j update_daily_quotes

# 查看状态
quant scheduler status

# 停止调度器
quant scheduler stop

# 初始化历史数据
quant init-data --years 3
```
