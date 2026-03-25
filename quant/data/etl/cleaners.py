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


class MissingValueCleaner(BaseCleaner):
    """缺失值清洗器

    支持多种填充策略，按股票分组处理。
    """

    @property
    def name(self) -> str:
        return "missing_value"

    def __init__(
        self,
        strategy: Literal["ffill", "bfill", "drop", "fillna"] = "ffill",
        fill_value: float | int | str = 0,
        limit: int = 5,
        group_by: str = "ts_code",
        columns: list[str] | None = None,
    ):
        """初始化缺失值清洗器

        Args:
            strategy: 填充策略
                - ffill: 前向填充（用前一个有效值填充）
                - bfill: 后向填充（用后一个有效值填充）
                - drop: 直接删除含缺失值的行
                - fillna: 用固定值填充
            fill_value: 当 strategy="fillna" 时使用的填充值
            limit: 填充的最大连续数（防止过度填充）
            group_by: 分组列名（按股票分组填充）
            columns: 需要处理的列，None 表示处理所有数值列
        """
        self.strategy = strategy
        self.fill_value = fill_value
        self.limit = limit
        self.group_by = group_by
        self.columns = columns
        self._stats: CleaningStats | None = None

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行缺失值清洗"""
        self._stats = CleaningStats(self.name)
        self._stats.input_rows = len(df)

        df = df.copy()

        # 确定要处理的列
        if self.columns is None:
            # 默认处理所有数值列
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            # 排除标识列
            exclude_cols = {self.group_by, "trade_date", "ts_code"}
            cols_to_process = [c for c in numeric_cols if c not in exclude_cols]
        else:
            cols_to_process = self.columns

        # 统计缺失值
        missing_before = df[cols_to_process].isna().sum().sum()

        if self.strategy == "drop":
            # 直接删除含缺失值的行
            df = df.dropna(subset=cols_to_process)

        elif self.strategy == "fillna":
            # 用固定值填充
            df[cols_to_process] = df[cols_to_process].fillna(self.fill_value)

        else:
            # ffill 或 bfill，按股票分组处理
            if self.group_by in df.columns:
                # 确保按日期排序
                sort_cols = [self.group_by]
                if "trade_date" in df.columns:
                    sort_cols.append("trade_date")
                df = df.sort_values(sort_cols)

                # 分组填充
                if self.strategy == "ffill":
                    df[cols_to_process] = df.groupby(self.group_by)[cols_to_process].ffill(
                        limit=self.limit
                    )
                else:  # bfill
                    df[cols_to_process] = df.groupby(self.group_by)[cols_to_process].bfill(
                        limit=self.limit
                    )
            else:
                # 无分组列，直接填充
                if self.strategy == "ffill":
                    df[cols_to_process] = df[cols_to_process].ffill(limit=self.limit)
                else:
                    df[cols_to_process] = df[cols_to_process].bfill(limit=self.limit)

        # 统计清洗结果
        missing_after = df[cols_to_process].isna().sum().sum()
        self._stats.output_rows = len(df)
        self._stats.removed_rows = self._stats.input_rows - self._stats.output_rows
        self._stats.details = {
            "strategy": self.strategy,
            "columns_processed": cols_to_process,
            "missing_before": int(missing_before),
            "missing_after": int(missing_after),
            "missing_filled": int(missing_before - missing_after),
        }

        return df

    def get_stats(self) -> CleaningStats | None:
        """获取清洗统计信息"""
        return self._stats


class DuplicateCleaner(BaseCleaner):
    """去重清洗器

    按指定列组合去重，保留最后一条记录。
    """

    @property
    def name(self) -> str:
        return "duplicate"

    def __init__(
        self,
        subset: list[str] | None = None,
        keep: Literal["first", "last", False] = "last",
    ):
        """初始化去重清洗器

        Args:
            subset: 用于判断重复的列，默认 ["ts_code", "trade_date"]
            keep: 保留策略
                - first: 保留第一条
                - last: 保留最后一条
                - False: 删除所有重复项
        """
        self.subset = subset or ["ts_code", "trade_date"]
        self.keep = keep
        self._stats: CleaningStats | None = None

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行去重"""
        self._stats = CleaningStats(self.name)
        self._stats.input_rows = len(df)

        # 检查 subset 列是否存在
        missing_cols = [c for c in self.subset if c not in df.columns]
        if missing_cols:
            # 如果列不存在，跳过去重
            self._stats.output_rows = len(df)
            self._stats.details = {"skipped": True, "reason": f"missing columns: {missing_cols}"}
            return df

        # 统计重复数
        duplicates = df.duplicated(subset=self.subset, keep=False)
        n_duplicates = duplicates.sum()

        # 去重
        df = df.drop_duplicates(subset=self.subset, keep=self.keep)

        self._stats.output_rows = len(df)
        self._stats.removed_rows = self._stats.input_rows - self._stats.output_rows
        self._stats.details = {
            "subset": self.subset,
            "keep": self.keep,
            "duplicates_found": int(n_duplicates),
        }

        return df

    def get_stats(self) -> CleaningStats | None:
        return self._stats


class OutlierCleaner(BaseCleaner):
    """异常值清洗器

    支持多种异常值处理方法。
    """

    @property
    def name(self) -> str:
        return "outlier"

    def __init__(
        self,
        method: Literal["winsorize", "zscore", "remove", "mark"] = "winsorize",
        columns: list[str] | None = None,
        limits: tuple[float, float] = (0.01, 0.99),
        zscore_threshold: float = 3.0,
        pct_chg_limit: float = 30.0,
    ):
        """初始化异常值清洗器

        Args:
            method: 处理方法
                - winsorize: 缩尾处理（将极端值替换为分位数边界值）
                - zscore: Z-score 方法（超过阈值的标记或替换）
                - remove: 直接删除异常行
                - mark: 标记异常但不处理（添加 is_outlier 列）
            columns: 需要处理的列，None 表示自动检测数值列
            limits: winsorize 的分位数边界，默认 (0.01, 0.99)
            zscore_threshold: zscore 方法的阈值
            pct_chg_limit: 涨跌幅异常阈值（%），超过此值标记为异常
        """
        self.method = method
        self.columns = columns
        self.limits = limits
        self.zscore_threshold = zscore_threshold
        self.pct_chg_limit = pct_chg_limit
        self._stats: CleaningStats | None = None

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行异常值处理"""
        self._stats = CleaningStats(self.name)
        self._stats.input_rows = len(df)

        df = df.copy()

        # 确定要处理的列
        if self.columns is None:
            # 默认处理关键价格/成交量列
            default_cols = ["open", "high", "low", "close", "vol", "amount", "pct_chg"]
            cols_to_process = [c for c in default_cols if c in df.columns]
        else:
            cols_to_process = self.columns

        outlier_count = 0

        # 1. 检查价格为负数的异常
        price_cols = [c for c in ["open", "high", "low", "close"] if c in df.columns]
        for col in price_cols:
            neg_mask = df[col] < 0
            if neg_mask.any():
                df.loc[neg_mask, col] = np.nan
                outlier_count += int(neg_mask.sum())
                self._stats.details[f"{col}_negative"] = int(neg_mask.sum())

        # 2. 检查涨跌幅异常（超过 ±30%，排除新股和复牌）
        if "pct_chg" in df.columns:
            # 正常交易日涨跌幅限制
            pct_abs = df["pct_chg"].abs()
            # 注意：新股上市首日、复牌等情况下涨跌幅可能超过正常范围
            # 这里只标记，不删除
            extreme_mask = pct_abs > self.pct_chg_limit
            if extreme_mask.any():
                self._stats.details["pct_chg_extreme"] = int(extreme_mask.sum())
                if self.method == "mark":
                    df["is_extreme_pct"] = extreme_mask

        # 3. 按指定方法处理异常值
        for col in cols_to_process:
            if col not in df.columns:
                continue
            if col in ["ts_code", "trade_date"]:
                continue

            if self.method == "winsorize":
                # 缩尾处理
                lower, upper = self.limits
                lower_val = df[col].quantile(lower)
                upper_val = df[col].quantile(upper)

                clipped = df[col].clip(lower=lower_val, upper=upper_val)
                n_clipped = (df[col] != clipped).sum()
                if n_clipped > 0:
                    df[col] = clipped
                    outlier_count += int(n_clipped)

            elif self.method == "zscore":
                # Z-score 方法
                col_mean = df[col].mean()
                col_std = df[col].std()
                if col_std > 0:
                    z_scores = np.abs((df[col] - col_mean) / col_std)
                    outlier_mask = z_scores > self.zscore_threshold
                    if outlier_mask.any():
                        # 用均值替换
                        df.loc[outlier_mask, col] = col_mean
                        outlier_count += int(outlier_mask.sum())

            elif self.method == "remove":
                # 删除异常行（使用 zscore 判断）
                col_mean = df[col].mean()
                col_std = df[col].std()
                if col_std > 0:
                    z_scores = np.abs((df[col] - col_mean) / col_std)
                    df = df[z_scores <= self.zscore_threshold]

            elif self.method == "mark":
                # 只标记，不处理
                col_mean = df[col].mean()
                col_std = df[col].std()
                if col_std > 0:
                    z_scores = np.abs((df[col] - col_mean) / col_std)
                    outlier_mask = z_scores > self.zscore_threshold
                    if outlier_mask.any():
                        outlier_count += int(outlier_mask.sum())
                        if f"{col}_outlier" not in df.columns:
                            df[f"{col}_outlier"] = False
                        df.loc[outlier_mask, f"{col}_outlier"] = True

        self._stats.output_rows = len(df)
        self._stats.removed_rows = self._stats.input_rows - self._stats.output_rows
        self._stats.modified_rows = outlier_count
        self._stats.details.update(
            {
                "method": self.method,
                "columns_processed": cols_to_process,
                "total_outliers": int(outlier_count),
            }
        )

        return df

    def get_stats(self) -> CleaningStats | None:
        return self._stats


class DateConverter(BaseCleaner):
    """日期字符串转换器

    将各种格式的日期字符串转换为 Python date 对象。
    支持的格式：
    - YYYYMMDD (Tushare 格式，默认优先)
    - YYYY-MM-DD (ISO 格式)
    - YYYY/MM/DD
    - 其他 pandas 可识别的日期格式

    Attributes:
        columns: 要转换的列名列表，为空则自动检测
        date_suffixes: 自动检测时匹配的列名后缀
        default_format: 优先尝试的日期格式，默认 "%Y%m%d"
    """

    # 常见的日期列名后缀（大小写不敏感匹配）
    DATE_SUFFIXES = (
        "_date",
        "date",
        "_time",
        "time",
        "datetime",
        "_datetime",
        "timestamp",
        "_timestamp",
    )

    # 支持的日期格式（按优先级排序）
    DATE_FORMATS = [
        "%Y%m%d",       # 20250103 (Tushare)
        "%Y-%m-%d",     # 2025-01-03 (ISO)
        "%Y/%m/%d",     # 2025/01/03
        "%Y.%m.%d",     # 2025.01.03
        "%d/%m/%Y",     # 03/01/2025 (欧洲)
        "%m/%d/%Y",     # 01/03/2025 (美国)
    ]

    @property
    def name(self) -> str:
        return "date_converter"

    def __init__(
        self,
        columns: list[str] | None = None,
        date_suffixes: tuple[str, ...] | None = None,
        default_format: str | None = None,
    ):
        """初始化日期转换器

        Args:
            columns: 要转换的列名列表，为空则自动检测
            date_suffixes: 自定义日期列后缀，默认使用 DATE_SUFFIXES
            default_format: 优先尝试的日期格式，默认 "%Y%m%d"（Tushare 格式）
        """
        self.columns = columns or []
        self.date_suffixes = date_suffixes or self.DATE_SUFFIXES
        self.default_format = default_format or "%Y%m%d"
        self._stats: CleaningStats | None = None

    def _detect_date_columns(self, df: pd.DataFrame) -> list[str]:
        """自动检测日期列

        Args:
            df: 输入 DataFrame

        Returns:
            检测到的日期列名列表
        """
        date_cols = []
        col_lower_map = {col: col.lower() for col in df.columns}

        for col in df.columns:
            col_lower = col_lower_map[col]
            # 检查列名是否以日期相关后缀结尾（大小写不敏感）
            if any(col_lower.endswith(suffix) for suffix in self.date_suffixes):
                # 确保不是数值类型
                if not pd.api.types.is_numeric_dtype(df[col]):
                    date_cols.append(col)
        return date_cols

    def _try_batch_parse(self, series: pd.Series, fmt: str) -> pd.Series | None:
        """尝试用指定格式批量解析

        Args:
            series: 日期字符串 Series
            fmt: 日期格式

        Returns:
            解析成功的 Timestamp Series，失败返回 None
        """
        try:
            parsed = pd.to_datetime(series, format=fmt, errors="coerce")
            # 检查是否所有非空值都解析成功
            original_notna = series.notna()
            parsed_notna = parsed.notna()
            # 如果原来非空的值现在变成空了，说明格式不对
            if (original_notna & ~parsed_notna).any():
                return None
            return parsed
        except Exception:
            return None

    def _parse_single_date(self, value: str) -> date | None:
        """解析单个日期字符串（用于逐行回退）

        Args:
            value: 日期字符串

        Returns:
            解析成功返回 date 对象，失败返回 None
        """
        from datetime import datetime as dt

        # 先尝试默认格式
        formats_to_try = [self.default_format] + [
            f for f in self.DATE_FORMATS if f != self.default_format
        ]

        for fmt in formats_to_try:
            try:
                return dt.strptime(value, fmt).date()
            except (ValueError, TypeError):
                continue

        # 最后尝试 pandas 通用解析
        try:
            ts = pd.to_datetime(value, errors="coerce")
            if pd.notna(ts):
                return ts.date()
        except Exception:
            pass

        return None

    def _convert_column(self, series: pd.Series) -> pd.Series:
        """转换单列日期（简化版）

        策略：
        1. 检查是否已经是 date 对象
        2. 尝试用默认格式批量解析
        3. 用 pandas 通用解析
        4. 对剩余失败的行逐行解析

        Args:
            series: 日期列 Series

        Returns:
            转换后的 Series（包含 date 对象或 None）
        """
        # 1. 检查是否已经是 date 对象
        first_valid = series.dropna().iloc[0] if not series.dropna().empty else None
        if first_valid is not None and isinstance(first_valid, date):
            return series

        # 2. 尝试默认格式批量解析
        parsed = self._try_batch_parse(series, self.default_format)
        if parsed is not None:
            return parsed.dt.date

        # 3. 用 pandas 通用解析
        parsed = pd.to_datetime(series, errors="coerce")

        # 4. 对失败的行逐行解析（仅处理 NaT 且原始值非空的）
        failed_mask = parsed.isna() & series.notna()
        if failed_mask.any():
            # 用 apply 处理失败的行
            failed_series = series[failed_mask].astype(str)
            fallback_dates = failed_series.apply(self._parse_single_date)

            # 将解析成功的转为 Timestamp 以便合并
            fallback_ts = pd.to_datetime(fallback_dates.dropna())
            parsed = parsed.combine_first(fallback_ts)

        return parsed.dt.date

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """转换日期字符串为 date 对象（优化版）

        性能优化：
        - 批量解析优先（pandas 向量化）
        - 采样推断格式
        - 仅对失败行逐行解析

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
        batch_parsed_cols = []
        fallback_parsed_cols = []

        # 确定要转换的列
        columns_to_convert = self.columns if self.columns else self._detect_date_columns(df)

        for col in columns_to_convert:
            if col not in df.columns:
                continue

            try:
                # 记录解析前的 NaT 数量
                original_notna = df[col].notna().sum()

                # 使用优化的列转换方法
                df[col] = self._convert_column(df[col])
                converted_count += 1

                # 统计解析方式（用于调试）
                final_notna = df[col].notna().sum()
                if final_notna == original_notna:
                    batch_parsed_cols.append(col)
                else:
                    fallback_parsed_cols.append(col)

            except Exception:
                # 转换失败，保持原样
                pass

        self._stats.output_rows = len(df)
        self._stats.details = {
            "columns_converted": columns_to_convert,
            "converted_count": converted_count,
            "default_format": self.default_format,
            "batch_parsed": batch_parsed_cols,
            "fallback_parsed": fallback_parsed_cols,
        }

        return df

    def get_stats(self) -> CleaningStats | None:
        return self._stats
