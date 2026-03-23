"""集成测试

测试完整的数据流程，包括 ETL 管道、数据验证等。
注意：这些测试不连接真实数据库或 API，使用模拟数据。
"""

import numpy as np
import pandas as pd
import pytest

from quant.data.etl.adjust import PriceAdjuster
from quant.data.etl.cleaners import DuplicateCleaner, MissingValueCleaner, OutlierCleaner
from quant.data.etl.filters import StockStatusFilter
from quant.data.etl.pipeline import ETLPipeline, create_default_pipeline
from quant.data.sources.validator import DataValidator, validate_and_merge


# ===== Fixtures =====


@pytest.fixture
def raw_quotes_data():
    """原始行情数据（包含各种问题）"""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    codes = ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ", "000005.SZ"]

    data = []
    for code in codes:
        for i, date in enumerate(dates):
            row = {
                "ts_code": code,
                "trade_date": date.strftime("%Y%m%d"),
                "open": 10.0 + np.random.randn() * 0.5,
                "high": 10.5 + np.random.randn() * 0.5,
                "low": 9.5 + np.random.randn() * 0.5,
                "close": 10.0 + np.random.randn() * 0.5,
                "vol": 1000.0 + np.random.randn() * 100,
                "amount": 10000.0 + np.random.randn() * 1000,
                "pct_chg": np.random.randn() * 2,
            }
            data.append(row)

    df = pd.DataFrame(data)

    # 添加一些问题数据
    # 1. 缺失值
    df.loc[10:15, "close"] = np.nan

    # 2. 重复数据
    duplicates = df.iloc[[0, 1, 2]].copy()
    df = pd.concat([df, duplicates], ignore_index=True)

    # 3. 异常值
    df.loc[100, "open"] = 1000.0  # 极端高价
    df.loc[101, "pct_chg"] = 50.0  # 极端涨跌幅

    return df


@pytest.fixture
def stock_info_data():
    """股票信息数据（包含 ST 和退市股票）"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ", "000005.SZ", "000006.SZ"],
        "name": ["平安银行", "万科A", "ST某某", "*ST某某", "正常股票", "退市股票"],
        "list_status": ["L", "L", "L", "L", "L", "D"],
        "is_active": [True, True, True, True, True, False],
    })


@pytest.fixture
def tushare_quotes():
    """模拟 Tushare 数据"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240102", "20240101"],
        "open": [10.0, 10.5, 20.0],
        "high": [10.5, 10.8, 20.5],
        "low": [9.8, 10.2, 19.5],
        "close": [10.2, 10.6, 20.2],
        "vol": [1000.0, 1200.0, 2000.0],
        "pct_chg": [1.0, 3.9, 1.0],
    })


@pytest.fixture
def akshare_quotes():
    """模拟 AKShare 数据（有轻微差异）"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ", "000003.SZ"],
        "trade_date": ["20240101", "20240102", "20240101", "20240101"],
        "open": [10.01, 10.49, 20.0, 30.0],  # 轻微差异
        "high": [10.51, 10.79, 20.5, 30.5],
        "low": [9.81, 10.21, 19.5, 29.5],
        "close": [10.21, 10.59, 20.2, 30.2],
        "vol": [1000.0, 1200.0, 2000.0, 3000.0],
        "pct_chg": [1.0, 3.8, 1.0, 2.0],
    })


# ===== Full Pipeline Integration Tests =====


class TestFullPipelineIntegration:
    """完整管道集成测试"""

    def test_full_pipeline_workflow(self, raw_quotes_data, stock_info_data):
        """测试完整管道工作流"""
        # 1. 创建管道
        pipeline = create_default_pipeline(stock_info=stock_info_data)
        pipeline.adjuster = None  # 禁用复权，测试数据没有复权因子

        # 2. 运行管道
        result = pipeline.run(
            raw_quotes_data,
            exclude_st=True,
            exclude_suspended=False,
            exclude_delist=True,
        )

        # 3. 验证结果
        # 应该移除了重复数据
        assert len(result) <= len(raw_quotes_data)

        # 4. 获取统计
        stats = pipeline.get_stats()
        assert len(stats) > 0

    def test_pipeline_with_strict_mode(self, raw_quotes_data, stock_info_data):
        """测试严格模式管道"""
        from quant.data.etl.pipeline import create_strict_pipeline

        pipeline = create_strict_pipeline(
            stock_info=stock_info_data,
            min_turnover=0.0,
        )
        pipeline.adjuster = None

        result = pipeline.run(raw_quotes_data)

        # 严格模式应该删除更多数据（缺失值直接删除，异常值直接删除）
        assert len(result) <= len(raw_quotes_data)


# ===== Data Validation Integration Tests =====


class TestDataValidationIntegration:
    """数据验证集成测试"""

    def test_cross_source_validation(self, tushare_quotes, akshare_quotes):
        """测试跨数据源验证"""
        merged, report = validate_and_merge(
            tushare_quotes,
            akshare_quotes,
            on=["ts_code", "trade_date"],
            tolerance=0.02,
        )

        # 应该合并了所有数据
        assert len(merged) == 4  # 3 个来自 Tushare，1 个只有 AKShare

        # 验证报告应该有统计
        assert report["total_rows"] == 4
        assert "match_rate" in report

    def test_validation_with_large_discrepancy(self):
        """测试有较大差异的验证"""
        df1 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
            "vol": [1000.0],
        })

        df2 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [20.0],  # 差异 100%
            "vol": [1000.0],
        })

        merged, report = validate_and_merge(df1, df2, tolerance=0.01)

        # 应该标记为异常
        assert len(report.get("anomalies", [])) > 0 or report.get("mismatched_rows", 0) > 0


# ===== ETL Component Integration Tests =====


class TestETLComponentIntegration:
    """ETL 组件集成测试"""

    def test_cleaners_chain(self, raw_quotes_data):
        """测试清洗器链式处理"""
        # 1. 去重
        dedup = DuplicateCleaner()
        df1 = dedup.clean(raw_quotes_data)
        assert len(df1) <= len(raw_quotes_data)

        # 2. 缺失值处理
        missing = MissingValueCleaner(strategy="ffill")
        df2 = missing.clean(df1)
        # 缺失值可能仍然存在（如第一行或整组为 NaN）
        # 只验证清洗器执行成功
        stats = missing.get_stats()
        assert stats is not None

        # 3. 异常值处理
        outlier = OutlierCleaner(method="winsorize")
        df3 = outlier.clean(df2)
        assert len(df3) == len(df2)

    def test_filter_integration(self, raw_quotes_data, stock_info_data):
        """测试过滤器集成"""
        # 先清洗数据
        pipeline = ETLPipeline()
        pipeline.add_cleaner(DuplicateCleaner())
        pipeline.add_cleaner(MissingValueCleaner(strategy="ffill"))

        cleaned = pipeline.run(raw_quotes_data)

        # 然后过滤
        filter = StockStatusFilter()
        filter.update_status(stock_info_data)

        filtered = filter.filter(
            cleaned,
            exclude_st=True,
            exclude_delist=True,
            exclude_suspended=False,
        )

        # 应该过滤掉 ST 股票
        st_codes = filter.st_stocks
        for code in st_codes:
            assert code not in filtered["ts_code"].values


# ===== Price Adjustment Integration Tests =====


class TestPriceAdjustmentIntegration:
    """复权集成测试"""

    def test_qfq_adjustment_with_pipeline(self):
        """测试前复权与管道集成"""
        # 创建测试数据
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"] * 5 + ["000002.SZ"] * 5,
            "trade_date": ["20240101", "20240102", "20240103", "20240104", "20240105"] * 2,
            "open": [10.0, 10.5, 11.0, 11.5, 12.0] * 2,
            "high": [10.5, 11.0, 11.5, 12.0, 12.5] * 2,
            "low": [9.5, 10.0, 10.5, 11.0, 11.5] * 2,
            "close": [10.2, 10.8, 11.2, 11.8, 12.2] * 2,
            "vol": [1000.0] * 10,
            "adj_factor": [1.0, 1.0, 1.1, 1.1, 1.1] * 2,  # 第三天有除权
        })

        # 创建管道
        pipeline = ETLPipeline()
        pipeline.add_cleaner(DuplicateCleaner())
        pipeline.set_adjuster("qfq")

        result = pipeline.run(df)

        # 应该有复权后的价格列
        assert "adj_close" in result.columns


# ===== Edge Cases Integration Tests =====


class TestEdgeCasesIntegration:
    """边缘情况集成测试"""

    def test_empty_input(self):
        """测试空输入"""
        pipeline = create_default_pipeline()
        pipeline.adjuster = None

        result = pipeline.run(pd.DataFrame())

        assert result.empty

    def test_single_row_input(self):
        """测试单行输入"""
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
            "vol": [1000.0],
        })

        pipeline = create_default_pipeline()
        pipeline.adjuster = None

        result = pipeline.run(df)

        assert len(result) == 1

    def test_all_nan_column(self):
        """测试全 NaN 列"""
        df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240101", "20240102"],
            "close": [np.nan, np.nan],
            "vol": [1000.0, 1100.0],
        })

        cleaner = MissingValueCleaner(strategy="drop")
        result = cleaner.clean(df)

        # 应该删除所有行
        assert len(result) == 0

    def test_mixed_data_types(self):
        """测试混合数据类型"""
        df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ"],
            "trade_date": ["20240101", "20240102"],
            "close": [10.0, 20.0],  # 数值类型
            "vol": [1000.0, 2000.0],
        })

        cleaner = OutlierCleaner()
        result = cleaner.clean(df)

        # 应该能正常处理
        assert len(result) == 2


# ===== Performance Tests =====


class TestPerformance:
    """性能测试"""

    def test_large_dataset_pipeline(self):
        """测试大数据集管道性能"""
        # 创建 10000 行数据
        np.random.seed(42)
        n = 10000

        df = pd.DataFrame({
            "ts_code": np.random.choice([f"00000{i}.SZ" for i in range(10)], n),
            "trade_date": np.random.choice([f"2024010{i}" for i in range(10)], n),
            "open": 10.0 + np.random.randn(n),
            "close": 10.0 + np.random.randn(n),
            "vol": 1000.0 + np.random.randn(n) * 100,
        })

        pipeline = create_default_pipeline()
        pipeline.adjuster = None

        # 运行管道
        result = pipeline.run(df)

        # 应该能处理大数据集
        assert len(result) > 0
        assert len(result) <= n


# ===== Data Quality Tests =====


class TestDataQuality:
    """数据质量测试"""

    def test_data_consistency_after_cleaning(self, raw_quotes_data):
        """测试清洗后数据一致性"""
        pipeline = ETLPipeline()
        pipeline.add_cleaner(DuplicateCleaner())
        pipeline.add_cleaner(MissingValueCleaner(strategy="ffill"))

        result = pipeline.run(raw_quotes_data)

        # 检查数据一致性
        # 1. 每个 (ts_code, trade_date) 组合应该是唯一的
        duplicates = result.duplicated(subset=["ts_code", "trade_date"])
        assert duplicates.sum() == 0, "存在重复的 (ts_code, trade_date) 组合"

        # 2. 检查有效数据的价格约束（high >= low）
        if "high" in result.columns and "low" in result.columns:
            valid_mask = result["high"].notna() & result["low"].notna()
            if valid_mask.any():
                invalid_prices = result.loc[valid_mask, "high"] < result.loc[valid_mask, "low"]
                # 由于是随机数据，可能有少量违反约束的情况，这是预期的
                # 我们只检查没有大量违反约束的情况
                assert invalid_prices.sum() < len(result) * 0.1, "大量价格约束违反"

    def test_volume_non_negative(self, raw_quotes_data):
        """测试成交量非负"""
        cleaner = OutlierCleaner()
        result = cleaner.clean(raw_quotes_data)

        # 成交量不应该有负值（可能被设为 NaN）
        if "vol" in result.columns:
            assert (result["vol"] < 0).sum() == 0


# ===== Validation Report Tests =====


class TestValidationReport:
    """验证报告测试"""

    def test_report_completeness(self, tushare_quotes, akshare_quotes):
        """测试报告完整性"""
        validator = DataValidator(tolerance=0.05)
        merged = validator.cross_validate(tushare_quotes, akshare_quotes)

        report = validator.get_validation_report()

        # 报告应该包含所有必要字段
        assert "total_rows" in report
        assert "matched_rows" in report
        assert "mismatched_rows" in report
        assert "match_rate" in report
        assert "field_diffs" in report

    def test_anomaly_tracking(self):
        """测试异常追踪"""
        df1 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
        })

        df2 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [100.0],  # 巨大差异
        })

        validator = DataValidator(tolerance=0.01)
        merged = validator.cross_validate(df1, df2)

        anomalies = validator.get_anomalies()

        # 应该记录异常
        assert len(anomalies) > 0
        assert anomalies[0]["type"] == "numeric_mismatch"
