# DateConverter ETL Cleaner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move date string conversion from data source layer (TushareClient/AKShareClient) to ETL layer, creating a unified DateConverter cleaner that handles all date column transformations.

**Architecture:** Create `DateConverter` class following the existing `BaseCleaner` pattern. It will detect date columns automatically and convert various date string formats (YYYYMMDD, YYYY-MM-DD, etc.) to Python `date` objects. The data source clients will return raw strings, and the ETL pipeline will handle all type conversions.

**Tech Stack:** pandas (to_datetime), Python date objects, existing ETL infrastructure (BaseCleaner, ETLPipeline)

---

## Files Structure

| File | Action | Purpose |
|------|--------|---------|
| `quant/data/etl/cleaners.py` | Modify | Add `DateConverter` class |
| `quant/data/etl/__init__.py` | Modify | Export `DateConverter` |
| `quant/data/etl/pipeline.py` | Modify | Add DateConverter to default pipeline |
| `quant/data/sources/tushare_client.py` | Modify | Remove date conversion code |
| `quant/data/sources/akshare_client.py` | Modify | Remove date conversion code (if present) |
| `quant/cli/init_data.py` | Verify | Ensure ETL pipeline is used before save |
| `tests/data/test_etl.py` | Modify | Add tests for DateConverter |
| `tests/data/test_integration.py` | Modify | Add integration test |

---

## Task 1: Write DateConverter Unit Tests

**Files:**
- Modify: `tests/data/test_etl.py`

- [ ] **Step 1: Write failing tests for DateConverter**

```python
# === DateConverter Tests ===


class TestDateConverter:
    """DateConverter 单元测试"""

    def test_convert_yyyymmdd_format(self):
        """测试 YYYYMMDD 格式转换"""
        df = pd.DataFrame(
            {
                "trade_date": ["20240101", "20240102", "20240103"],
                "value": [1, 2, 3],
            }
        )
        cleaner = DateConverter(columns=["trade_date"])
        result = cleaner.clean(df)

        assert result["trade_date"].dtype == object
        assert result["trade_date"].iloc[0] == date(2024, 1, 1)
        assert result["trade_date"].iloc[1] == date(2024, 1, 2)

    def test_convert_yyyy_mm_dd_format(self):
        """测试 YYYY-MM-DD 格式转换"""
        df = pd.DataFrame(
            {
                "list_date": ["2024-01-01", "2024-06-15", "2024-12-31"],
                "name": ["A", "B", "C"],
            }
        )
        cleaner = DateConverter(columns=["list_date"])
        result = cleaner.clean(df)

        assert result["list_date"].iloc[0] == date(2024, 1, 1)
        assert result["list_date"].iloc[2] == date(2024, 12, 31)

    def test_convert_multiple_columns(self):
        """测试多列转换"""
        df = pd.DataFrame(
            {
                "start_date": ["20240101", "20240201"],
                "end_date": ["20240131", "20240228"],
                "value": [100, 200],
            }
        )
        cleaner = DateConverter(columns=["start_date", "end_date"])
        result = cleaner.clean(df)

        assert result["start_date"].iloc[0] == date(2024, 1, 1)
        assert result["end_date"].iloc[0] == date(2024, 1, 31)

    def test_convert_with_nat_values(self):
        """测试包含 NaT 值的转换"""
        df = pd.DataFrame(
            {
                "delist_date": ["20240101", None, "20241231"],
                "symbol": ["A", "B", "C"],
            }
        )
        cleaner = DateConverter(columns=["delist_date"])
        result = cleaner.clean(df)

        assert result["delist_date"].iloc[0] == date(2024, 1, 1)
        assert pd.isna(result["delist_date"].iloc[1])
        assert result["delist_date"].iloc[2] == date(2024, 12, 31)

    def test_auto_detect_date_columns(self):
        """测试自动检测日期列"""
        df = pd.DataFrame(
            {
                "trade_date": ["20240101", "20240102"],
                "list_date": ["2024-01-01", "2024-01-02"],
                "name": ["A", "B"],
                "value": [1, 2],
            }
        )
        cleaner = DateConverter()  # 不指定 columns，自动检测
        result = cleaner.clean(df)

        assert result["trade_date"].iloc[0] == date(2024, 1, 1)
        assert result["list_date"].iloc[0] == date(2024, 1, 1)
        assert result["name"].dtype == object
        assert result["value"].dtype in [np.int64, np.int32]

    def test_invalid_date_strings_coerced_to_nat(self):
        """测试无效日期字符串转为 NaT"""
        df = pd.DataFrame(
            {
                "date_col": ["20240101", "INVALID", "20240103"],
            }
        )
        cleaner = DateConverter(columns=["date_col"])
        result = cleaner.clean(df)

        assert result["date_col"].iloc[0] == date(2024, 1, 1)
        assert pd.isna(result["date_col"].iloc[1])
        assert result["date_col"].iloc[2] == date(2024, 1, 3)

    def test_empty_dataframe(self):
        """测试空 DataFrame"""
        df = pd.DataFrame(columns=["trade_date", "value"])
        cleaner = DateConverter(columns=["trade_date"])
        result = cleaner.clean(df)

        assert len(result) == 0
        assert "trade_date" in result.columns

    def test_column_not_exists(self):
        """测试指定列不存在时跳过"""
        df = pd.DataFrame({"value": [1, 2, 3]})
        cleaner = DateConverter(columns=["nonexistent_date"])
        result = cleaner.clean(df)

        assert "value" in result.columns
        assert "nonexistent_date" not in result.columns

    def test_already_date_objects(self):
        """测试已经是 date 对象的列保持不变"""
        df = pd.DataFrame(
            {
                "trade_date": [date(2024, 1, 1), date(2024, 1, 2)],
            }
        )
        cleaner = DateConverter(columns=["trade_date"])
        result = cleaner.clean(df)

        assert result["trade_date"].iloc[0] == date(2024, 1, 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/data/test_etl.py::TestDateConverter -v`
Expected: FAIL with "NameError: name 'DateConverter' is not defined"

---

## Task 2: Implement DateConverter Class

**Files:**
- Modify: `quant/data/etl/cleaners.py`

- [ ] **Step 3: Add DateConverter class to cleaners.py**

Update imports at the top of `quant/data/etl/cleaners.py`:

```python
"""基础数据清洗器

包含：
- MissingValueCleaner: 缺失值处理
- DuplicateCleaner: 去重处理
- OutlierCleaner: 异常值处理
- DateConverter: 日期字符串转换
"""

from datetime import date
from typing import Literal

import numpy as np
import pandas as pd

from .base import BaseCleaner, CleaningStats
```

Add `DateConverter` class at the end of the file (after `OutlierCleaner`):

```python
class DateConverter(BaseCleaner):
    """日期字符串转换器

    将各种格式的日期字符串转换为 Python date 对象。
    支持的格式：
    - YYYYMMDD (Tushare 格式)
    - YYYY-MM-DD (ISO 格式)
    - 其他 pandas 可识别的日期格式

    Attributes:
        columns: 要转换的列名列表，为空则自动检测
        date_suffixes: 自动检测时匹配的列名后缀
    """

    # 常见的日期列名后缀
    DATE_SUFFIXES = (
        "_date",
        "date",
        "_time",
        "time",
    )

    @property
    def name(self) -> str:
        return "date_converter"

    def __init__(
        self,
        columns: list[str] | None = None,
        date_suffixes: tuple[str, ...] | None = None,
    ):
        """初始化日期转换器

        Args:
            columns: 要转换的列名列表，为空则自动检测
            date_suffixes: 自定义日期列后缀，默认使用 DATE_SUFFIXES
        """
        self.columns = columns or []
        self.date_suffixes = date_suffixes or self.DATE_SUFFIXES
        self._stats: CleaningStats | None = None

    def _detect_date_columns(self, df: pd.DataFrame) -> list[str]:
        """自动检测日期列

        Args:
            df: 输入 DataFrame

        Returns:
            检测到的日期列名列表
        """
        date_cols = []
        for col in df.columns:
            # 检查列名是否以日期相关后缀结尾
            if any(col.lower().endswith(suffix) for suffix in self.date_suffixes):
                # 确保不是数值类型
                if not pd.api.types.is_numeric_dtype(df[col]):
                    date_cols.append(col)
        return date_cols

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """转换日期字符串为 date 对象

        Args:
            df: 输入 DataFrame

        Returns:
            转换后的 DataFrame
        """
        self._stats = CleaningStats(self.name)
        self._stats.input_rows = len(df)

        if df.empty:
            self._stats.output_rows = 0
            return df

        df = df.copy()
        converted_count = 0

        # 确定要转换的列
        columns_to_convert = self.columns if self.columns else self._detect_date_columns(df)

        for col in columns_to_convert:
            if col not in df.columns:
                continue

            # 如果已经是 date 对象，跳过
            if df[col].dtype == object:
                first_valid = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                if first_valid is not None and isinstance(first_valid, date):
                    # 已经是 date 对象，跳过
                    continue

            # 使用 pandas to_datetime 转换
            try:
                # 先尝试 YYYYMMDD 格式（Tushare 格式）
                dt_series = pd.to_datetime(df[col], format="%Y%m%d", errors="coerce")
                # 如果全部失败（但原始数据不为空），尝试通用解析
                if dt_series.isna().all() and not df[col].isna().all():
                    dt_series = pd.to_datetime(df[col], errors="coerce")

                # 转换为 date 对象
                df[col] = dt_series.dt.date
                converted_count += 1
            except Exception:
                # 转换失败，保持原样
                pass

        self._stats.output_rows = len(df)
        self._stats.details = {
            "columns_converted": columns_to_convert,
            "converted_count": converted_count,
        }

        return df

    def get_stats(self) -> CleaningStats | None:
        return self._stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/data/test_etl.py::TestDateConverter -v`
Expected: PASS (all 9 tests)

---

## Task 3: Export DateConverter

**Files:**
- Modify: `quant/data/etl/__init__.py`

- [ ] **Step 5: Add DateConverter to exports**

Update `quant/data/etl/__init__.py`:

```python
from quant.data.etl.cleaners import (
    DateConverter,
    DuplicateCleaner,
    MissingValueCleaner,
    OutlierCleaner,
)

__all__ = [
    "DateConverter",
    "DuplicateCleaner",
    "MissingValueCleaner",
    "OutlierCleaner",
    # ... rest of exports
]
```

- [ ] **Step 6: Run tests to verify import works**

Run: `python -c "from quant.data.etl import DateConverter; print(DateConverter)"`
Expected: `<class 'quant.data.etl.cleaners.DateConverter'>`

---

## Task 4: Update ETL Pipeline

**Files:**
- Modify: `quant/data/etl/pipeline.py`

- [ ] **Step 7: Add DateConverter to default pipeline factory**

Update `create_default_pipeline` function:

```python
def create_default_pipeline() -> ETLPipeline:
    """创建默认 ETL 管道

    包含：
    - DateConverter: 日期字符串转换
    - MissingValueCleaner: 缺失值处理
    - DuplicateCleaner: 去重
    - OutlierCleaner: 异常值处理
    """
    return ETLPipeline(
        cleaners=[
            DateConverter(),
            MissingValueCleaner(),
            DuplicateCleaner(),
            OutlierCleaner(),
        ]
    )
```

- [ ] **Step 8: Run pipeline tests**

Run: `pytest tests/data/test_etl.py::TestETLPipeline -v`
Expected: PASS

---

## Task 5: Remove Date Conversion from TushareClient

**Files:**
- Modify: `quant/data/sources/tushare_client.py`

- [ ] **Step 9: Remove date conversion from get_stock_list**

Remove these lines from `get_stock_list`:

```python
# DELETE: 转换日期字符串为 date 对象
for col in ["list_date", "delist_date"]:
    if col in result.columns:
        result[col] = pd.to_datetime(result[col], format="%Y%m%d", errors="coerce").dt.date
```

- [ ] **Step 10: Remove date conversion from get_daily_quotes**

Remove these lines from `get_daily_quotes`:

```python
# DELETE: 转换日期字符串为 date 对象
if "trade_date" in result.columns:
    result["trade_date"] = pd.to_datetime(result["trade_date"], format="%Y%m%d", errors="coerce").dt.date
```

- [ ] **Step 11: Remove date conversion from get_index_quotes**

Remove these lines from `get_index_quotes`:

```python
# DELETE: 转换日期字符串为 date 对象
if "trade_date" in result.columns:
    result["trade_date"] = pd.to_datetime(result["trade_date"], format="%Y%m%d", errors="coerce").dt.date
```

- [ ] **Step 12: Remove date conversion from get_trade_calendar**

Remove these lines from `get_trade_calendar`:

```python
# DELETE: 转换日期字符串为 date 对象
for col in ["cal_date", "pretrade_date"]:
    if col in result.columns:
        result[col] = pd.to_datetime(result[col], format="%Y%m%d", errors="coerce").dt.date
```

- [ ] **Step 13: Remove date conversion from get_daily_basic**

Remove these lines from `get_daily_basic`:

```python
# DELETE: 转换日期字符串为 date 对象
if "trade_date" in result.columns:
    result["trade_date"] = pd.to_datetime(result["trade_date"], format="%Y%m%d", errors="coerce").dt.date
```

- [ ] **Step 14: Run TushareClient tests**

Run: `pytest tests/data/test_sources.py -v -k tushare`
Expected: PASS

---

## Task 6: Update CLI init_data to Use ETL Pipeline

**Files:**
- Modify: `quant/cli/init_data.py`

- [ ] **Step 15: Ensure init_data uses ETL pipeline before repository save**

Verify that `init_data.py` processes data through ETL pipeline before saving to repository. The current implementation should already do this - verify the flow:

```python
# The flow should be:
# 1. Data source returns DataFrame with date strings
# 2. ETL pipeline processes DataFrame (DateConverter converts dates)
# 3. Repository receives DataFrame with date objects
# 4. Repository saves to database
```

If not using ETL pipeline, add it:

```python
from quant.data.etl import create_default_pipeline

# After fetching from data source, before saving to repository:
pipeline = create_default_pipeline()
df = pipeline.run(df)
await repo.upsert_xxx(df)
```

- [ ] **Step 16: Verify repository tests still pass**

Run: `pytest tests/data/test_repository.py -v`
Expected: PASS

---

## Task 7: Integration Test

**Files:**
- Modify: `tests/data/test_integration.py`

- [ ] **Step 17: Add integration test for date conversion**

```python
async def test_date_conversion_in_pipeline():
    """测试日期转换在完整 ETL 管道中工作"""
    # 模拟 Tushare 返回的原始数据（字符串格式）
    raw_df = pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000002.SZ"],
            "trade_date": ["20240101", "20240102"],
            "open": [10.0, 11.0],
            "close": [10.5, 11.5],
        }
    )

    # 通过 ETL 管道处理
    pipeline = create_default_pipeline()
    result = pipeline.run(raw_df)

    # 验证日期转换
    assert isinstance(result["trade_date"].iloc[0], date)
    assert result["trade_date"].iloc[0] == date(2024, 1, 1)
```

- [ ] **Step 18: Run integration tests**

Run: `pytest tests/data/test_integration.py -v`
Expected: PASS

---

## Task 8: Run Full Test Suite and Commit

- [ ] **Step 19: Run all data module tests**

Run: `pytest tests/data/ -v`
Expected: All tests pass

- [ ] **Step 20: Run code quality checks**

Run: `black quant/data/etl/cleaners.py tests/data/test_etl.py && ruff check quant/data/etl/ tests/data/test_etl.py`
Expected: No errors

- [ ] **Step 21: Commit changes**

```bash
git add quant/data/etl/cleaners.py quant/data/etl/__init__.py quant/data/etl/pipeline.py quant/data/sources/tushare_client.py quant/data/storage/repository.py tests/data/test_etl.py tests/data/test_integration.py
git commit -m "refactor(etl): move date conversion from data sources to ETL layer

- Add DateConverter cleaner for unified date string handling
- Support YYYYMMDD and YYYY-MM-DD formats
- Auto-detect date columns by suffix
- Remove date conversion from TushareClient
- Update default pipeline to include DateConverter

This centralizes type conversion in the ETL layer, keeping data
source clients focused on data retrieval only."
```

---

## Summary

| Task | Description | Files Modified |
|------|-------------|----------------|
| 1 | Write DateConverter tests | `tests/data/test_etl.py` |
| 2 | Implement DateConverter | `quant/data/etl/cleaners.py` |
| 3 | Export DateConverter | `quant/data/etl/__init__.py` |
| 4 | Update ETL Pipeline | `quant/data/etl/pipeline.py` |
| 5 | Remove Tushare date conversion | `quant/data/sources/tushare_client.py` |
| 6 | Verify CLI uses ETL pipeline | `quant/cli/init_data.py` |
| 7 | Add integration test | `tests/data/test_integration.py` |
| 8 | Test suite & commit | All files |

## Architecture Decision

**Why move date conversion to ETL?**

1. **Single Responsibility**: Data sources focus on retrieval, ETL focuses on transformation
2. **Consistency**: All date handling in one place, unified format support
3. **Testability**: Easier to test date conversion independently
4. **Maintainability**: Adding new date formats only requires updating one class
5. **AKShare Support**: When AKShare client is fully implemented, it will benefit from the same DateConverter

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | All tests use ETL pipeline, so they should continue to work |
| Date format not recognized | Fallback to pandas generic parser with `errors="coerce"` |
| Performance impact | Date conversion is fast, minimal overhead |
