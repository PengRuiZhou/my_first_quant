# Stage 3 实现计划：数据支撑模块

## Context

Stage 3 目标是构建完整的数据支撑模块，包括：
- **数据源层**：Tushare/AKShare 双源适配器 + 交叉验证
- **ETL 清洗层**：缺失值/异常值/复权/状态过滤
- **存储层**：数据仓库 + APScheduler 调度
- **CLI 扩展**：fetch/scheduler/init_data 命令

**设计文档**：[2026-03-22-data-module-design.md](../specs/2026-03-22-data-module-design.md)

**现有基础**：
- 数据库模型已完成（`quant/data/models/`）
- 配置系统已就绪（TushareConfig, AKShareConfig）
- 依赖已安装（tushare, akshare, apscheduler, asyncpg）
- CLI 框架已搭建（typer + rich）

---

## 实现任务

### Task 1: 数据源抽象接口 (sources/base.py)

**文件**：`quant/data/sources/base.py`

**步骤**：
1. 创建 `BaseDataSource` 抽象基类
2. 定义异步方法接口：
   - `get_stock_list()` - 获取股票列表
   - `get_index_list()` - 获取指数列表
   - `get_daily_quotes()` - 获取日线行情
   - `get_index_quotes()` - 获取指数行情
   - `get_trade_calendar()` - 获取交易日历
   - `get_daily_basic()` - 获取每日指标
   - `get_financial_indicator()` - 获取财务指标

**验证**：`python -c "from quant.data.sources.base import BaseDataSource"`

---

### Task 2: Tushare 适配器 (sources/tushare_client.py)

**文件**：`quant/data/sources/tushare_client.py`

**步骤**：
1. 继承 `BaseDataSource`
2. 初始化 tushare pro API（使用配置中的 token）
3. 实现字段映射（Tushare 字段 → 数据库字段）
4. 实现所有抽象方法，调用 tushare API
5. 添加重试逻辑和超时处理

**字段映射示例**：
```python
FIELD_MAP = {
    "ts_code": "ts_code",
    "trade_date": "trade_date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "vol": "vol",
    "amount": "amount",
    # ...
}
```

**验证**：
```bash
# 需要配置 TUSHARE_TOKEN
python -c "from quant.data.sources.tushare_client import TushareClient; print('OK')"
```

---

### Task 3: AKShare 适配器 (sources/akshare_client.py)

**文件**：`quant/data/sources/akshare_client.py`

**步骤**：
1. 继承 `BaseDataSource`
2. 实现 AKShare 接口适配（注意：AKShare 接口与 Tushare 差异较大）
3. 实现字段映射
4. 实现所有抽象方法

**注意**：AKShare 的接口命名和返回格式与 Tushare 不同，需要仔细适配。

**验证**：`python -c "from quant.data.sources.akshare_client import AKShareClient; print('OK')"`

---

### Task 4: 双源交叉验证器 (sources/validator.py)

**文件**：`quant/data/sources/validator.py`

**步骤**：
1. 创建 `DataValidator` 类
2. 实现 `cross_validate()` 方法：
   - 数值型：差值在容差内取均值，否则标记异常
   - 字符串：必须完全一致
   - 单源缺失：使用另一源填充
3. 实现 `get_validation_report()` 返回验证报告

**验证**：`python -c "from quant.data.sources.validator import DataValidator; print('OK')"`

---

### Task 5: ETL 清洗器基类 (etl/base.py)

**文件**：`quant/data/etl/base.py`

**步骤**：
1. 创建 `BaseCleaner` 抽象基类
2. 定义 `clean(df) -> df` 抽象方法
3. 定义 `name` 属性

**验证**：`python -c "from quant.data.etl.base import BaseCleaner; print('OK')"`

---

### Task 6: 基础清洗器 (etl/cleaners.py)

**文件**：`quant/data/etl/cleaners.py`

**步骤**：
1. 实现 `MissingValueCleaner`：
   - 支持 ffill/bfill/drop/fillna 策略
   - 按股票分组填充
2. 实现 `DuplicateCleaner`：
   - 按 (ts_code, trade_date) 去重
3. 实现 `OutlierCleaner`：
   - 支持 winsorize/zscore/remove 方法
   - 涨跌幅超 ±30% 标记异常

**验证**：编写单元测试验证清洗逻辑

---

### Task 7: 复权处理器 (etl/adjust.py)

**文件**：`quant/data/etl/adjust.py`

**步骤**：
1. 创建 `PriceAdjuster` 类
2. 支持前复权(qfq)、后复权(hfq)、不复权(none)
3. 实现 `adjust(df, adj_factor)` 方法
4. 实现 `recalculate_pct_chg(df)` 重算涨跌幅

**验证**：测试复权计算正确性

---

### Task 8: 状态过滤器 (etl/filters.py)

**文件**：`quant/data/etl/filters.py`

**步骤**：
1. 创建 `StockStatusFilter` 类
2. 维护 ST/停牌/退市股票集合
3. 实现 `update_status(stock_info)` 更新状态
4. 实现 `filter(df, exclude_st, exclude_suspended, exclude_delist, min_turnover)` 过滤

**验证**：`python -c "from quant.data.etl.filters import StockStatusFilter; print('OK')"`

---

### Task 9: ETL 管道编排 (etl/pipeline.py)

**文件**：`quant/data/etl/pipeline.py`

**步骤**：
1. 创建 `ETLPipeline` 类
2. 实现 `add_cleaner()`, `set_adjuster()`, `set_filter()` 方法（链式调用）
3. 实现 `run(df)` 方法，按顺序执行：
   - 去重 → 缺失值 → 异常值 → 复权 → 状态过滤
4. 创建 `create_default_pipeline()` 工厂函数

**验证**：`python -c "from quant.data.etl.pipeline import create_default_pipeline; print('OK')"`

---

### Task 10: 数据仓库 (storage/repository.py)

**文件**：`quant/data/storage/repository.py`

**步骤**：
1. 创建 `DataRepository` 类
2. 实现 `bulk_insert(model_class, df, on_conflict)` 批量插入
3. 实现各数据类型的 CRUD 方法：
   - `get_stock_list()`, `upsert_stock_info()`
   - `get_daily_quotes()`, `upsert_daily_quotes()`
   - `get_index_quotes()`, `upsert_index_quotes()`
   - `get_trade_dates()`, `get_latest_trade_date()`, `upsert_trade_calendar()`
   - `upsert_daily_basic()`, `upsert_financial_indicator()`

**验证**：需要数据库连接，可使用测试数据库

---

### Task 11: APScheduler 调度器 (storage/scheduler.py)

**文件**：`quant/data/storage/scheduler.py`

**步骤**：
1. 创建 `DataScheduler` 类
2. 使用 `AsyncIOScheduler`
3. 实现 `add_job(job_id, func, cron, interval)` 添加任务
4. 实现 `setup_default_jobs()` 设置默认任务：
   - 每日 18:00 更新行情
   - 每周六 10:00 更新股票列表
   - 每周六 10:30 更新交易日历
5. 实现 `start()`, `stop()`, `get_jobs()` 方法

**验证**：`python -c "from quant.data.storage.scheduler import DataScheduler; print('OK')"`

---

### Task 12: CLI 命令扩展

**文件**：`quant/cli.py`（修改）

**步骤**：
1. 重构 `fetch` 命令：
   ```python
   @app.command()
   def fetch(
       data_type: str = typer.Argument(..., help="stock_list/daily/index/basic/calendar/financial"),
       start_date: str | None = typer.Option(None, "--start", "-s"),
       end_date: str | None = typer.Option(None, "--end", "-e"),
       source: str = typer.Option("both", help="tushare/akshare/both"),
   ) -> None:
   ```

2. 新增 `scheduler` 命令组：
   ```python
   @app.command()
   def scheduler(action: str = typer.Argument(..., help="start/stop/status/list")) -> None:
   ```

3. 新增 `init_data` 命令：
   ```python
   @app.command()
   def init_data(years: int = typer.Option(3, "--years", "-y")) -> None:
   """初始化历史数据"""
   ```

**验证**：
```bash
quant fetch stock_list
quant scheduler status
quant init-data --years 3
```

---

### Task 13: 单元测试

**文件**：`tests/data/`

**步骤**：
1. 创建测试目录结构：
   ```
   tests/data/
   ├── test_sources.py
   ├── test_etl.py
   ├── test_repository.py
   └── test_scheduler.py
   ```
2. 测试清洗器逻辑
3. 测试复权计算
4. 测试过滤器
5. 使用 mock 测试数据源（避免真实 API 调用）

**验证**：`pytest tests/data/ -v`

---

### Task 14: 集成测试

**文件**：`tests/data/test_integration.py`

**步骤**：
1. 测试完整 ETL 管道
2. 测试数据源到数据库的端到端流程
3. 测试调度器任务执行（使用测试数据库）

**验证**：`pytest tests/data/test_integration.py -v`

---

## 实现顺序

```
Phase 1: 数据源层 (Task 1-4)
  base.py → tushare_client.py → akshare_client.py → validator.py

Phase 2: ETL 层 (Task 5-9)
  base.py → cleaners.py → adjust.py → filters.py → pipeline.py

Phase 3: 存储层 (Task 10-11)
  repository.py → scheduler.py

Phase 4: CLI 扩展 (Task 12)
  重构 fetch, 新增 scheduler, init_data

Phase 5: 测试 (Task 13-14)
  单元测试 → 集成测试
```

---

## 关键文件清单

| 文件 | 用途 | 依赖 |
|------|------|------|
| `quant/data/sources/base.py` | 数据源抽象接口 | - |
| `quant/data/sources/tushare_client.py` | Tushare 实现 | base.py, config |
| `quant/data/sources/akshare_client.py` | AKShare 实现 | base.py |
| `quant/data/sources/validator.py` | 交叉验证 | - |
| `quant/data/etl/base.py` | 清洗器基类 | - |
| `quant/data/etl/cleaners.py` | 基础清洗器 | base.py |
| `quant/data/etl/adjust.py` | 复权处理 | - |
| `quant/data/etl/filters.py` | 状态过滤 | - |
| `quant/data/etl/pipeline.py` | ETL 管道 | cleaners, adjust, filters |
| `quant/data/storage/repository.py` | 数据仓库 | models, config |
| `quant/data/storage/scheduler.py` | 调度器 | repository, sources, pipeline |
| `quant/cli.py` | CLI 扩展 | 所有模块 |

---

## 验证清单

- [ ] 所有模块可正常导入
- [ ] Tushare 数据源可获取数据
- [ ] AKShare 数据源可获取数据
- [ ] ETL 管道可正常清洗数据
- [ ] 数据仓库可读写数据库
- [ ] 调度器可启动/停止
- [ ] CLI 命令可正常执行
- [ ] 单元测试全部通过
- [ ] 集成测试全部通过

---

## 风险与注意事项

1. **AKShare 接口差异**：AKShare 的接口命名和返回格式与 Tushare 差异较大，需要仔细适配
2. **异步数据库**：需要使用 `asyncpg` 驱动，确保异步操作正确
3. **Tushare Token**：需要用户配置有效的 Tushare Token 才能获取数据
4. **数据库连接**：集成测试需要可用的 PostgreSQL 数据库
