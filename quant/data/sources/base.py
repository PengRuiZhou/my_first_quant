"""数据源抽象基类

定义数据源的统一接口，支持 Tushare、AKShare 等多数据源适配。
"""

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
        """获取股票列表

        Returns:
            DataFrame 包含字段:
            - ts_code: str, TS代码
            - symbol: str, 股票代码
            - name: str, 股票名称
            - area: str, 地域
            - industry: str, 所属行业
            - market: str, 市场类型
            - list_date: date, 上市日期
            - delist_date: date, 退市日期
            - is_active: bool, 是否在市
        """
        pass

    @abstractmethod
    async def get_index_list(self) -> pd.DataFrame:
        """获取指数列表

        Returns:
            DataFrame 包含字段:
            - ts_code: str, TS代码
            - name: str, 指数名称
            - market: str, 市场
            - publisher: str, 发布方
            - base_date: date, 基期
            - base_point: float, 基点
        """
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
        """获取日线行情

        Args:
            ts_code: 股票代码，如 "000001.SZ"，None 表示全部
            trade_date: 交易日期，格式 YYYYMMDD
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame 包含字段:
            - ts_code: str, TS代码
            - trade_date: date, 交易日期
            - open: float, 开盘价
            - high: float, 最高价
            - low: float, 最低价
            - close: float, 收盘价
            - pre_close: float, 昨收价
            - change: float, 涨跌额
            - pct_chg: float, 涨跌幅(%)
            - vol: float, 成交量(手)
            - amount: float, 成交额(千元)
        """
        pass

    @abstractmethod
    async def get_index_quotes(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取指数行情

        Args:
            ts_code: 指数代码，如 "000001.SH"（上证指数），None 表示全部
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame 包含字段同 get_daily_quotes
        """
        pass

    # ===== 市场数据 =====

    @abstractmethod
    async def get_trade_calendar(
        self,
        exchange: str = "SSE",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取交易日历

        Args:
            exchange: 交易所代码 SSE(上交所) SZSE(深交所)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame 包含字段:
            - exchange: str, 交易所
            - cal_date: date, 日期
            - is_open: bool, 是否交易
            - pretrade_date: date, 上一交易日
        """
        pass

    @abstractmethod
    async def get_daily_basic(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取每日指标

        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame 包含字段:
            - ts_code: str, TS代码
            - trade_date: date, 交易日期
            - close: float, 收盘价
            - turnover_rate: float, 换手率(%)
            - turnover_rate_f: float, 换手率（自由流通股）
            - volume_ratio: float, 量比
            - pe: float, 市盈率
            - pe_ttm: float, 市盈率TTM
            - pb: float, 市净率
            - ps: float, 市销率
            - ps_ttm: float, 市销率TTM
            - dv_ratio: float, 股息率(%)
            - total_mv: float, 总市值(万元)
            - circ_mv: float, 流通市值(万元)
        """
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
        """获取财务指标

        Args:
            ts_code: 股票代码
            start_date: 报告期开始日期
            end_date: 报告期结束日期
            period: 报告期，如 "20231231"

        Returns:
            DataFrame 包含字段:
            - ts_code: str, TS代码
            - ann_date: date, 公告日期
            - end_date: date, 报告期
            - roe: float, ROE(%)
            - roe_dt: float, ROE(摊薄)
            - roa: float, ROA
            - netprofit_margin: float, 销售净利率(%)
            - grossprofit_margin: float, 销售毛利率(%)
            - debt_to_assets: float, 资产负债率(%)
            - current_ratio: float, 流动比率
            - quick_ratio: float, 速动比率
            - eps: float, 每股收益
            - bvps: float, 每股净资产
        """
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
        """获取复权因子

        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame 包含字段:
            - ts_code: str, TS代码
            - trade_date: date, 交易日期
            - adj_factor: float, 复权因子
        """
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
