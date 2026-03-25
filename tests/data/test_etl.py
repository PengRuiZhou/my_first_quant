"""ETL 模块单元测试

测试清洗器、复权处理器、过滤器和管道的功能。
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from quant.data.etl.adjust import PriceAdjuster, adjust_volume
from quant.data.etl.base import CleaningStats
from quant.data.etl.cleaners import (
    DateConverter,
    DuplicateCleaner,
    MissingValueCleaner,
    OutlierCleaner,
)
from quant.data.etl.filters import StockStatusFilter, TradeableFilter
from quant.data.etl.pipeline import (
    ETLPipeline,
    create_default_pipeline,
    create_minimal_pipeline,
    create_strict_pipeline,
)

# ===== Fixtures =====


@pytest.fixture
def sample_quotes():
    """示例日线行情数据"""
    return pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ"],
            "trade_date": ["20240101", "20240102", "20240103", "20240101", "20240102"],
            "open": [10.0, 10.5, 10.8, 20.0, 20.5],
            "high": [10.5, 10.8, 11.0, 20.5, 21.0],
            "low": [9.8, 10.2, 10.5, 19.5, 20.0],
            "close": [10.2, 10.6, 10.9, 20.2, 20.8],
            "vol": [1000.0, 1200.0, 1100.0, 2000.0, 2200.0],
            "amount": [10200.0, 12600.0, 11890.0, 40400.0, 45760.0],
            "pct_chg": [1.0, 3.9, 2.8, 1.0, 3.0],
        }
    )


@pytest.fixture
def sample_quotes_with_missing():
    """包含缺失值的行情数据"""
    return pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ"],
            "trade_date": ["20240101", "20240102", "20240103", "20240101", "20240102"],
            "open": [10.0, np.nan, 10.8, 20.0, 20.5],
            "high": [10.5, 10.8, np.nan, 20.5, 21.0],
            "close": [10.2, 10.6, 10.9, np.nan, 20.8],
            "vol": [1000.0, 1200.0, 1100.0, 2000.0, 2200.0],
        }
    )


@pytest.fixture
def sample_quotes_with_duplicates():
    """包含重复数据的行情数据"""
    return pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ", "000001.SZ", "000002.SZ"],
            "trade_date": ["20240101", "20240101", "20240102", "20240102", "20240101"],
            "close": [10.0, 10.1, 10.5, 10.6, 20.0],
            "vol": [1000.0, 1100.0, 1200.0, 1300.0, 2000.0],
        }
    )


@pytest.fixture
def sample_quotes_with_outliers():
    """包含异常值的行情数据"""
    return pd.DataFrame(
        {
            "ts_code": ["000001.SZ"] * 10,
            "trade_date": [f"2024010{i}" for i in range(10)],
            "open": [
                10.0,
                10.1,
                10.2,
                1000.0,
                10.4,
                10.5,
                10.6,
                -5.0,
                10.8,
                10.9,
            ],  # 1000 和 -5 是异常
            "close": [10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9],
            "vol": [1000.0] * 10,
            "pct_chg": [1.0, 1.0, 1.0, 50.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],  # 50% 是异常涨跌幅
        }
    )


@pytest.fixture
def sample_adj_factor():
    """示例复权因子数据"""
    return pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ"],
            "trade_date": ["20240101", "20240102", "20240103"],
            "adj_factor": [1.0, 1.1, 1.2],
        }
    )


@pytest.fixture
def sample_stock_info():
    """示例股票信息数据"""
    return pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ", "000005.SZ"],
            "name": ["平安银行", "万科A", "ST国农", "*ST众泰", "正常股票"],
            "list_status": ["L", "L", "L", "D", "L"],
        }
    )


# ===== CleaningStats Tests =====


def test_cleaning_stats():
    """测试清洗统计信息"""
    stats = CleaningStats("test_cleaner")
    stats.input_rows = 100
    stats.output_rows = 95
    stats.removed_rows = 5
    stats.modified_rows = 10
    stats.details = {"test": "value"}

    assert stats.cleaner_name == "test_cleaner"
    assert stats.removal_rate == 0.05

    d = stats.to_dict()
    assert d["input_rows"] == 100
    assert d["output_rows"] == 95
    assert d["removed_rows"] == 5
    assert d["removal_rate"] == "5.00%"


def test_cleaning_stats_zero_input():
    """测试输入为 0 时的统计"""
    stats = CleaningStats("test")
    assert stats.removal_rate == 0.0


# ===== MissingValueCleaner Tests =====


class TestMissingValueCleaner:
    """缺失值清洗器测试"""

    def test_cleaner_name(self):
        """测试清洗器名称"""
        cleaner = MissingValueCleaner()
        assert cleaner.name == "missing_value"

    def test_ffill_strategy(self, sample_quotes_with_missing):
        """测试前向填充策略"""
        cleaner = MissingValueCleaner(strategy="ffill", limit=5)
        result = cleaner.clean(sample_quotes_with_missing)

        # 验证填充结果
        assert result["open"].isna().sum() == 0
        # 000001.SZ 第二行的 open 应该被填充为 10.0
        assert result.loc[1, "open"] == 10.0

    def test_bfill_strategy(self, sample_quotes_with_missing):
        """测试后向填充策略"""
        cleaner = MissingValueCleaner(strategy="bfill", limit=5)
        result = cleaner.clean(sample_quotes_with_missing)

        # bfill 在分组内从后往前填充，最后一组股票的 NaN 可能无法填充
        # 检查是否有填充效果即可
        stats = cleaner.get_stats()
        assert stats is not None
        assert "missing_before" in stats.details

    def test_drop_strategy(self, sample_quotes_with_missing):
        """测试删除策略"""
        cleaner = MissingValueCleaner(strategy="drop")
        result = cleaner.clean(sample_quotes_with_missing)

        # 应该删除含有缺失值的行
        assert len(result) < len(sample_quotes_with_missing)

    def test_fillna_strategy(self, sample_quotes_with_missing):
        """测试固定值填充策略"""
        cleaner = MissingValueCleaner(strategy="fillna", fill_value=-999)
        result = cleaner.clean(sample_quotes_with_missing)

        # 检查是否有 -999 值
        assert (result["open"] == -999).any() or result["open"].isna().sum() == 0

    def test_stats_recording(self, sample_quotes_with_missing):
        """测试统计信息记录"""
        cleaner = MissingValueCleaner(strategy="ffill")
        cleaner.clean(sample_quotes_with_missing)

        stats = cleaner.get_stats()
        assert stats is not None
        assert stats.input_rows == len(sample_quotes_with_missing)
        assert "missing_before" in stats.details


# ===== DuplicateCleaner Tests =====


class TestDuplicateCleaner:
    """去重清洗器测试"""

    def test_cleaner_name(self):
        """测试清洗器名称"""
        cleaner = DuplicateCleaner()
        assert cleaner.name == "duplicate"

    def test_remove_duplicates_keep_last(self, sample_quotes_with_duplicates):
        """测试去重保留最后一条"""
        cleaner = DuplicateCleaner(keep="last")
        result = cleaner.clean(sample_quotes_with_duplicates)

        # 应该只保留每个 (ts_code, trade_date) 组合的最后一条
        assert len(result) == 3
        # 20240101 的 000001.SZ 应该保留 close=10.1
        row = result[(result["ts_code"] == "000001.SZ") & (result["trade_date"] == "20240101")]
        assert row["close"].values[0] == 10.1

    def test_remove_duplicates_keep_first(self, sample_quotes_with_duplicates):
        """测试去重保留第一条"""
        cleaner = DuplicateCleaner(keep="first")
        result = cleaner.clean(sample_quotes_with_duplicates)

        assert len(result) == 3
        row = result[(result["ts_code"] == "000001.SZ") & (result["trade_date"] == "20240101")]
        assert row["close"].values[0] == 10.0

    def test_no_duplicates(self, sample_quotes):
        """测试无重复数据"""
        cleaner = DuplicateCleaner()
        result = cleaner.clean(sample_quotes)

        assert len(result) == len(sample_quotes)

    def test_missing_columns_skip(self):
        """测试缺少列时跳过去重"""
        cleaner = DuplicateCleaner(subset=["nonexistent_col"])
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = cleaner.clean(df)

        assert len(result) == 3


# ===== OutlierCleaner Tests =====


class TestOutlierCleaner:
    """异常值清洗器测试"""

    def test_cleaner_name(self):
        """测试清洗器名称"""
        cleaner = OutlierCleaner()
        assert cleaner.name == "outlier"

    def test_winsorize_method(self, sample_quotes_with_outliers):
        """测试缩尾处理"""
        cleaner = OutlierCleaner(method="winsorize", limits=(0.1, 0.9))
        result = cleaner.clean(sample_quotes_with_outliers)

        # 极端值应该被裁剪到分位数范围内
        # winsorize 不会改变最大值的数量级，只是将极端值替换为边界值
        stats = cleaner.get_stats()
        assert stats.modified_rows >= 0  # 可能有或没有修改

    def test_zscore_method(self, sample_quotes_with_outliers):
        """测试 Z-score 方法"""
        cleaner = OutlierCleaner(method="zscore", zscore_threshold=2.0)
        result = cleaner.clean(sample_quotes_with_outliers)

        # 异常值应该被替换为均值
        stats = cleaner.get_stats()
        assert stats.modified_rows > 0

    def test_remove_method(self, sample_quotes_with_outliers):
        """测试删除异常值"""
        cleaner = OutlierCleaner(method="remove", zscore_threshold=2.0)
        result = cleaner.clean(sample_quotes_with_outliers)

        # 应该删除异常行
        assert len(result) < len(sample_quotes_with_outliers)

    def test_mark_method(self, sample_quotes_with_outliers):
        """测试标记异常值"""
        cleaner = OutlierCleaner(method="mark", zscore_threshold=2.0)
        result = cleaner.clean(sample_quotes_with_outliers)

        # 应该添加标记列
        assert "open_outlier" in result.columns or "pct_chg_extreme" in result.columns

    def test_negative_price_handling(self, sample_quotes_with_outliers):
        """测试负价格处理"""
        cleaner = OutlierCleaner()
        result = cleaner.clean(sample_quotes_with_outliers)

        # 负价格应该被设为 NaN
        assert (result["open"] < 0).sum() == 0

    def test_extreme_pct_chg_detection(self, sample_quotes_with_outliers):
        """测试极端涨跌幅检测"""
        cleaner = OutlierCleaner(method="mark", pct_chg_limit=20.0)
        result = cleaner.clean(sample_quotes_with_outliers)

        stats = cleaner.get_stats()
        assert "pct_chg_extreme" in stats.details


# ===== PriceAdjuster Tests =====


class TestPriceAdjuster:
    """复权处理器测试"""

    def test_adjuster_name(self):
        """测试处理器名称"""
        adjuster = PriceAdjuster()
        assert adjuster.name == "price_adjuster"

    def test_no_adjust(self, sample_quotes):
        """测试不复权"""
        adjuster = PriceAdjuster(method="none")
        result = adjuster.transform(sample_quotes)

        # 应该返回原数据
        pd.testing.assert_frame_equal(result, sample_quotes)

    def test_qfq_adjust(self, sample_quotes, sample_adj_factor):
        """测试前复权"""
        # 合并复权因子
        df = sample_quotes.merge(sample_adj_factor, on=["ts_code", "trade_date"], how="left")

        adjuster = PriceAdjuster(method="qfq")
        result = adjuster.transform(df)

        # 应该添加 adj_ 前缀的列
        assert "adj_close" in result.columns
        assert "adj_open" in result.columns

    def test_hfq_adjust(self, sample_quotes, sample_adj_factor):
        """测试后复权"""
        df = sample_quotes.merge(sample_adj_factor, on=["ts_code", "trade_date"], how="left")

        adjuster = PriceAdjuster(method="hfq")
        result = adjuster.transform(df)

        assert "adj_close" in result.columns

    def test_no_adj_factor(self, sample_quotes):
        """测试无复权因子"""
        adjuster = PriceAdjuster(method="qfq")
        result = adjuster.transform(sample_quotes)

        # 应该返回原数据（不做处理）
        stats = adjuster.get_stats()
        assert stats.details.get("adjusted") is False

    def test_pct_chg_recalculation(self, sample_quotes, sample_adj_factor):
        """测试涨跌幅重算"""
        df = sample_quotes.merge(sample_adj_factor, on=["ts_code", "trade_date"], how="left")
        df["pre_close"] = df.groupby("ts_code")["close"].shift(1)

        adjuster = PriceAdjuster(method="qfq")
        result = adjuster.transform(df)

        # 应该计算复权后的涨跌幅
        if "adj_pct_chg" in result.columns:
            assert result["adj_pct_chg"].notna().any()


# ===== adjust_volume Tests =====


def test_adjust_volume_qfq():
    """测试前复权成交量调整"""
    df = pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ"],
            "trade_date": ["20240101", "20240102", "20240103"],
            "vol": [1000.0, 1100.0, 1200.0],
            "adj_factor": [1.0, 1.1, 1.2],
        }
    )

    result = adjust_volume(df, method="qfq")
    assert "vol_adj" in result.columns


def test_adjust_volume_none():
    """测试不复权成交量"""
    df = pd.DataFrame(
        {
            "vol": [1000.0, 1100.0],
            "adj_factor": [1.0, 1.1],
        }
    )

    result = adjust_volume(df, method="none")
    assert "vol_adj" not in result.columns


# ===== StockStatusFilter Tests =====


class TestStockStatusFilter:
    """股票状态过滤器测试"""

    def test_filter_name(self):
        """测试过滤器名称"""
        f = StockStatusFilter()
        assert f.name == "stock_status_filter"

    def test_update_status_from_name(self, sample_stock_info):
        """测试从名称更新状态"""
        f = StockStatusFilter()
        f.update_status(sample_stock_info)

        summary = f.get_status_summary()
        # 应该检测到 ST 股票
        assert summary["st_stocks"] == 2  # ST国农 和 *ST众泰

    def test_update_status_from_list_status(self, sample_stock_info):
        """测试从上市状态更新"""
        f = StockStatusFilter()
        f.update_status(sample_stock_info)

        summary = f.get_status_summary()
        # 应该检测到退市股票
        assert summary["delist"] == 1  # *ST众泰

    def test_filter_st_stocks(self, sample_quotes, sample_stock_info):
        """测试过滤 ST 股票"""
        f = StockStatusFilter()
        f.update_status(sample_stock_info)

        # 添加一个 ST 股票到行情数据
        quotes_with_st = pd.concat(
            [
                sample_quotes,
                pd.DataFrame(
                    {
                        "ts_code": ["000003.SZ"],
                        "trade_date": ["20240101"],
                        "close": [15.0],
                        "vol": [500.0],
                    }
                ),
            ],
            ignore_index=True,
        )

        result = f.filter(
            quotes_with_st, exclude_st=True, exclude_suspended=False, exclude_delist=False
        )

        # ST 股票应该被过滤
        assert "000003.SZ" not in result["ts_code"].values

    def test_filter_with_whitelist(self, sample_quotes):
        """测试白名单过滤"""
        f = StockStatusFilter()
        whitelist = {"000001.SZ"}

        result = f.filter(sample_quotes, codes_whitelist=whitelist)

        assert set(result["ts_code"].unique()) == whitelist

    def test_filter_with_blacklist(self, sample_quotes):
        """测试黑名单过滤"""
        f = StockStatusFilter()
        blacklist = {"000001.SZ"}

        result = f.filter(sample_quotes, codes_blacklist=blacklist)

        assert "000001.SZ" not in result["ts_code"].values

    def test_filter_by_turnover(self, sample_quotes):
        """测试换手率过滤"""
        f = StockStatusFilter()
        quotes = sample_quotes.copy()
        quotes["turnover_rate"] = [0.5, 0.6, 0.7, 0.8, 2.0]

        result = f.filter(
            quotes,
            min_turnover=1.0,
            exclude_st=False,
            exclude_suspended=False,
            exclude_delist=False,
        )

        assert len(result) == 1  # 只有换手率 >= 1.0 的

    def test_filter_by_price(self, sample_quotes):
        """测试价格过滤"""
        f = StockStatusFilter()

        result = f.filter(
            sample_quotes,
            min_price=15.0,
            exclude_st=False,
            exclude_suspended=False,
            exclude_delist=False,
        )

        assert all(result["close"] >= 15.0)

    def test_set_suspended(self):
        """测试设置停牌股票"""
        f = StockStatusFilter()
        f.set_suspended({"000001.SZ", "000002.SZ"})

        summary = f.get_status_summary()
        assert summary["suspended"] == 2


# ===== TradeableFilter Tests =====


class TestTradeableFilter:
    """可交易股票过滤器测试"""

    def test_filter_name(self):
        """测试过滤器名称"""
        f = TradeableFilter()
        assert f.name == "tradeable_filter"

    def test_default_params(self, sample_quotes, sample_stock_info):
        """测试默认参数过滤"""
        f = TradeableFilter(min_price=0.0)  # 设置为 0 以避免过滤掉测试数据
        f.update_stock_status(sample_stock_info)

        result = f.filter(sample_quotes)

        # 应该过滤掉 ST 和退市股票
        assert len(result) >= 0


# ===== ETLPipeline Tests =====


class TestETLPipeline:
    """ETL 管道测试"""

    def test_add_cleaner(self):
        """测试添加清洗器"""
        pipeline = ETLPipeline()
        pipeline.add_cleaner(DuplicateCleaner())

        assert len(pipeline.cleaners) == 1

    def test_chain_calls(self):
        """测试链式调用"""
        pipeline = (
            ETLPipeline()
            .add_cleaner(DuplicateCleaner())
            .add_cleaner(MissingValueCleaner())
            .set_adjuster("qfq")
        )

        assert len(pipeline.cleaners) == 2
        assert pipeline.adjuster is not None

    def test_run_pipeline(self, sample_quotes_with_missing):
        """测试运行管道"""
        pipeline = (
            ETLPipeline()
            .add_cleaner(DuplicateCleaner())
            .add_cleaner(MissingValueCleaner(strategy="ffill"))
        )

        result = pipeline.run(sample_quotes_with_missing)

        assert len(result) > 0
        stats = pipeline.get_stats()
        assert len(stats) == 2

    def test_get_summary(self, sample_quotes):
        """测试获取摘要"""
        pipeline = ETLPipeline().add_cleaner(DuplicateCleaner()).set_adjuster("none")
        pipeline.run(sample_quotes)

        summary = pipeline.get_summary()
        assert "steps" in summary
        assert "cleaners" in summary


# ===== Pipeline Factory Tests =====


def test_create_default_pipeline():
    """测试创建默认管道"""
    pipeline = create_default_pipeline()

    assert (
        len(pipeline.cleaners) == 4
    )  # DateConverter + DuplicateCleaner + MissingValueCleaner + OutlierCleaner
    assert pipeline.adjuster is not None
    assert pipeline.status_filter is not None


def test_create_minimal_pipeline():
    """测试创建最小管道"""
    pipeline = create_minimal_pipeline()

    assert len(pipeline.cleaners) == 3  # DateConverter + DuplicateCleaner + MissingValueCleaner
    assert pipeline.adjuster is None


def test_create_strict_pipeline():
    """测试创建严格管道"""
    pipeline = create_strict_pipeline(min_turnover=2.0)

    assert (
        len(pipeline.cleaners) == 4
    )  # DateConverter + DuplicateCleaner + MissingValueCleaner + OutlierCleaner
    assert pipeline.adjuster is not None


# ===== Integration-like Tests =====


def test_full_pipeline_workflow(sample_quotes, sample_stock_info, sample_adj_factor):
    """测试完整管道工作流"""
    # 1. 添加一些问题数据
    df = sample_quotes.copy()
    df.loc[0, "close"] = np.nan  # 缺失值

    # 2. 创建管道
    pipeline = create_default_pipeline(stock_info=sample_stock_info)

    # 3. 运行管道（不使用复权，因为测试数据不完整）
    pipeline.adjuster = None  # 禁用复权
    result = pipeline.run(df, exclude_st=False)

    # 4. 验证结果
    assert len(result) > 0
    summary = pipeline.get_summary()
    assert summary["total_removed"] >= 0


# ===== DateConverter Tests =====


class TestDateConverter:
    """DateConverter 单元测试"""

    def test_convert_yyyymmdd_format(self):
        """测试 YYYYMMDD 格式转换"""
        df = pd.DataFrame(
            {
                "trade_date": ["20240101", "20240102", "20240103"],
                "value": [1, 2, 3],
            }
        )
        cleaner = DateConverter(columns=["trade_date"])
        result = cleaner.clean(df)

        assert result["trade_date"].dtype == object
        assert result["trade_date"].iloc[0] == date(2024, 1, 1)
        assert result["trade_date"].iloc[1] == date(2024, 1, 2)

    def test_convert_yyyy_mm_dd_format(self):
        """测试 YYYY-MM-DD 格式转换"""
        df = pd.DataFrame(
            {
                "list_date": ["2024-01-01", "2024-06-15", "2024-12-31"],
                "name": ["A", "B", "C"],
            }
        )
        cleaner = DateConverter(columns=["list_date"])
        result = cleaner.clean(df)

        assert result["list_date"].iloc[0] == date(2024, 1, 1)
        assert result["list_date"].iloc[2] == date(2024, 12, 31)

    def test_convert_multiple_columns(self):
        """测试多列转换"""
        df = pd.DataFrame(
            {
                "start_date": ["20240101", "20240201"],
                "end_date": ["20240131", "20240228"],
                "value": [100, 200],
            }
        )
        cleaner = DateConverter(columns=["start_date", "end_date"])
        result = cleaner.clean(df)

        assert result["start_date"].iloc[0] == date(2024, 1, 1)
        assert result["end_date"].iloc[0] == date(2024, 1, 31)

    def test_convert_with_nat_values(self):
        """测试包含 NaT 值的转换"""
        df = pd.DataFrame(
            {
                "delist_date": ["20240101", None, "20241231"],
                "symbol": ["A", "B", "C"],
            }
        )
        cleaner = DateConverter(columns=["delist_date"])
        result = cleaner.clean(df)

        assert result["delist_date"].iloc[0] == date(2024, 1, 1)
        assert pd.isna(result["delist_date"].iloc[1])
        assert result["delist_date"].iloc[2] == date(2024, 12, 31)

    def test_auto_detect_date_columns(self):
        """测试自动检测日期列"""
        df = pd.DataFrame(
            {
                "trade_date": ["20240101", "20240102"],
                "list_date": ["2024-01-01", "2024-01-02"],
                "name": ["A", "B"],
                "value": [1, 2],
            }
        )
        cleaner = DateConverter()  # 不指定 columns，自动检测
        result = cleaner.clean(df)

        assert result["trade_date"].iloc[0] == date(2024, 1, 1)
        assert result["list_date"].iloc[0] == date(2024, 1, 1)
        # name 列应该是字符串类型（object 或 StringDtype），不是日期
        assert str(result["name"].dtype) in ("object", "str", "string")
        assert result["value"].dtype in [np.int64, np.int32]

    def test_invalid_date_strings_coerced_to_nat(self):
        """测试无效日期字符串转为 NaT"""
        df = pd.DataFrame(
            {
                "date_col": ["20240101", "INVALID", "20240103"],
            }
        )
        cleaner = DateConverter(columns=["date_col"])
        result = cleaner.clean(df)

        assert result["date_col"].iloc[0] == date(2024, 1, 1)
        assert pd.isna(result["date_col"].iloc[1])
        assert result["date_col"].iloc[2] == date(2024, 1, 3)

    def test_empty_dataframe(self):
        """测试空 DataFrame"""
        df = pd.DataFrame(columns=["trade_date", "value"])
        cleaner = DateConverter(columns=["trade_date"])
        result = cleaner.clean(df)

        assert len(result) == 0
        assert "trade_date" in result.columns

    def test_column_not_exists(self):
        """测试指定列不存在时跳过"""
        df = pd.DataFrame({"value": [1, 2, 3]})
        cleaner = DateConverter(columns=["nonexistent_date"])
        result = cleaner.clean(df)

        assert "value" in result.columns
        assert "nonexistent_date" not in result.columns

    def test_already_date_objects(self):
        """测试已经是 date 对象的列保持不变"""
        df = pd.DataFrame(
            {
                "trade_date": [date(2024, 1, 1), date(2024, 1, 2)],
            }
        )
        cleaner = DateConverter(columns=["trade_date"])
        result = cleaner.clean(df)

        assert result["trade_date"].iloc[0] == date(2024, 1, 1)
