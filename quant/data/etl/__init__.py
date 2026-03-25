"""数据清洗 ETL Pipeline

处理缺失值、异常值、数据对齐、复权、状态过滤等。

Example:
    >>> from quant.data.etl import create_default_pipeline
    >>> pipeline = create_default_pipeline(adjust_method="qfq")
    >>> df_cleaned = pipeline.run(df_raw)
"""

from .adjust import PriceAdjuster, adjust_volume, calculate_adj_factor
from .base import BaseCleaner, BaseFilter, BaseTransformer, CleaningStats
from .cleaners import DateConverter, DuplicateCleaner, MissingValueCleaner, OutlierCleaner
from .filters import StockStatusFilter, TradeableFilter
from .pipeline import (
    ETLPipeline,
    create_default_pipeline,
    create_minimal_pipeline,
    create_strict_pipeline,
)

__all__ = [
    # Base
    "BaseCleaner",
    "BaseFilter",
    "BaseTransformer",
    "CleaningStats",
    # Cleaners
    "DateConverter",
    "MissingValueCleaner",
    "DuplicateCleaner",
    "OutlierCleaner",
    # Adjust
    "PriceAdjuster",
    "calculate_adj_factor",
    "adjust_volume",
    # Filters
    "StockStatusFilter",
    "TradeableFilter",
    # Pipeline
    "ETLPipeline",
    "create_default_pipeline",
    "create_minimal_pipeline",
    "create_strict_pipeline",
]
