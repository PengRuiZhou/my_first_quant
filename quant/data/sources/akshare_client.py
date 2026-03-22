"""AKShare 数据源适配器

使用 AKShare API 实现数据源接口。

注意：AKShare 接口命名和返回格式与 Tushare 差异较大，需要适配。
"""

import asyncio
from datetime import datetime

import akshare as ak
import pandas as pd
from loguru import logger

from quant.core import get_settings
from quant.data.sources.base import BaseDataSource


class AKShareClient(BaseDataSource):
    """AKShare 数据源适配器

    使用 AKShare 获取 A 股数据。

    AKShare 与 Tushare 的主要差异：
    1. 股票代码格式不同：AKShare 使用 "000001"，Tushare 使用 "000001.SZ"
    2. 接口命名不同：AKShare 使用中文函数名
    3. 返回字段命名不同：AKShare 使用中文字段名
    """

    def __init__(self):
        """初始化 AKShare 客户端"""
        settings = get_settings()
        self._timeout = settings.akshare.timeout
        self._retry_times = settings.akshare.retry_times

    @property
    def name(self) -> str:
        return "akshare"

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
        """将 Tushare 代码转换为 AKShare 格式

        Args:
            ts_code: Tushare 格式代码，如 "000001.SZ"

        Returns:
            股票代码，如 "000001"
        """
        return ts_code.split(".")[0]

    def _get_market_from_code(self, ts_code: str) -> str:
        """从 Tushare 代码获取市场"""
        suffix = ts_code.split(".")[1] if "." in ts_code else "SZ"
        return suffix

    async def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表

        AKShare 使用 stock_zh_a_spot_em 接口获取 A 股列表。
        """
        logger.info("正在从 AKShare 获取股票列表...")

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None, lambda: ak.stock_zh_a_spot_em()
        )

        # 字段映射
        result = pd.DataFrame()
        result["ts_code"] = df["代码"].apply(self._convert_code_to_ts)
        result["symbol"] = df["代码"]
        result["name"] = df["名称"]
        result["market"] = df["代码"].apply(
            lambda x: "SH" if x.startswith("6") else "SZ"
        )
        # AKShare 实时数据中没有行业、地域等字段
        result["area"] = None
        result["industry"] = None
        result["list_date"] = None
        result["delist_date"] = None
        result["is_active"] = True

        logger.info(f"获取到 {len(result)} 条股票信息")
        return result

    async def get_index_list(self) -> pd.DataFrame:
        """获取指数列表

        AKShare 使用 index_stock_info 接口获取指数列表。
        """
        logger.info("正在从 AKShare 获取指数列表...")

        loop = asyncio.get_event_loop()

        # 获取上证指数列表
        try:
            # AKShare 接口名可能变化，使用 getattr 动态调用
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

        if df_sh.empty and df_sz.empty:
            # 使用备用接口
            try:
                df = await loop.run_in_executor(
                    None, lambda: ak.index_stock_info()
                )
                result = pd.DataFrame()
                result["ts_code"] = df["index_code"].apply(
                    lambda x: f"{x}.SH" if str(x).startswith("0") else f"{x}.SZ"
                )
                result["name"] = df["index_name"]
                result["market"] = df["index_code"].apply(
                    lambda x: "SH" if str(x).startswith("0") else "SZ"
                )
                result["full_name"] = None
                result["publisher"] = None
                result["base_date"] = None
                result["base_point"] = None
                logger.info(f"获取到 {len(result)} 条指数信息")
                return result
            except Exception as e:
                logger.error(f"获取指数列表失败: {e}")
                return pd.DataFrame()

        df = pd.concat([df_sh, df_sz], ignore_index=True)

        result = pd.DataFrame()
        # 安全获取列，确保返回 Series
        code_col = df["指数代码"] if "指数代码" in df.columns else df["index_code"]
        name_col = df["指数简称"] if "指数简称" in df.columns else df["index_name"]

        result["ts_code"] = code_col.apply(
            lambda x: f"{x}.SH" if str(x).startswith("0") else f"{x}.SZ"
        )
        result["name"] = name_col
        result["market"] = df["market"]
        result["full_name"] = None
        result["publisher"] = None
        result["base_date"] = None
        result["base_point"] = None

        logger.info(f"获取到 {len(result)} 条指数信息")
        return result

    async def get_daily_quotes(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取日线行情

        AKShare 使用 stock_zh_a_hist 接口获取日线数据。
        """
        logger.debug(
            f"获取日线行情: ts_code={ts_code}, trade_date={trade_date}, "
            f"start_date={start_date}, end_date={end_date}"
        )

        loop = asyncio.get_event_loop()

        if trade_date:
            # 按日期获取所有股票行情
            try:
                df = await loop.run_in_executor(
                    None,
                    lambda: ak.stock_zh_a_spot_em(),
                )
                # AKShare 的实时数据不包含历史数据，这里需要其他接口
                logger.warning("AKShare 按日期获取全市场行情功能有限")
                return pd.DataFrame()
            except Exception as e:
                logger.error(f"获取日线行情失败: {e}")
                return pd.DataFrame()

        if ts_code:
            # 按股票代码获取历史数据
            symbol = self._convert_ts_to_code(ts_code)
            market = self._get_market_from_code(ts_code)

            # 转换日期格式
            start = start_date if start_date else "19900101"
            end = end_date if end_date else datetime.now().strftime("%Y%m%d")
            start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:]}"
            end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:]}"

            try:
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
                result["trade_date"] = pd.to_datetime(df["日期"]).dt.strftime(
                    "%Y%m%d"
                )
                result["open"] = df["开盘"]
                result["high"] = df["最高"]
                result["low"] = df["最低"]
                result["close"] = df["收盘"]
                result["vol"] = df["成交量"]
                result["amount"] = df["成交额"]
                result["change"] = df.get("涨跌额", None)
                result["pct_chg"] = df.get("涨跌幅", None)
                result["pre_close"] = df.get("昨收", None)

                return result
            except Exception as e:
                logger.error(f"获取 {ts_code} 日线行情失败: {e}")
                return pd.DataFrame()

        logger.warning("必须指定 ts_code 或 trade_date")
        return pd.DataFrame()

    async def get_index_quotes(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取指数行情

        AKShare 使用 index_zh_a_hist 接口获取指数历史数据。
        """
        logger.debug(
            f"获取指数行情: ts_code={ts_code}, trade_date={trade_date}"
        )

        if not ts_code:
            logger.warning("AKShare 获取指数行情需要指定 ts_code")
            return pd.DataFrame()

        loop = asyncio.get_event_loop()
        symbol = self._convert_ts_to_code(ts_code)
        market = self._get_market_from_code(ts_code)

        start = start_date if start_date else "19900101"
        end = end_date if end_date else datetime.now().strftime("%Y%m%d")
        start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:]}"
        end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:]}"

        try:
            df = await loop.run_in_executor(
                None,
                lambda: ak.index_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_fmt,
                    end_date=end_fmt,
                ),
            )

            result = pd.DataFrame()
            result["ts_code"] = ts_code
            result["trade_date"] = pd.to_datetime(df["日期"]).dt.strftime(
                "%Y%m%d"
            )
            result["open"] = df["开盘"]
            result["high"] = df["最高"]
            result["low"] = df["最低"]
            result["close"] = df["收盘"]
            result["vol"] = df.get("成交量", None)
            result["amount"] = df.get("成交额", None)
            result["change"] = df.get("涨跌额", None)
            result["pct_chg"] = df.get("涨跌幅", None)
            result["pre_close"] = df.get("昨收", None)

            return result
        except Exception as e:
            logger.error(f"获取 {ts_code} 指数行情失败: {e}")
            return pd.DataFrame()

    async def get_trade_calendar(
        self,
        exchange: str = "SSE",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取交易日历

        AKShare 使用 tool_trade_date_hist_sina 接口获取交易日历。
        """
        logger.debug(f"获取交易日历: exchange={exchange}")

        loop = asyncio.get_event_loop()

        try:
            dates = await loop.run_in_executor(
                None, lambda: ak.tool_trade_date_hist_sina()
            )

            # dates 是一个日期列表
            df = pd.DataFrame({"cal_date": dates})
            df["exchange"] = exchange
            df["is_open"] = True
            df["pretrade_date"] = None  # AKShare 不提供此字段

            # 过滤日期范围
            if start_date:
                df = df[df["cal_date"] >= start_date]
            if end_date:
                df = df[df["cal_date"] <= end_date]

            return df
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return pd.DataFrame()

    async def get_daily_basic(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取每日指标

        AKShare 的每日指标数据分散在多个接口中，这里使用实时数据接口。
        """
        logger.debug(f"获取每日指标: ts_code={ts_code}, trade_date={trade_date}")

        loop = asyncio.get_event_loop()

        try:
            # 使用实时行情数据作为替代
            df = await loop.run_in_executor(
                None, lambda: ak.stock_zh_a_spot_em()
            )

            if ts_code:
                symbol = self._convert_ts_to_code(ts_code)
                df = df[df["代码"] == symbol]

            result = pd.DataFrame()
            result["ts_code"] = df["代码"].apply(self._convert_code_to_ts)
            result["trade_date"] = datetime.now().strftime("%Y%m%d")
            result["close"] = df["最新价"]
            result["turnover_rate"] = df.get("换手率", None)
            result["pe"] = df.get("市盈率-动态", None)
            result["pb"] = df.get("市净率", None)
            result["total_mv"] = df.get("总市值", None)
            result["circ_mv"] = df.get("流通市值", None)

            # AKShare 实时数据中没有的字段
            result["turnover_rate_f"] = None
            result["volume_ratio"] = None
            result["pe_ttm"] = None
            result["ps"] = None
            result["ps_ttm"] = None
            result["dv_ratio"] = None

            return result
        except Exception as e:
            logger.error(f"获取每日指标失败: {e}")
            return pd.DataFrame()

    async def get_financial_indicator(
        self,
        ts_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str | None = None,
    ) -> pd.DataFrame:
        """获取财务指标

        AKShare 使用 stock_financial_analysis_indicator 接口获取财务指标。
        """
        logger.debug(f"获取财务指标: ts_code={ts_code}, period={period}")

        if not ts_code:
            logger.warning("AKShare 获取财务指标需要指定 ts_code")
            return pd.DataFrame()

        loop = asyncio.get_event_loop()
        symbol = self._convert_ts_to_code(ts_code)

        try:
            df = await loop.run_in_executor(
                None,
                lambda: ak.stock_financial_analysis_indicator(symbol=symbol),
            )

            result = pd.DataFrame()
            result["ts_code"] = ts_code
            result["end_date"] = df.get("日期", df.get("date", None))
            result["roe"] = df.get("净资产收益率", df.get("roe", None))
            result["netprofit_margin"] = df.get("销售净利率", None)
            result["grossprofit_margin"] = df.get("销售毛利率", None)
            result["current_ratio"] = df.get("流动比率", None)
            result["quick_ratio"] = df.get("速动比率", None)

            # AKShare 不提供的字段
            result["ann_date"] = None
            result["roe_dt"] = None
            result["roa"] = None
            result["debt_to_assets"] = None
            result["eps"] = None
            result["bvps"] = None

            return result
        except Exception as e:
            logger.error(f"获取 {ts_code} 财务指标失败: {e}")
            return pd.DataFrame()

    async def get_adj_factor(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """获取复权因子

        AKShare 通过 qfq/hfq 参数获取复权数据，但不直接提供复权因子。
        这里通过计算前复权价格与原始价格的比值来估算复权因子。
        """
        logger.debug(f"获取复权因子: ts_code={ts_code}")

        if not ts_code:
            logger.warning("AKShare 获取复权因子需要指定 ts_code")
            return pd.DataFrame()

        loop = asyncio.get_event_loop()
        symbol = self._convert_ts_to_code(ts_code)

        start = start_date if start_date else "19900101"
        end = end_date if end_date else datetime.now().strftime("%Y%m%d")
        start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:]}"
        end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:]}"

        try:
            # 获取不复权数据
            df_raw = await loop.run_in_executor(
                None,
                lambda: ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_fmt,
                    end_date=end_fmt,
                    adjust="",
                ),
            )

            # 获取前复权数据
            df_qfq = await loop.run_in_executor(
                None,
                lambda: ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_fmt,
                    end_date=end_fmt,
                    adjust="qfq",
                ),
            )

            # 计算复权因子
            result = pd.DataFrame()
            result["ts_code"] = ts_code
            result["trade_date"] = pd.to_datetime(df_raw["日期"]).dt.strftime(
                "%Y%m%d"
            )
            # 复权因子 = 前复权价格 / 原始价格
            result["adj_factor"] = df_qfq["收盘"] / df_raw["收盘"]

            return result
        except Exception as e:
            logger.error(f"获取 {ts_code} 复权因子失败: {e}")
            return pd.DataFrame()

    async def close(self) -> None:
        """关闭连接

        AKShare 使用 HTTP API，无需显式关闭。
        """
        pass
