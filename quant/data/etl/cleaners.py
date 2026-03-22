"""基础数据清洗器

包含：
- MissingValueCleaner: 缺失值处理
- DuplicateCleaner: 去重处理
- OutlierCleaner: 异常值处理
"""

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
                    df[cols_to_process] = (
                        df.groupby(self.group_by)[cols_to_process]
                        .ffill(limit=self.limit)
                    )
                else:  # bfill
                    df[cols_to_process] = (
                        df.groupby(self.group_by)[cols_to_process]
                        .bfill(limit=self.limit)
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
        self._stats.details.update({
            "method": self.method,
            "columns_processed": cols_to_process,
            "total_outliers": int(outlier_count),
        })

        return df

    def get_stats(self) -> CleaningStats | None:
        return self._stats
