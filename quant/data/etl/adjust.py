"""复权处理器

支持前复权(qfq)、后复权(hfq)、不复权(none)三种模式。
"""

from typing import Literal

import numpy as np
import pandas as pd

from .base import BaseTransformer, CleaningStats


class PriceAdjuster(BaseTransformer):
    """复权处理器

    复权用于消除分红、拆股等事件对价格的影响，
    使价格序列具有连续性和可比性。

    前复权 (qfq): 以最新价格为基准，调整历史价格
        adj_price = price * adj_factor / latest_adj_factor

    后复权 (hfq): 以上市价格为基准，调整当前价格
        adj_price = price * adj_factor

    不复权 (none): 使用原始价格
    """

    @property
    def name(self) -> str:
        return "price_adjuster"

    def __init__(self, method: Literal["qfq", "hfq", "none"] = "qfq"):
        """初始化复权处理器

        Args:
            method: 复权方法
                - qfq: 前复权（以最新价格为基准）
                - hfq: 后复权（以上市价格为基准）
                - none: 不复权
        """
        self.method = method
        self._stats: CleaningStats | None = None

    def transform(
        self,
        df: pd.DataFrame,
        adj_factor: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """应用复权因子

        Args:
            df: 日线行情数据，需包含 open, high, low, close, ts_code, trade_date 列
            adj_factor: 复权因子数据，需包含 ts_code, trade_date, adj_factor 列

        Returns:
            复权后的 DataFrame

        Note:
            如果 adj_factor 为 None，尝试从 df 中获取 adj_factor 列
        """
        self._stats = CleaningStats(self.name)
        self._stats.input_rows = len(df)

        if self.method == "none":
            self._stats.output_rows = len(df)
            self._stats.details = {"method": "none", "adjusted": False}
            return df

        df = df.copy()

        # 获取复权因子
        if adj_factor is not None:
            # 合并复权因子
            df = df.merge(
                adj_factor[["ts_code", "trade_date", "adj_factor"]],
                on=["ts_code", "trade_date"],
                how="left",
            )
        elif "adj_factor" not in df.columns:
            # 无复权因子数据
            self._stats.output_rows = len(df)
            self._stats.details = {"method": self.method, "adjusted": False, "reason": "no adj_factor"}
            return df

        # 确保按股票和日期排序
        df = df.sort_values(["ts_code", "trade_date"])

        # 价格列
        price_cols = ["open", "high", "low", "close", "pre_close"]
        existing_price_cols = [c for c in price_cols if c in df.columns]

        if self.method == "qfq":
            # 前复权：以每只股票最新复权因子为基准
            df["_latest_adj"] = df.groupby("ts_code")["adj_factor"].transform("last")
            adj_ratio = df["adj_factor"] / df["_latest_adj"]

            for col in existing_price_cols:
                df[f"adj_{col}"] = df[col] * adj_ratio

            # 删除临时列
            df = df.drop(columns=["_latest_adj"])

        elif self.method == "hfq":
            # 后复权：直接乘以复权因子
            for col in existing_price_cols:
                df[f"adj_{col}"] = df[col] * df["adj_factor"]

        # 重算涨跌幅
        if "adj_close" in df.columns and "adj_pre_close" in df.columns:
            df["adj_pct_chg"] = (df["adj_close"] - df["adj_pre_close"]) / df["adj_pre_close"] * 100
        elif "adj_close" in df.columns:
            df = self._recalculate_pct_chg(df)

        # 统计
        n_adjusted = df["adj_factor"].notna().sum()
        self._stats.output_rows = len(df)
        self._stats.modified_rows = int(n_adjusted)
        self._stats.details = {
            "method": self.method,
            "adjusted": True,
            "rows_adjusted": int(n_adjusted),
            "price_cols": existing_price_cols,
        }

        return df

    def _recalculate_pct_chg(self, df: pd.DataFrame) -> pd.DataFrame:
        """复权后重算涨跌幅

        基于复权后的收盘价计算涨跌幅。
        """
        if "adj_close" not in df.columns:
            return df

        df = df.copy()

        # 按股票分组计算前一日复权收盘价
        df["_prev_adj_close"] = df.groupby("ts_code")["adj_close"].shift(1)

        # 计算涨跌幅
        mask = df["_prev_adj_close"].notna() & (df["_prev_adj_close"] != 0)
        df.loc[mask, "adj_pct_chg"] = (
            (df.loc[mask, "adj_close"] - df.loc[mask, "_prev_adj_close"])
            / df.loc[mask, "_prev_adj_close"]
            * 100
        )

        # 删除临时列
        df = df.drop(columns=["_prev_adj_close"])

        return df

    def get_stats(self) -> CleaningStats | None:
        return self._stats


def calculate_adj_factor(
    df: pd.DataFrame,
    dividend_data: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """计算复权因子

    从分红送股数据计算复权因子。
    如果没有分红数据，返回全为 1 的复权因子。

    Args:
        df: 日线行情数据
        dividend_data: 分红送股数据，需包含 ts_code, ann_date, div_amt, split_ratio 列

    Returns:
        包含 ts_code, trade_date, adj_factor 的 DataFrame
    """
    # 初始化复权因子为 1
    result = df[["ts_code", "trade_date"]].copy()
    result["adj_factor"] = 1.0

    if dividend_data is None or len(dividend_data) == 0:
        return result

    # TODO: 根据分红送股数据计算复权因子
    # 这需要更复杂的逻辑来处理分红和拆股事件
    # 暂时返回全为 1 的复权因子

    return result


def adjust_volume(
    df: pd.DataFrame,
    method: Literal["qfq", "hfq", "none"] = "qfq",
) -> pd.DataFrame:
    """调整成交量

    复权时成交量也需要相应调整。
    - 前复权: vol_adj = vol * latest_adj_factor / adj_factor
    - 后复权: vol_adj = vol / adj_factor

    Args:
        df: 包含 vol 和 adj_factor 列的 DataFrame
        method: 复权方法

    Returns:
        添加 vol_adj 列的 DataFrame
    """
    if method == "none" or "adj_factor" not in df.columns:
        return df

    df = df.copy()

    if method == "qfq":
        df["_latest_adj"] = df.groupby("ts_code")["adj_factor"].transform("last")
        df["vol_adj"] = df["vol"] * df["_latest_adj"] / df["adj_factor"]
        df = df.drop(columns=["_latest_adj"])
    else:  # hfq
        # 后复权时，成交量除以复权因子
        mask = df["adj_factor"] != 0
        df.loc[mask, "vol_adj"] = df.loc[mask, "vol"] / df.loc[mask, "adj_factor"]

    return df
