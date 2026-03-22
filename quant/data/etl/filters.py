"""股票状态过滤器

用于过滤 ST、停牌、退市等不符合交易条件的股票。
"""

import re
from typing import Literal

import pandas as pd

from .base import BaseFilter, CleaningStats


class StockStatusFilter(BaseFilter):
    """股票状态过滤器

    维护股票状态信息，并根据条件过滤股票。
    """

    @property
    def name(self) -> str:
        return "stock_status_filter"

    def __init__(self):
        """初始化过滤器"""
        self.st_stocks: set[str] = set()      # ST 股票
        self.suspended: set[str] = set()      # 停牌股票
        self.delist: set[str] = set()         # 退市股票
        self._stats: CleaningStats | None = None

    def update_status(self, stock_info: pd.DataFrame) -> None:
        """更新股票状态

        从股票信息中提取状态信息。

        Args:
            stock_info: 股票信息 DataFrame，需包含 ts_code, name 列
                可选列：list_status（上市状态）, is_st
        """
        if stock_info is None or len(stock_info) == 0:
            return

        # 检查 ST 股票（从名称判断）
        if "name" in stock_info.columns:
            # ST 股票名称包含 ST、*ST、S*ST、SST 等
            st_pattern = re.compile(r"(\*ST|S\*?ST|ST)", re.IGNORECASE)
            st_mask = stock_info["name"].str.contains(st_pattern, na=False)
            self.st_stocks = set(stock_info.loc[st_mask, "ts_code"].tolist())

        # 检查退市股票
        if "list_status" in stock_info.columns:
            # list_status: L=上市, D=退市, P=暂停上市
            delist_mask = stock_info["list_status"].isin(["D", "P"])
            self.delist = set(stock_info.loc[delist_mask, "ts_code"].tolist())

        # 如果有明确的 is_st 列
        if "is_st" in stock_info.columns:
            st_mask = stock_info["is_st"] == True  # noqa: E712
            self.st_stocks.update(stock_info.loc[st_mask, "ts_code"].tolist())

    def set_suspended(self, suspended_codes: set[str]) -> None:
        """设置停牌股票

        Args:
            suspended_codes: 停牌股票代码集合
        """
        self.suspended = suspended_codes

    def filter(
        self,
        df: pd.DataFrame,
        exclude_st: bool = True,
        exclude_suspended: bool = True,
        exclude_delist: bool = True,
        min_turnover: float = 0.0,
        min_price: float = 0.0,
        max_price: float = float("inf"),
        min_volume: float = 0.0,
        codes_whitelist: set[str] | None = None,
        codes_blacklist: set[str] | None = None,
    ) -> pd.DataFrame:
        """过滤股票

        Args:
            df: 输入数据，需包含 ts_code 列
            exclude_st: 排除 ST 股票
            exclude_suspended: 排除停牌股票
            exclude_delist: 排除退市股票
            min_turnover: 最小换手率阈值（%）
            min_price: 最小价格
            max_price: 最大价格
            min_volume: 最小成交量
            codes_whitelist: 股票代码白名单（只保留这些股票）
            codes_blacklist: 股票代码黑名单（排除这些股票）

        Returns:
            过滤后的 DataFrame
        """
        self._stats = CleaningStats(self.name)
        self._stats.input_rows = len(df)

        if "ts_code" not in df.columns:
            self._stats.output_rows = len(df)
            self._stats.details = {"skipped": True, "reason": "no ts_code column"}
            return df

        original_len = len(df)
        exclusion_stats = {}

        # 1. 白名单过滤
        if codes_whitelist is not None:
            mask = df["ts_code"].isin(codes_whitelist)
            df = df[mask]
            exclusion_stats["whitelist_filtered"] = original_len - len(df)

        # 2. 黑名单过滤
        if codes_blacklist is not None:
            mask = ~df["ts_code"].isin(codes_blacklist)
            df = df[mask]
            exclusion_stats["blacklist_filtered"] = original_len - len(df)

        # 3. 排除 ST 股票
        if exclude_st and self.st_stocks:
            mask = ~df["ts_code"].isin(self.st_stocks)
            n_excluded = (~mask).sum()
            df = df[mask]
            exclusion_stats["st_excluded"] = int(n_excluded)

        # 4. 排除停牌股票
        if exclude_suspended and self.suspended:
            mask = ~df["ts_code"].isin(self.suspended)
            n_excluded = (~mask).sum()
            df = df[mask]
            exclusion_stats["suspended_excluded"] = int(n_excluded)

        # 5. 排除退市股票
        if exclude_delist and self.delist:
            mask = ~df["ts_code"].isin(self.delist)
            n_excluded = (~mask).sum()
            df = df[mask]
            exclusion_stats["delist_excluded"] = int(n_excluded)

        # 6. 换手率过滤
        if min_turnover > 0 and "turnover_rate" in df.columns:
            mask = df["turnover_rate"] >= min_turnover
            n_excluded = (~mask).sum()
            df = df[mask]
            exclusion_stats["low_turnover_excluded"] = int(n_excluded)

        # 7. 价格过滤
        if "close" in df.columns:
            if min_price > 0:
                mask = df["close"] >= min_price
                n_excluded = (~mask).sum()
                df = df[mask]
                exclusion_stats["low_price_excluded"] = int(n_excluded)

            if max_price < float("inf"):
                mask = df["close"] <= max_price
                n_excluded = (~mask).sum()
                df = df[mask]
                exclusion_stats["high_price_excluded"] = int(n_excluded)

        # 8. 成交量过滤
        if min_volume > 0 and "vol" in df.columns:
            mask = df["vol"] >= min_volume
            n_excluded = (~mask).sum()
            df = df[mask]
            exclusion_stats["low_volume_excluded"] = int(n_excluded)

        # 统计
        self._stats.output_rows = len(df)
        self._stats.removed_rows = self._stats.input_rows - self._stats.output_rows
        self._stats.details = {
            "exclude_st": exclude_st,
            "exclude_suspended": exclude_suspended,
            "exclude_delist": exclude_delist,
            "min_turnover": min_turnover,
            "st_stocks_count": len(self.st_stocks),
            "suspended_count": len(self.suspended),
            "delist_count": len(self.delist),
            **exclusion_stats,
        }

        return df

    def get_stats(self) -> CleaningStats | None:
        return self._stats

    def get_status_summary(self) -> dict:
        """获取状态摘要"""
        return {
            "st_stocks": len(self.st_stocks),
            "suspended": len(self.suspended),
            "delist": len(self.delist),
        }


class TradeableFilter(BaseFilter):
    """可交易股票过滤器

    组合多个条件，提供简化的过滤接口。
    """

    @property
    def name(self) -> str:
        return "tradeable_filter"

    def __init__(
        self,
        exclude_st: bool = True,
        exclude_suspended: bool = True,
        exclude_delist: bool = True,
        min_turnover: float = 0.0,
        min_price: float = 1.0,
        min_volume: float = 0.0,
        min_days_listed: int = 0,
    ):
        """初始化可交易过滤器

        Args:
            exclude_st: 排除 ST 股票
            exclude_suspended: 排除停牌股票
            exclude_delist: 排除退市股票
            min_turnover: 最小换手率（%）
            min_price: 最小价格（元）
            min_volume: 最小成交量（手）
            min_days_listed: 最小上市天数
        """
        self.exclude_st = exclude_st
        self.exclude_suspended = exclude_suspended
        self.exclude_delist = exclude_delist
        self.min_turnover = min_turnover
        self.min_price = min_price
        self.min_volume = min_volume
        self.min_days_listed = min_days_listed
        self._status_filter = StockStatusFilter()
        self._stats: CleaningStats | None = None

    def update_stock_status(self, stock_info: pd.DataFrame) -> None:
        """更新股票状态"""
        self._status_filter.update_status(stock_info)

    def filter(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """执行过滤

        Args:
            df: 输入数据
            **kwargs: 覆盖默认参数

        Returns:
            过滤后的 DataFrame
        """
        # 合并参数
        params = {
            "exclude_st": kwargs.get("exclude_st", self.exclude_st),
            "exclude_suspended": kwargs.get("exclude_suspended", self.exclude_suspended),
            "exclude_delist": kwargs.get("exclude_delist", self.exclude_delist),
            "min_turnover": kwargs.get("min_turnover", self.min_turnover),
            "min_price": kwargs.get("min_price", self.min_price),
            "min_volume": kwargs.get("min_volume", self.min_volume),
        }

        df = self._status_filter.filter(df, **params)

        # 上市天数过滤
        if self.min_days_listed > 0 and "list_date" in df.columns:
            # 计算上市天数
            df["_list_date"] = pd.to_datetime(df["list_date"], format="%Y%m%d", errors="coerce")
            if "trade_date" in df.columns:
                trade_date = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
                days_listed = (trade_date - df["_list_date"]).dt.days
                df = df[days_listed >= self.min_days_listed]
            df = df.drop(columns=["_list_date"])

        self._stats = self._status_filter.get_stats()
        return df

    def get_stats(self) -> CleaningStats | None:
        return self._stats
