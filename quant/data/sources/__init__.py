"""数据源适配器

支持 Tushare、AKShare 等数据源。
"""

from quant.data.sources.base import BaseDataSource
from quant.data.sources.tushare_client import TushareClient
from quant.data.sources.akshare_client import AKShareClient
from quant.data.sources.validator import DataValidator, ValidationReport, validate_and_merge

__all__ = [
    "BaseDataSource",
    "TushareClient",
    "AKShareClient",
    "DataValidator",
    "ValidationReport",
    "validate_and_merge",
]
