# 数据源层架构解析

本文档详细解析 `quant/data/sources/` 模块的设计与实现，涵盖异步架构、适配器模式、交叉验证机制和错误处理策略。

## 目录

1. [模块概述](#模块概述)
2. [适配器模式设计](#适配器模式设计)
3. [异步架构实现](#异步架构实现)
4. [Tushare 适配器](#tushare-适配器)
5. [AKShare 适配器](#akshare-适配器)
6. [交叉验证机制](#交叉验证机制)
7. [错误处理策略](#错误处理策略)
8. [总结](#总结)

---

## 模块概述

### 文件结构

```
quant/data/sources/
├── __init__.py           # 模块导出
├── base.py               # 抽象基类定义
├── tushare_client.py     # Tushare 适配器
├── akshare_client.py     # AKShare 适配器
└── validator.py          # 双源交叉验证器
```

### 核心组件关系

```
┌─────────────────────────────────────────────────────────────┐
│                     BaseDataSource                          │
│                     (抽象基类)                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ get_stock_list() / get_index_list()                 │   │
│  │ get_daily_quotes() / get_index_quotes()             │   │
│  │ get_trade_calendar() / get_daily_basic()            │   │
│  │ get_financial_indicator() / get_adj_factor()        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 继承
              ┌───────────────┴───────────────┐
              │                               │
┌─────────────────────────┐     ┌─────────────────────────┐
│    TushareClient        │     │    AKShareClient        │
│    (Tushare 适配器)      │     │    (AKShare 适配器)     │
│                         │     │                         │
│  - REST API             │     │  - 直接函数调用          │
│  - 需要 Token           │     │  - 无需 Token           │
│  - 字段映射表            │     │  - 动态接口调用          │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DataValidator                            │
│                    (交叉验证器)                              │
│                                                             │
│  - 数值型字段：容差内取均值                                   │
│  - 字符串字段：必须完全一致                                   │
│  - 单源缺失：使用另一源填充                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 适配器模式设计

### 抽象基类 `BaseDataSource`

`base.py` 定义了数据源的统一接口，所有适配器必须实现此接口。

```python
# /Users/peng/my_first_quant/quant/data/sources/base.py

from abc import ABC, abstractmethod
from typing import Literal
import pandas as pd


class BaseDataSource(ABC):
    """数据源抽象基类

    所有数据源适配器必须实现此接口。
    """

    # ===== 基础信息 =====
    @abstractmethod
    async def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        pass

    @abstractmethod
    async def get_index_list(self) -> pd.DataFrame:
        """获取指数列表"""
        pass

    # ===== 行情数据 =====
    @abstractmethod
    async def get_daily_quotes(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取日线行情"""
        pass

    # ===== 市场数据 =====
    @abstractmethod
    async def get_trade_calendar(
        self,
        exchange: str = "SSE",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取交易日历"""
        pass

    # ===== 财务数据 =====
    @abstractmethod
    async def get_financial_indicator(
        self,
        ts_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str | None = None,
    ) -> pd.DataFrame:
        """获取财务指标"""
        pass

    # ===== 复权因子 =====
    @abstractmethod
    async def get_adj_factor(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取复权因子"""
        pass

    # ===== 辅助方法 =====
    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭连接/清理资源"""
        pass
```

### 设计要点

1. **抽象方法定义**：使用 `@abstractmethod` 装饰器强制子类实现所有接口方法
2. **统一返回类型**：所有方法返回 `pd.DataFrame`，便于后续处理
3. **统一的参数命名**：使用 `ts_code`（Tushare 风格）作为股票标识
4. **异步接口**：所有数据获取方法都是 `async` 的

---

## 异步架构实现

### 核心问题

Tushare 和 AKShare 都是同步 API，而我们的系统需要异步操作以：
- 避免阻塞事件循环
- 支持并发获取多个数据
- 与异步存储层配合

### 解决方案：`asyncio.run_in_executor`

将同步 API 调用包装为异步操作：

```python
# /Users/peng/my_first_quant/quant/data/sources/tushare_client.py

import asyncio

class TushareClient(BaseDataSource):
    @retry_on_failure(max_retries=3)
    async def get_daily_quotes(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取日线行情"""
        loop = asyncio.get_event_loop()

        # 关键：将同步 API 调用放入线程池执行
        df = await loop.run_in_executor(
            None,  # 使用默认线程池
            lambda: self._pro.daily(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
            ),
        )

        result = self._rename_columns(df, self.DAILY_QUOTE_MAP)
        return result
```

### 工作原理图解

```
┌──────────────────────────────────────────────────────────────┐
│                     主事件循环 (Main Event Loop)               │
│                                                              │
│   asyncio.run()                                              │
│        │                                                     │
│        ▼                                                     │
│   ┌─────────────────┐                                        │
│   │ async func()    │                                        │
│   │ await get_data()│                                        │
│   └────────┬────────┘                                        │
│            │                                                 │
│            ▼                                                 │
│   ┌─────────────────────────────────────────────┐            │
│   │ loop.run_in_executor(None, sync_api_call)   │            │
│   └────────────────────┬────────────────────────┘            │
│                        │                                     │
│            ┌───────────┴───────────┐                         │
│            │                       │                          │
│            ▼                       ▼                          │
│   ┌─────────────────┐    ┌─────────────────┐                 │
│   │ 线程池 Worker 1  │    │ 线程池 Worker 2  │                │
│   │ (执行同步调用)    │    │ (执行同步调用)    │               │
│   └────────┬────────┘    └────────┬────────┘                 │
│            │                       │                          │
│            └───────────┬───────────┘                          │
│                        │                                     │
│                        ▼                                     │
│              返回 Future (awaitable)                          │
│                        │                                     │
│                        ▼                                     │
│              继续执行后续代码                                  │
└──────────────────────────────────────────────────────────────┘
```

### AKShare 的异步包装

```python
# /Users/peng/my_first_quant/quant/data/sources/akshare_client.py

import asyncio
import akshare as ak

class AKShareClient(BaseDataSource):
    async def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        loop = asyncio.get_event_loop()

        # 同样的异步包装模式
        df = await loop.run_in_executor(
            None,
            lambda: ak.stock_zh_a_spot_em()
        )

        # 数据转换处理...
        return result
```

---

## Tushare 适配器

### 文件位置
`/Users/peng/my_first_quant/quant/data/sources/tushare_client.py`

### 核心特性

#### 1. 字段映射机制

Tushare API 返回的字段名与系统标准字段名可能不同，使用映射表进行转换：

```python
class TushareClient(BaseDataSource):
    # 字段映射：Tushare 字段 -> 标准字段
    DAILY_QUOTE_MAP = {
        "ts_code": "ts_code",
        "trade_date": "trade_date",
        "pre_close": "pre_close",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "change": "change",
        "pct_chg": "pct_chg",
        "vol": "vol",
        "amount": "amount",
    }

    DAILY_BASIC_MAP = {
        "ts_code": "ts_code",
        "trade_date": "trade_date",
        "close": "close",
        "turnover_rate": "turnover_rate",
        "turnover_rate_f": "turnover_rate_f",
        "volume_ratio": "volume_ratio",
        "pe": "pe",
        "pe_ttm": "pe_ttm",
        "pb": "pb",
        "ps": "ps",
        "ps_ttm": "ps_ttm",
        "dv_ratio": "dv_ratio",
        "total_mv": "total_mv",
        "circ_mv": "circ_mv",
    }

    def _rename_columns(
        self, df: pd.DataFrame, field_map: dict[str, str]
    ) -> pd.DataFrame:
        """重命名列，只保留 field_map 中定义的字段"""
        if df.empty:
            return df

        # 只选择存在的列
        existing_cols = [c for c in field_map if c in df.columns]
        df = df[existing_cols].copy()
        df.columns = [field_map[c] for c in existing_cols]
        return df
```

#### 2. 初始化与配置

```python
class TushareClient(BaseDataSource):
    def __init__(self, token: str | None = None):
        """初始化 Tushare 客户端

        Args:
            token: Tushare API Token，为空则从配置读取
        """
        settings = get_settings()
        self._token = token or settings.tushare.token
        self._timeout = settings.tushare.timeout
        self._retry_times = settings.tushare.retry_times

        if not self._token:
            logger.warning("Tushare token 未配置，部分功能不可用")

        # 初始化 pro API
        ts.set_token(self._token)
        self._pro = ts.pro_api()
```

#### 3. 数据获取方法示例

```python
@retry_on_failure(max_retries=3)
async def get_stock_list(self) -> pd.DataFrame:
    """获取股票列表"""
    logger.info("正在从 Tushare 获取股票列表...")

    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(
        None,
        lambda: self._pro.stock_basic(
            exchange="",
            list_status="L",
            fields=",".join(self.STOCK_LIST_MAP.keys())
        )
    )

    result = self._rename_columns(df, self.STOCK_LIST_MAP)

    # 添加 is_active 字段
    result["is_active"] = True

    logger.info(f"获取到 {len(result)} 条股票信息")
    return result
```

---

## AKShare 适配器

### 文件位置
`/Users/peng/my_first_quant/quant/data/sources/akshare_client.py`

### AKShare 与 Tushare 的主要差异

```python
class AKShareClient(BaseDataSource):
    """AKShare 数据源适配器

    AKShare 与 Tushare 的主要差异：
    1. 股票代码格式不同：AKShare 使用 "000001"，Tushare 使用 "000001.SZ"
    2. 接口命名不同：AKShare 使用中文函数名
    3. 返回字段命名不同：AKShare 使用中文字段名
    """
```

### 代码格式转换

```python
def _convert_code_to_ts(self, symbol: str, market: str = "SZ") -> str:
    """将 AKShare 代码转换为 Tushare 格式

    Args:
        symbol: 股票代码，如 "000001"
        market: 市场代码 "SZ" 或 "SH"

    Returns:
        Tushare 格式代码，如 "000001.SZ"
    """
    # 判断市场：6 开头为上海，其他为深圳
    if symbol.startswith("6"):
        return f"{symbol}.SH"
    else:
        return f"{symbol}.SZ"

def _convert_ts_to_code(self, ts_code: str) -> str:
    """将 Tushare 代码转换为 AKShare 格式"""
    return ts_code.split(".")[0]
```

### 动态接口调用

由于 AKShare 接口名可能变化，使用 `getattr` 动态调用：

```python
async def get_index_list(self) -> pd.DataFrame:
    """获取指数列表"""
    loop = asyncio.get_event_loop()

    # AKShare 接口名可能变化，使用 getattr 动态调用
    try:
        index_sh_func = getattr(ak, "index_stock_info_sh", None)
        if index_sh_func:
            df_sh = await loop.run_in_executor(None, index_sh_func)
            df_sh["market"] = "SH"
        else:
            df_sh = pd.DataFrame()
    except Exception:
        df_sh = pd.DataFrame()
        logger.warning("获取上证指数列表失败")
```

### 中文字段名映射

```python
async def get_daily_quotes(self, ts_code: str | None = None, ...) -> pd.DataFrame:
    """获取日线行情"""
    # ...
    df = await loop.run_in_executor(
        None,
        lambda: ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_fmt,
            end_date=end_fmt,
            adjust="",  # 不复权
        ),
    )

    result = pd.DataFrame()
    result["ts_code"] = ts_code
    result["trade_date"] = pd.to_datetime(df["日期"]).dt.strftime("%Y%m%d")
    result["open"] = df["开盘"]
    result["high"] = df["最高"]
    result["low"] = df["最低"]
    result["close"] = df["收盘"]
    result["vol"] = df["成交量"]
    result["amount"] = df["成交额"]
    # ...
    return result
```

---

## 交叉验证机制

### 文件位置
`/Users/peng/my_first_quant/quant/data/sources/validator.py`

### 验证报告数据结构

```python
@dataclass
class ValidationReport:
    """验证报告"""

    total_rows: int = 0                    # 总行数
    matched_rows: int = 0                  # 匹配行数
    mismatched_rows: int = 0               # 不匹配行数
    missing_in_tushare: int = 0            # Tushare 缺失数
    missing_in_akshare: int = 0            # AKShare 缺失数

    # 字段级别的差异统计
    field_diffs: dict[str, dict] = field(default_factory=dict)

    # 异常记录
    anomalies: list[dict] = field(default_factory=list)

    @property
    def match_rate(self) -> float:
        """匹配率"""
        if self.total_rows == 0:
            return 0.0
        return self.matched_rows / self.total_rows
```

### 交叉验证流程

```
┌─────────────────────────────────────────────────────────────┐
│                    交叉验证流程                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 数据合并 (pd.merge)                                  │
│                                                              │
│   df_tushare ─────┐                                          │
│                    ├── outer join ──► merged_df              │
│   df_akshare ─────┘                                          │
│                                                              │
│   统计: missing_in_tushare, missing_in_akshare               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 字段类型识别                                         │
│                                                              │
│   自动识别:                                                   │
│   - numeric_fields: float64, int64                          │
│   - string_fields: object, str                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 数值型字段处理                                        │
│                                                              │
│   计算相对差异: diff = |tushare - akshare| / |tushare|       │
│                                                              │
│   ┌──────────────┬──────────────────────────────────────┐   │
│   │ diff <= 容差  │ 取均值: (tushare + akshare) / 2     │   │
│   ├──────────────┼──────────────────────────────────────┤   │
│   │ diff > 容差   │ 使用 Tushare 值，标记异常            │   │
│   └──────────────┴──────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: 字符串字段处理                                        │
│                                                              │
│   ┌─────────────────┬────────────────────────────────┐      │
│   │ 值完全一致       │ 使用该值                        │      │
│   ├─────────────────┼────────────────────────────────┤      │
│   │ 值不一致         │ 使用 Tushare 值，标记异常        │      │
│   └─────────────────┴────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: 生成验证报告                                         │
│                                                              │
│   - match_rate: 匹配率                                       │
│   - field_diffs: 各字段差异统计                              │
│   - anomalies: 异常记录列表                                  │
└─────────────────────────────────────────────────────────────┘
```

### 核心验证逻辑

```python
class DataValidator:
    """双源数据验证器"""

    def __init__(self, tolerance: float = 0.01):
        """初始化验证器

        Args:
            tolerance: 数值型字段容差（默认 1%）
        """
        self.tolerance = tolerance

    def cross_validate(
        self,
        df_tushare: pd.DataFrame,
        df_akshare: pd.DataFrame,
        on: list[str] | None = None,
        numeric_fields: list[str] | None = None,
        string_fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """交叉验证并合并数据"""
        if on is None:
            on = ["ts_code", "trade_date"]

        # 合并数据
        merged = pd.merge(
            df_tushare,
            df_akshare,
            on=on,
            how="outer",
            suffixes=("_tushare", "_akshare"),
            indicator=True,
        )

        # 统计缺失情况
        self._report.missing_in_tushare = (merged["_merge"] == "right_only").sum()
        self._report.missing_in_akshare = (merged["_merge"] == "left_only").sum()

        # 处理数值型字段...
        # 处理字符串字段...

        return result
```

### 数值差异计算

```python
def _calculate_numeric_diff(self, s1: pd.Series, s2: pd.Series) -> pd.Series:
    """计算数值型差异（相对差异）"""
    # 避免除零
    denominator = s1.abs().replace(0, np.nan)
    diff = (s1 - s2).abs() / denominator
    return diff.fillna(0)

def _merge_numeric_field(
    self,
    s_tushare: pd.Series,
    s_akshare: pd.Series,
    diff: pd.Series,
    field: str,
) -> pd.Series:
    """合并数值型字段"""
    result = pd.Series(index=s_tushare.index, dtype=float)

    for idx in s_tushare.index:
        t_val = s_tushare.get(idx)
        a_val = s_akshare.get(idx)
        d = diff.get(idx, 0)

        # 两个值都存在
        if pd.notna(t_val) and pd.notna(a_val):
            if d <= self.tolerance:
                # 在容差内，取均值
                result[idx] = (t_val + a_val) / 2
            else:
                # 超出容差，标记异常，使用 Tushare 值
                result[idx] = t_val
                self._report.anomalies.append({
                    "field": field,
                    "index": str(idx),
                    "tushare_value": float(t_val),
                    "akshare_value": float(a_val),
                    "diff": float(d),
                    "type": "numeric_mismatch",
                })
        # 单源有值的情况...
```

### 便捷函数

```python
def validate_and_merge(
    df_tushare: pd.DataFrame,
    df_akshare: pd.DataFrame,
    on: list[str] | None = None,
    tolerance: float = 0.01,
) -> tuple[pd.DataFrame, dict]:
    """便捷函数：验证并合并数据

    Returns:
        (合并后的数据, 验证报告)
    """
    validator = DataValidator(tolerance=tolerance)
    merged = validator.cross_validate(df_tushare, df_akshare, on=on)
    report = validator.get_validation_report()
    return merged, report
```

---

## 错误处理策略

### 重试装饰器

```python
# /Users/peng/my_first_quant/quant/data/sources/tushare_client.py

import asyncio
from functools import wraps

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_error: Exception | None = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}"
                        )
                        # 指数退避：每次重试等待时间递增
                        await asyncio.sleep(delay * (attempt + 1))

            # 所有重试都失败后抛出最后一个错误
            if last_error is None:
                raise RuntimeError(f"{func.__name__} failed with unknown error")
            raise last_error

        return wrapper

    return decorator
```

### 使用方式

```python
class TushareClient(BaseDataSource):
    @retry_on_failure(max_retries=3)  # 最多重试3次
    async def get_daily_quotes(self, ...) -> pd.DataFrame:
        # API 调用...
        pass
```

### AKShare 的异常处理

AKShare 适配器使用 try-except 处理接口调用失败：

```python
# /Users/peng/my_first_quant/quant/data/sources/akshare_client.py

async def get_index_list(self) -> pd.DataFrame:
    """获取指数列表"""
    loop = asyncio.get_event_loop()

    # 获取上证指数列表
    try:
        index_sh_func = getattr(ak, "index_stock_info_sh", None)
        if index_sh_func:
            df_sh = await loop.run_in_executor(None, index_sh_func)
            df_sh["market"] = "SH"
        else:
            df_sh = pd.DataFrame()
    except Exception:
        df_sh = pd.DataFrame()
        logger.warning("获取上证指数列表失败")

    # 获取深证指数列表
    try:
        index_sz_func = getattr(ak, "index_stock_info_sz", None)
        if index_sz_func:
            df_sz = await loop.run_in_executor(None, index_sz_func)
            df_sz["market"] = "SZ"
        else:
            df_sz = pd.DataFrame()
    except Exception:
        df_sz = pd.DataFrame()
        logger.warning("获取深证指数列表失败")

    # 如果两个接口都失败，使用备用接口
    if df_sh.empty and df_sz.empty:
        try:
            df = await loop.run_in_executor(
                None, lambda: ak.index_stock_info()
            )
            # 处理备用接口数据...
        except Exception as e:
            logger.error(f"获取指数列表失败: {e}")
            return pd.DataFrame()
```

### 错误处理策略对比

| 策略 | Tushare | AKShare |
|------|---------|---------|
| 重试机制 | 装饰器自动重试 | 手动 try-except |
| 接口变化 | 稳定，无需特殊处理 | 使用 getattr 动态调用 |
| 降级处理 | 抛出异常 | 返回空 DataFrame |
| 日志级别 | warning + error | warning + error |

---

## 总结

### 架构优势

1. **统一接口**：通过 `BaseDataSource` 抽象基类，所有数据源适配器遵循相同接口
2. **异步友好**：使用 `run_in_executor` 包装同步 API，不阻塞事件循环
3. **数据质量保障**：双源交叉验证机制提高数据准确性
4. **容错能力**：重试机制和异常处理确保系统稳定性

### 关键设计模式

| 模式 | 应用场景 |
|------|----------|
| **适配器模式** | Tushare/AKShare 适配器统一接口 |
| **策略模式** | 数值/字符串字段采用不同验证策略 |
| **装饰器模式** | `retry_on_failure` 添加重试能力 |
| **模板方法模式** | 基类定义算法骨架，子类实现具体步骤 |

### 使用示例

```python
from quant.data.sources import TushareClient, AKShareClient, validate_and_merge

async def fetch_and_validate():
    # 初始化客户端
    tushare = TushareClient()
    akshare = AKShareClient()

    # 从两个数据源获取数据
    df_ts = await tushare.get_daily_quotes(trade_date="20240101")
    df_ak = await akshare.get_daily_quotes(trade_date="20240101")

    # 交叉验证并合并
    merged, report = validate_and_merge(df_ts, df_ak)

    print(f"匹配率: {report['match_rate']}")
    print(f"异常数: {len(report['anomalies'])}")

    # 清理资源
    await tushare.close()
    await akshare.close()
```

### 文件路径参考

- 抽象基类：`/Users/peng/my_first_quant/quant/data/sources/base.py`
- Tushare 适配器：`/Users/peng/my_first_quant/quant/data/sources/tushare_client.py`
- AKShare 适配器：`/Users/peng/my_first_quant/quant/data/sources/akshare_client.py`
- 交叉验证器：`/Users/peng/my_first_quant/quant/data/sources/validator.py`
