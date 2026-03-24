# Test Suite 测试套件详解

本文档详细解析 `tests/data/` 模块的设计与实现，重点关注异步测试和 Mock 策略。

## 1. 模块概述

测试套件采用 pytest 框架，覆盖数据模块的所有组件。

### 文件结构

```
tests/data/
├── __init__.py          # 包初始化
├── test_etl.py          # ETL 模块测试
├── test_sources.py      # 数据源测试
├── test_repository.py   # 存储层测试
├── test_scheduler.py    # 调度器测试
└── test_integration.py  # 集成测试
```

### 测试类型

| 类型 | 文件 | 覆盖范围 |
|------|------|----------|
| 单元测试 | test_etl.py | 清洗器、管道 |
| 单元测试 | test_repository.py | 数据仓库 |
| 单元测试 | test_sources.py | 数据源适配器 |
| 单元测试 | test_scheduler.py | 调度器 |
| 集成测试 | test_integration.py | 完整流程 |

## 2. 异步测试模式

### 2.1 pytest-asyncio 配置

```python
# pytest.ini 或 pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### 2.2 异步测试用例

```python
# tests/data/test_repository.py

import pytest
from unittest.mock import AsyncMock, MagicMock

class TestDailyQuotes:
    """日线行情操作测试"""

    @pytest.mark.asyncio  # 标记为异步测试
    async def test_get_daily_quotes_with_filter(
        self,
        mock_session_factory,
        mock_session
    ):
        """测试带过滤条件获取日线行情"""
        # 设置 mock 行为
        mock_stock = MagicMock()
        mock_stock.ts_code = "000001.SZ"
        mock_stock.trade_date = date(2024, 1, 1)
        mock_stock.close = 10.2

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_stock]
        mock_session.execute.return_value = mock_result

        # 执行测试
        repo = DataRepository(session_factory=mock_session_factory)
        result = await repo.get_daily_quotes(ts_code="000001.SZ")

        # 验证结果
        assert len(result) == 1
        assert result["ts_code"].iloc[0] == "000001.SZ"
```

### 2.3 AsyncMock 使用

```python
from unittest.mock import AsyncMock

# 创建异步 Mock
mock_session = MagicMock(spec=AsyncSession)
mock_session.execute = AsyncMock(return_value=mock_result)
mock_session.commit = AsyncMock()

# 异步上下文管理器 Mock
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=None)
```

## 3. Fixture 设计

### 3.1 测试数据 Fixtures

```python
# tests/data/test_etl.py

import pandas as pd
import numpy as np
import pytest

@pytest.fixture
def sample_quotes():
    """示例日线行情数据"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240102", "20240103", "20240101", "20240102"],
        "open": [10.0, 10.5, 10.8, 20.0, 20.5],
        "high": [10.5, 10.8, 11.0, 20.5, 21.0],
        "low": [9.8, 10.2, 10.5, 19.5, 20.0],
        "close": [10.2, 10.6, 10.9, 20.2, 20.8],
        "vol": [1000.0, 1200.0, 1100.0, 2000.0, 2200.0],
        "pct_chg": [1.0, 3.9, 2.8, 1.0, 3.0],
    })

@pytest.fixture
def sample_quotes_with_missing():
    """包含缺失值的行情数据"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240102", "20240103", "20240101", "20240102"],
        "open": [10.0, np.nan, 10.8, 20.0, 20.5],  # 包含 NaN
        "close": [10.2, 10.6, 10.9, np.nan, 20.8],
        "vol": [1000.0, 1200.0, 1100.0, 2000.0, 2200.0],
    })

@pytest.fixture
def sample_quotes_with_duplicates():
    """包含重复数据的行情数据"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ", "000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240101", "20240102", "20240102", "20240101"],
        "close": [10.0, 10.1, 10.5, 10.6, 20.0],
        "vol": [1000.0, 1100.0, 1200.0, 1300.0, 2000.0],
    })

@pytest.fixture
def sample_quotes_with_outliers():
    """包含异常值的行情数据"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ"] * 10,
        "trade_date": [f"2024010{i}" for i in range(10)],
        "open": [10.0, 10.1, 10.2, 1000.0, 10.4, 10.5, 10.6, -5.0, 10.8, 10.9],
        "close": [10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9],
        "vol": [1000.0] * 10,
        "pct_chg": [1.0, 1.0, 1.0, 50.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    })
```

### 3.2 Mock Fixtures

```python
# tests/data/test_repository.py

from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

@pytest.fixture
def mock_session_factory():
    """创建模拟会话工厂"""
    factory = MagicMock(spec=async_sessionmaker)
    return factory

@pytest.fixture
def mock_session():
    """创建模拟会话"""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session
```

### 3.3 组合 Fixtures

```python
@pytest.fixture
def mock_session_factory(mock_session):
    """创建配置好的会话工厂"""
    factory = MagicMock(spec=async_sessionmaker)
    factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return factory
```

## 4. 单元测试示例

### 4.1 清洗器测试

```python
# tests/data/test_etl.py

class TestMissingValueCleaner:
    """缺失值清洗器测试"""

    def test_cleaner_name(self):
        """测试清洗器名称"""
        cleaner = MissingValueCleaner()
        assert cleaner.name == "missing_value"

    def test_ffill_strategy(self, sample_quotes_with_missing):
        """测试前向填充策略"""
        cleaner = MissingValueCleaner(strategy="ffill", limit=5)
        result = cleaner.clean(sample_quotes_with_missing)

        # 验证填充结果
        assert result["open"].isna().sum() == 0
        # 000001.SZ 第二行的 open 应该被填充为 10.0
        assert result.loc[1, "open"] == 10.0

    def test_drop_strategy(self, sample_quotes_with_missing):
        """测试删除策略"""
        cleaner = MissingValueCleaner(strategy="drop")
        result = cleaner.clean(sample_quotes_with_missing)

        # 应该删除含有缺失值的行
        assert len(result) < len(sample_quotes_with_missing)

    def test_stats_recording(self, sample_quotes_with_missing):
        """测试统计信息记录"""
        cleaner = MissingValueCleaner(strategy="ffill")
        cleaner.clean(sample_quotes_with_missing)

        stats = cleaner.get_stats()
        assert stats is not None
        assert stats.input_rows == len(sample_quotes_with_missing)
        assert "missing_before" in stats.details
```

### 4.2 去重测试

```python
class TestDuplicateCleaner:
    """去重清洗器测试"""

    def test_remove_duplicates_keep_last(self, sample_quotes_with_duplicates):
        """测试去重保留最后一条"""
        cleaner = DuplicateCleaner(keep="last")
        result = cleaner.clean(sample_quotes_with_duplicates)

        # 应该只保留每个 (ts_code, trade_date) 组合的最后一条
        assert len(result) == 3
        # 20240101 的 000001.SZ 应该保留 close=10.1
        row = result[
            (result["ts_code"] == "000001.SZ") &
            (result["trade_date"] == "20240101")
        ]
        assert row["close"].values[0] == 10.1

    def test_no_duplicates(self, sample_quotes):
        """测试无重复数据"""
        cleaner = DuplicateCleaner()
        result = cleaner.clean(sample_quotes)

        assert len(result) == len(sample_quotes)
```

### 4.3 异常值测试

```python
class TestOutlierCleaner:
    """异常值清洗器测试"""

    def test_winsorize_method(self, sample_quotes_with_outliers):
        """测试缩尾处理"""
        cleaner = OutlierCleaner(method="winsorize", limits=(0.1, 0.9))
        result = cleaner.clean(sample_quotes_with_outliers)

        stats = cleaner.get_stats()
        assert stats.modified_rows >= 0

    def test_negative_price_handling(self, sample_quotes_with_outliers):
        """测试负价格处理"""
        cleaner = OutlierCleaner()
        result = cleaner.clean(sample_quotes_with_outliers)

        # 负价格应该被设为 NaN
        assert (result["open"] < 0).sum() == 0
```

### 4.4 Pipeline 测试

```python
class TestETLPipeline:
    """ETL 管道测试"""

    def test_add_cleaner(self):
        """测试添加清洗器"""
        pipeline = ETLPipeline()
        pipeline.add_cleaner(DuplicateCleaner())

        assert len(pipeline.cleaners) == 1

    def test_chain_calls(self):
        """测试链式调用"""
        pipeline = (
            ETLPipeline()
            .add_cleaner(DuplicateCleaner())
            .add_cleaner(MissingValueCleaner())
            .set_adjuster("qfq")
        )

        assert len(pipeline.cleaners) == 2
        assert pipeline.adjuster is not None

    def test_run_pipeline(self, sample_quotes_with_missing):
        """测试运行管道"""
        pipeline = (
            ETLPipeline()
            .add_cleaner(DuplicateCleaner())
            .add_cleaner(MissingValueCleaner(strategy="ffill"))
        )

        result = pipeline.run(sample_quotes_with_missing)

        assert len(result) > 0
        stats = pipeline.get_stats()
        assert len(stats) == 2
```

### 4.5 工厂函数测试

```python
def test_create_default_pipeline():
    """测试创建默认管道"""
    pipeline = create_default_pipeline()

    assert len(pipeline.cleaners) == 3
    assert pipeline.adjuster is not None
    assert pipeline.status_filter is not None

def test_create_minimal_pipeline():
    """测试创建最小管道"""
    pipeline = create_minimal_pipeline()

    assert len(pipeline.cleaners) == 2
    assert pipeline.adjuster is None

def test_create_strict_pipeline():
    """测试创建严格管道"""
    pipeline = create_strict_pipeline(min_turnover=2.0)

    assert len(pipeline.cleaners) == 3
    assert pipeline.adjuster is not None
```

## 5. 存储层测试

### 5.1 Mock 数据库操作

```python
# tests/data/test_repository.py

class TestStockInfo:
    """股票信息操作测试"""

    @pytest.mark.asyncio
    async def test_get_stock_list_empty(self, mock_session_factory, mock_session):
        """测试获取空股票列表"""
        # 配置 mock 返回空结果
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        result = await repo.get_stock_list()

        assert result.empty

    @pytest.mark.asyncio
    async def test_upsert_stock_info(
        self,
        mock_session_factory,
        mock_session,
        sample_stock_df
    ):
        """测试更新/插入股票信息"""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.upsert_stock_info(sample_stock_df)

        assert count == 3
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_empty_dataframe(self, mock_session_factory, mock_session):
        """测试插入空数据框"""
        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.upsert_stock_info(pd.DataFrame())

        assert count == 0
        mock_session.execute.assert_not_called()
```

### 5.2 NaN 处理测试

```python
class TestNaNHandling:
    """NaN 值处理测试"""

    @pytest.mark.asyncio
    async def test_upsert_with_nan_values(self, mock_session_factory, mock_session):
        """测试包含 NaN 值的插入"""
        df_with_nan = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "symbol": ["000001"],
            "name": ["平安银行"],
            "area": [None],  # NaN 值
            "industry": ["银行"],
            "market": ["主板"],
            "list_date": [date(1991, 4, 3)],
            "is_active": [True],
        })

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.upsert_stock_info(df_with_nan)

        # 应该成功插入，NaN 被转换为 None
        assert count == 1
```

### 5.3 表创建测试

```python
class TestTableCreation:
    """表创建测试"""

    @pytest.mark.asyncio
    async def test_create_tables(self, mock_session_factory):
        """测试创建表"""
        mock_conn = AsyncMock()

        with patch("quant.data.storage.repository.create_async_engine") as mock_engine:
            engine_instance = MagicMock()
            engine_instance.begin = MagicMock(return_value=AsyncMock())
            engine_instance.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            engine_instance.begin.return_value.__aexit__ = AsyncMock(return_value=None)
            engine_instance.dispose = AsyncMock()
            mock_engine.return_value = engine_instance

            repo = DataRepository(session_factory=mock_session_factory)
            await repo.create_tables()

            # 验证调用了 run_sync
            mock_conn.run_sync.assert_called_once()
```

## 6. 集成测试

### 6.1 完整工作流测试

```python
# tests/data/test_etl.py

def test_full_pipeline_workflow(sample_quotes, sample_stock_info, sample_adj_factor):
    """测试完整管道工作流"""
    # 1. 添加一些问题数据
    df = sample_quotes.copy()
    df.loc[0, "close"] = np.nan  # 缺失值

    # 2. 创建管道
    pipeline = create_default_pipeline(stock_info=sample_stock_info)

    # 3. 运行管道
    pipeline.adjuster = None  # 禁用复权
    result = pipeline.run(df, exclude_st=False)

    # 4. 验证结果
    assert len(result) > 0
    summary = pipeline.get_summary()
    assert summary["total_removed"] >= 0
```

## 7. 测试组织结构

### 7.1 测试类组织

```python
class TestMissingValueCleaner:
    """缺失值清洗器测试"""

    def test_cleaner_name(self):
        """测试清洗器名称"""
        ...

    def test_ffill_strategy(self, sample_quotes_with_missing):
        """测试前向填充策略"""
        ...

    def test_drop_strategy(self, sample_quotes_with_missing):
        """测试删除策略"""
        ...
```

### 7.2 命名约定

| 类型 | 命名模式 | 示例 |
|------|----------|------|
| 测试类 | `Test<Component>` | `TestMissingValueCleaner` |
| 测试方法 | `test_<scenario>` | `test_ffill_strategy` |
| Fixture | `<description>_<type>` | `sample_quotes_with_missing` |

## 8. Mock 策略总结

### 8.1 何时使用 Mock

| 场景 | Mock 对象 | 原因 |
|------|-----------|------|
| 数据库操作 | AsyncSession | 避免真实数据库连接 |
| 外部 API | requests/httpx | 避免网络请求 |
| 文件系统 | patch open | 隔离文件依赖 |
| 时间相关 | patch datetime | 确保可重复性 |

### 8.2 Mock 层级

```python
# 1. 对象级别 Mock
mock_session = MagicMock(spec=AsyncSession)

# 2. 方法级别 Mock
mock_session.execute = AsyncMock(return_value=mock_result)

# 3. 上下文管理器 Mock
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=None)

# 4. 工厂级别 Mock
mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
```

## 9. 运行测试

```bash
# 运行所有测试
pytest tests/data/

# 运行特定测试文件
pytest tests/data/test_etl.py

# 运行特定测试类
pytest tests/data/test_etl.py::TestMissingValueCleaner

# 运行特定测试方法
pytest tests/data/test_etl.py::TestMissingValueCleaner::test_ffill_strategy

# 带覆盖率
pytest --cov=quant/data tests/data/

# 详细输出
pytest -v tests/data/
```

## 10. 最佳实践

1. **隔离测试**：每个测试应该独立，不依赖其他测试
2. **使用 Fixture**：复用测试数据和 Mock 配置
3. **明确断言**：每个测试只验证一个行为
4. **Mock 外部依赖**：避免测试依赖外部服务
5. **测试边界条件**：空数据、异常值、极端情况
6. **保持简单**：测试代码应该易于理解
