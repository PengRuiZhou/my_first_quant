"""ETL 管道编排

组合多个清洗器、复权处理器、过滤器，形成完整的 ETL 管道。
"""

from typing import Literal

import pandas as pd
from loguru import logger

from .adjust import PriceAdjuster
from .base import BaseCleaner, CleaningStats
from .cleaners import DateConverter, DuplicateCleaner, MissingValueCleaner, OutlierCleaner
from .filters import StockStatusFilter


class ETLPipeline:
    """ETL 管道

    按顺序执行清洗、转换、过滤操作。
    支持链式调用配置。
    """

    def __init__(self):
        """初始化 ETL 管道"""
        self.cleaners: list[BaseCleaner] = []
        self.adjuster: PriceAdjuster | None = None
        self.status_filter: StockStatusFilter | None = None
        self._stats: list[CleaningStats] = []

    def add_cleaner(self, cleaner: BaseCleaner) -> "ETLPipeline":
        """添加清洗器

        Args:
            cleaner: 清洗器实例

        Returns:
            self（支持链式调用）
        """
        self.cleaners.append(cleaner)
        return self

    def set_adjuster(
        self,
        method: Literal["qfq", "hfq", "none"] = "qfq",
    ) -> "ETLPipeline":
        """设置复权方式

        Args:
            method: 复权方法

        Returns:
            self（支持链式调用）
        """
        self.adjuster = PriceAdjuster(method=method)
        return self

    def set_filter(
        self,
        stock_info: pd.DataFrame | None = None,
        suspended_codes: set[str] | None = None,
    ) -> "ETLPipeline":
        """设置过滤器

        Args:
            stock_info: 股票信息（用于更新 ST/退市状态）
            suspended_codes: 停牌股票代码集合

        Returns:
            self（支持链式调用）
        """
        self.status_filter = StockStatusFilter()
        if stock_info is not None:
            self.status_filter.update_status(stock_info)
        if suspended_codes is not None:
            self.status_filter.set_suspended(suspended_codes)
        return self

    def run(
        self,
        df: pd.DataFrame,
        adj_factor: pd.DataFrame | None = None,
        exclude_st: bool = True,
        exclude_suspended: bool = True,
        exclude_delist: bool = True,
        min_turnover: float = 0.0,
    ) -> pd.DataFrame:
        """执行 ETL 管道

        执行顺序：
        1. 清洗器（按添加顺序）
        2. 复权处理
        3. 状态过滤

        Args:
            df: 输入数据
            adj_factor: 复权因子数据（可选）
            exclude_st: 排除 ST 股票
            exclude_suspended: 排除停牌股票
            exclude_delist: 排除退市股票
            min_turnover: 最小换手率

        Returns:
            处理后的 DataFrame
        """
        self._stats = []
        input_rows = len(df)

        logger.info(f"ETL Pipeline 开始，输入 {input_rows} 行")

        # 1. 执行清洗器
        for cleaner in self.cleaners:
            df = cleaner.clean(df)
            stats = cleaner.get_stats()
            if stats is not None:
                self._stats.append(stats)
                logger.debug(f"清洗器 {cleaner.name}: {stats.removed_rows} 行被移除")

        # 2. 执行复权
        if self.adjuster is not None:
            df = self.adjuster.transform(df, adj_factor=adj_factor)
            stats = self.adjuster.get_stats()
            if stats is not None:
                self._stats.append(stats)
                logger.debug(f"复权处理: {stats.modified_rows} 行被处理")

        # 3. 执行过滤
        if self.status_filter is not None:
            df = self.status_filter.filter(
                df,
                exclude_st=exclude_st,
                exclude_suspended=exclude_suspended,
                exclude_delist=exclude_delist,
                min_turnover=min_turnover,
            )
            stats = self.status_filter.get_stats()
            if stats is not None:
                self._stats.append(stats)
                logger.debug(f"状态过滤: {stats.removed_rows} 行被移除")

        output_rows = len(df)
        logger.info(f"ETL Pipeline 完成，输出 {output_rows} 行，移除 {input_rows - output_rows} 行")

        return df

    def get_stats(self) -> list[dict]:
        """获取所有清洗统计信息"""
        return [s.to_dict() for s in self._stats]

    def get_summary(self) -> dict:
        """获取处理摘要"""
        if not self._stats:
            return {}

        total_removed = sum(s.removed_rows for s in self._stats)
        total_modified = sum(s.modified_rows for s in self._stats)

        return {
            "steps": len(self._stats),
            "total_removed": total_removed,
            "total_modified": total_modified,
            "cleaners": [c.name for c in self.cleaners],
            "adjuster": self.adjuster.method if self.adjuster else None,
            "has_filter": self.status_filter is not None,
        }


def create_default_pipeline(
    adjust_method: Literal["qfq", "hfq", "none"] = "qfq",
    stock_info: pd.DataFrame | None = None,
) -> ETLPipeline:
    """创建默认 ETL 管道

    默认管道包含：
    1. 日期字符串转换
    2. 去重处理
    3. 缺失值填充（前向填充）
    4. 异常值处理（缩尾）
    5. 前复权
    6. 状态过滤（排除 ST/停牌/退市）

    Args:
        adjust_method: 复权方法
        stock_info: 股票信息（用于状态过滤）

    Returns:
        配置好的 ETL 管道
    """
    pipeline = (
        ETLPipeline()
        .add_cleaner(DateConverter())
        .add_cleaner(DuplicateCleaner())
        .add_cleaner(MissingValueCleaner(strategy="ffill", limit=5))
        .add_cleaner(OutlierCleaner(method="winsorize", limits=(0.01, 0.99)))
        .set_adjuster(adjust_method)
    )

    if stock_info is not None:
        pipeline.set_filter(stock_info=stock_info)
    else:
        # 创建一个空的过滤器，后续可以更新状态
        pipeline.status_filter = StockStatusFilter()

    return pipeline


def create_minimal_pipeline() -> ETLPipeline:
    """创建最小 ETL 管道

    只包含基本清洗：日期转换 + 去重 + 缺失值处理
    """
    return (
        ETLPipeline()
        .add_cleaner(DateConverter())
        .add_cleaner(DuplicateCleaner())
        .add_cleaner(MissingValueCleaner(strategy="ffill", limit=5))
    )


def create_strict_pipeline(
    adjust_method: Literal["qfq", "hfq", "none"] = "qfq",
    stock_info: pd.DataFrame | None = None,
    min_turnover: float = 1.0,
) -> ETLPipeline:
    """创建严格 ETL 管道

    严格的清洗和过滤：
    - 日期转换
    - 异常值直接删除
    - 排除低换手率股票
    - 排除低价股

    Args:
        adjust_method: 复权方法
        stock_info: 股票信息
        min_turnover: 最小换手率（%）
    """
    pipeline = (
        ETLPipeline()
        .add_cleaner(DateConverter())
        .add_cleaner(DuplicateCleaner())
        .add_cleaner(MissingValueCleaner(strategy="drop"))  # 直接删除缺失值
        .add_cleaner(OutlierCleaner(method="remove"))  # 直接删除异常值
        .set_adjuster(adjust_method)
    )

    if stock_info is not None:
        pipeline.set_filter(stock_info=stock_info)
    else:
        pipeline.status_filter = StockStatusFilter()

    return pipeline
