"""Tushare 数据源适配器

使用 Tushare Pro API 实现数据源接口。
"""

import asyncio
from functools import wraps
from typing import Any, Callable

import pandas as pd
import tushare as ts
from loguru import logger

from quant.core import get_settings
from quant.data.sources.base import BaseDataSource


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
                        await asyncio.sleep(delay * (attempt + 1))
            # last_error must be set if we reach here (all retries failed)
            if last_error is None:
                raise RuntimeError(f"{func.__name__} failed with unknown error")
            raise last_error

        return wrapper

    return decorator


class TushareClient(BaseDataSource):
    """Tushare 数据源适配器

    使用 Tushare Pro API 获取 A 股数据。
    """

    # 字段映射：Tushare 字段 -> 标准字段
    STOCK_LIST_MAP = {
        "ts_code": "ts_code",
        "symbol": "symbol",
        "name": "name",
        "area": "area",
        "industry": "industry",
        "market": "market",
        "list_date": "list_date",
        "delist_date": "delist_date",
        "curr_type": "curr_type",
        "full_name": "full_name",
        "cnspell": "cnspell",
        "exchange": "exchange",
    }

    INDEX_LIST_MAP = {
        "ts_code": "ts_code",
        "name": "name",
        "full_name": "full_name",
        "market": "market",
        "publisher": "publisher",
        "base_date": "base_date",
        "base_point": "base_point",
        "list_date": "list_date",
        "weight_rule": "weight_rule",
    }

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

    TRADE_CAL_MAP = {
        "exchange": "exchange",
        "cal_date": "cal_date",
        "is_open": "is_open",
        "pretrade_date": "pretrade_date",
    }

    FINANCIAL_INDICATOR_MAP = {
        "ts_code": "ts_code",
        "ann_date": "ann_date",
        "end_date": "end_date",
        "roe": "roe",
        "roe_dt": "roe_dt",
        "roa": "roa",
        "netprofit_margin": "netprofit_margin",
        "grossprofit_margin": "grossprofit_margin",
        "debt_to_assets": "debt_to_assets",
        "current_ratio": "current_ratio",
        "quick_ratio": "quick_ratio",
        "eps": "eps",
        "bvps": "bvps",
    }

    ADJ_FACTOR_MAP = {
        "ts_code": "ts_code",
        "trade_date": "trade_date",
        "adj_factor": "adj_factor",
    }

    def __init__(self, token: str | None = None, api_url: str | None = None):
        """初始化 Tushare 客户端

        Args:
            token: Tushare API Token，为空则从配置读取
            api_url: 自定义 API 地址，为空则从配置读取
        """
        settings = get_settings()
        self._token = token or settings.tushare.token
        self._api_url = api_url or settings.tushare.api_url
        self._timeout = settings.tushare.timeout
        self._retry_times = settings.tushare.retry_times

        if not self._token:
            logger.warning("Tushare token 未配置，部分功能不可用")

        # 初始化 pro API
        ts.set_token(self._token)
        self._pro = ts.pro_api()

        # 设置自定义 API URL（如果配置了非默认值）
        if self._api_url and self._api_url != "http://api.tushare.pro":
            setattr(self._pro, "_DataApi__http_url", self._api_url)
            logger.info(f"使用自定义 Tushare API: {self._api_url}")

    @property
    def name(self) -> str:
        return "tushare"

    def _rename_columns(self, df: pd.DataFrame, field_map: dict[str, str]) -> pd.DataFrame:
        """重命名列

        只保留 field_map 中定义的字段。
        """
        if df.empty:
            return df

        # 只选择存在的列
        existing_cols = [c for c in field_map if c in df.columns]
        df = df[existing_cols].copy()
        df.columns = [field_map[c] for c in existing_cols]
        return df

    @retry_on_failure(max_retries=3)
    async def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        logger.info("正在从 Tushare 获取股票列表...")

        # Tushare API 是同步的，使用 run_in_executor
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: self._pro.stock_basic(
                exchange="", list_status="L", fields=",".join(self.STOCK_LIST_MAP.keys())
            ),
        )

        result = self._rename_columns(df, self.STOCK_LIST_MAP)

        # 添加 is_active 字段
        result["is_active"] = True

        logger.info(f"获取到 {len(result)} 条股票信息")
        return result

    @retry_on_failure(max_retries=3)
    async def get_index_list(self) -> pd.DataFrame:
        """获取指数列表"""
        logger.info("正在从 Tushare 获取指数列表...")

        loop = asyncio.get_event_loop()
        # 获取上证指数
        df_sh = await loop.run_in_executor(None, lambda: self._pro.index_basic(market="SSE"))
        # 获取深证指数
        df_sz = await loop.run_in_executor(None, lambda: self._pro.index_basic(market="SZSE"))

        df = pd.concat([df_sh, df_sz], ignore_index=True)
        result = self._rename_columns(df, self.INDEX_LIST_MAP)

        logger.info(f"获取到 {len(result)} 条指数信息")
        return result

    @retry_on_failure(max_retries=3)
    async def get_daily_quotes(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取日线行情"""
        logger.debug(
            f"获取日线行情: ts_code={ts_code}, trade_date={trade_date}, "
            f"start_date={start_date}, end_date={end_date}"
        )

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: self._pro.daily(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
            ),
        )

        result = self._rename_columns(df, self.DAILY_QUOTE_MAP)

        return result

    # 常用指数代码列表（约50个）
    COMMON_INDEX_CODES = [
        # 宽基指数
        "000001.SH",  # 上证综指
        "000016.SH",  # 上证50
        "000300.SH",  # 沪深300
        "000905.SH",  # 中证500
        "000852.SH",  # 中证1000
        "399001.SZ",  # 深证成指
        "399005.SZ",  # 中小板指
        "399006.SZ",  # 创业板指
        "399102.SZ",  # 创业板综
        # 上证行业指数
        "000032.SH",  # 上证能源
        "000033.SH",  # 上证材料
        "000034.SH",  # 上证工业
        "000035.SH",  # 上证可选
        "000036.SH",  # 上证消费
        "000037.SH",  # 上证医药
        "000038.SH",  # 上证金融
        "000039.SH",  # 上证信息
        "000040.SH",  # 上证电信
        "000041.SH",  # 上证公用
        # 沪深300行业指数
        "300能源.SH",  # 沪深300能源
        "300材料.SH",  # 沪深300材料
        "300工业.SH",  # 沪深300工业
        "300可选.SH",  # 沪深300可选
        "300消费.SH",  # 沪深300消费
        "300医药.SH",  # 沪深300医药
        "300金融.SH",  # 沪深300金融
        "300信息.SH",  # 沪深300信息
        "300电信.SH",  # 沪深300电信
        "300公用.SH",  # 沪深300公用
        # 中证行业指数
        "中证能源.SH",  # 中证能源
        "中证材料.SH",  # 中证材料
        "中证工业.SH",  # 中证工业
        "中证可选.SH",  # 中证可选
        "中证消费.SH",  # 中证消费
        "中证医药.SH",  # 中证医药
        "中证金融.SH",  # 中证金融
        "中证信息.SH",  # 中证信息
        "中证电信.SH",  # 中证电信
        "中证公用.SH",  # 中证公用
        # 主题指数
        "000688.SH",  # 科创50
        "399673.SZ",  # 创业板50
        "000991.SH",  # 全指医药
        "000993.SH",  # 全指信息
        "399971.SZ",  # 中证传媒
        "399986.SZ",  # 中证银行
        "399989.SZ",  # 中证医疗
        "931079.SH",  # 国企一带一路
        "931643.SH",  # 央企创新
    ]

    @retry_on_failure(max_retries=3)
    async def get_index_list(
        self,
        market: str | None = None,
        ts_code: str | None = None,
    ) -> pd.DataFrame:
        """获取指数基本信息列表

        Args:
            market: 市场代码 (SSE/SZSE)，为空则获取常用指数
            ts_code: 指数代码，指定则只获取该指数

        Returns:
            指数信息 DataFrame
        """
        logger.debug(f"获取指数列表: market={market}, ts_code={ts_code}")

        # 如果没有指定 market 或 ts_code，返回常用指数列表
        if market is None and ts_code is None:
            # 从 API 逐个获取这些指数的基本信息
            all_indexes = []
            loop = asyncio.get_event_loop()

            for code in self.COMMON_INDEX_CODES:
                try:
                    df = await loop.run_in_executor(
                        None,
                        lambda c=code: self._pro.index_basic(ts_code=c),
                    )
                    if not df.empty:
                        all_indexes.append(df)
                except Exception as e:
                    logger.warning(f"获取指数 {code} 失败: {e}")

            if all_indexes:
                result = pd.concat(all_indexes, ignore_index=True)
            else:
                result = pd.DataFrame()

            # 列名映射
            column_map = {
                "fullname": "full_name",
            }
            result = result.rename(columns=column_map)
            return result

        # 指定了 market 或 ts_code，从 API 获取
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: self._pro.index_basic(market=market, ts_code=ts_code),
        )

        column_map = {
            "fullname": "full_name",
        }
        result = df.rename(columns=column_map)
        return result

    @retry_on_failure(max_retries=3)
    async def get_index_quotes(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取指数行情"""
        logger.debug(
            f"获取指数行情: ts_code={ts_code}, trade_date={trade_date}, "
            f"start_date={start_date}, end_date={end_date}"
        )

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: self._pro.index_daily(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
            ),
        )

        result = self._rename_columns(df, self.DAILY_QUOTE_MAP)

        return result

    @retry_on_failure(max_retries=3)
    async def get_trade_calendar(
        self,
        exchange: str = "SSE",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取交易日历"""
        logger.debug(
            f"获取交易日历: exchange={exchange}, start_date={start_date}, end_date={end_date}"
        )

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: self._pro.trade_cal(
                exchange=exchange, start_date=start_date, end_date=end_date
            ),
        )

        result = self._rename_columns(df, self.TRADE_CAL_MAP)

        return result

    @retry_on_failure(max_retries=3)
    async def get_daily_basic(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取每日指标"""
        logger.debug(f"获取每日指标: ts_code={ts_code}, trade_date={trade_date}")

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: self._pro.daily_basic(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                fields=",".join(self.DAILY_BASIC_MAP.keys()),
            ),
        )

        result = self._rename_columns(df, self.DAILY_BASIC_MAP)

        return result

    @retry_on_failure(max_retries=3)
    async def get_financial_indicator(
        self,
        ts_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str | None = None,
    ) -> pd.DataFrame:
        """获取财务指标"""
        logger.debug(f"获取财务指标: ts_code={ts_code}, period={period}")

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: self._pro.fina_indicator(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                period=period,
                fields=",".join(self.FINANCIAL_INDICATOR_MAP.keys()),
            ),
        )

        result = self._rename_columns(df, self.FINANCIAL_INDICATOR_MAP)
        return result

    @retry_on_failure(max_retries=3)
    async def get_adj_factor(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取复权因子"""
        logger.debug(f"获取复权因子: ts_code={ts_code}, trade_date={trade_date}")

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: self._pro.adj_factor(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
            ),
        )

        result = self._rename_columns(df, self.ADJ_FACTOR_MAP)
        return result

    async def close(self) -> None:
        """关闭连接

        Tushare 使用 HTTP API，无需显式关闭。
        """
        pass
