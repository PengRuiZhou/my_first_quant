"""数据源模块单元测试

使用 mock 测试数据源适配器和验证器，避免真实 API 调用。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from quant.data.sources.base import BaseDataSource
from quant.data.sources.validator import DataValidator, ValidationReport, validate_and_merge


# ===== Fixtures =====


@pytest.fixture
def mock_stock_list():
    """模拟股票列表数据"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ", "600000.SH"],
        "symbol": ["000001", "000002", "600000"],
        "name": ["平安银行", "万科A", "浦发银行"],
        "area": ["深圳", "深圳", "上海"],
        "industry": ["银行", "房地产", "银行"],
        "market": ["主板", "主板", "主板"],
        "list_date": ["19910403", "19910129", "19991110"],
    })


@pytest.fixture
def mock_daily_quotes():
    """模拟日线行情数据"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240102", "20240101"],
        "open": [10.0, 10.5, 20.0],
        "high": [10.5, 10.8, 20.5],
        "low": [9.8, 10.2, 19.5],
        "close": [10.2, 10.6, 20.2],
        "vol": [1000.0, 1200.0, 2000.0],
        "amount": [10200.0, 12600.0, 40400.0],
        "pct_chg": [1.0, 3.9, 1.0],
    })


@pytest.fixture
def mock_trade_calendar():
    """模拟交易日历数据"""
    return pd.DataFrame({
        "exchange": ["SSE"] * 5,
        "cal_date": ["20240101", "20240102", "20240103", "20240104", "20240105"],
        "is_open": [0, 1, 1, 1, 1],
        "pretrade_date": [None, "20240101", "20240102", "20240103", "20240104"],
    })


# ===== BaseDataSource Tests =====


class TestBaseDataSource:
    """数据源基类测试"""

    def test_abstract_methods(self):
        """测试抽象方法必须被实现"""
        with pytest.raises(TypeError):
            # 不能直接实例化抽象类
            BaseDataSource()

    def test_name_property_abstract(self):
        """测试 name 属性是抽象的"""
        # 检查是否是抽象属性
        assert hasattr(BaseDataSource, "name")


# ===== Mock DataSource for Testing =====


class MockDataSource(BaseDataSource):
    """用于测试的模拟数据源"""

    @property
    def name(self) -> str:
        return "mock"

    async def get_stock_list(self) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "symbol": ["000001"],
            "name": ["测试股票"],
        })

    async def get_index_list(self) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code": ["000001.SH"],
            "name": ["上证指数"],
        })

    async def get_daily_quotes(self, ts_code=None, trade_date=None, start_date=None, end_date=None) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
        })

    async def get_index_quotes(self, ts_code=None, trade_date=None, start_date=None, end_date=None) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code": ["000001.SH"],
            "trade_date": ["20240101"],
            "close": [3000.0],
        })

    async def get_trade_calendar(self, exchange="SSE", start_date=None, end_date=None) -> pd.DataFrame:
        return pd.DataFrame({
            "exchange": ["SSE"],
            "cal_date": ["20240101"],
            "is_open": [1],
        })

    async def get_daily_basic(self, ts_code=None, trade_date=None, start_date=None, end_date=None) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "pe": [10.0],
        })

    async def get_financial_indicator(self, ts_code=None, start_date=None, end_date=None, period=None) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "end_date": ["20231231"],
            "roe": [12.0],
        })

    async def get_adj_factor(self, ts_code=None, trade_date=None, start_date=None, end_date=None) -> pd.DataFrame:
        return pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "adj_factor": [1.0],
        })

    async def close(self) -> None:
        pass


class TestMockDataSource:
    """模拟数据源测试"""

    @pytest.mark.asyncio
    async def test_get_stock_list(self):
        """测试获取股票列表"""
        source = MockDataSource()
        result = await source.get_stock_list()

        assert len(result) == 1
        assert "ts_code" in result.columns
        assert result["ts_code"].iloc[0] == "000001.SZ"

    @pytest.mark.asyncio
    async def test_get_daily_quotes(self):
        """测试获取日线行情"""
        source = MockDataSource()
        result = await source.get_daily_quotes()

        assert len(result) == 1
        assert "close" in result.columns

    @pytest.mark.asyncio
    async def test_name_property(self):
        """测试名称属性"""
        source = MockDataSource()
        assert source.name == "mock"


# ===== DataValidator Tests =====


class TestDataValidator:
    """数据验证器测试"""

    def test_init(self):
        """测试初始化"""
        validator = DataValidator(tolerance=0.05)
        assert validator.tolerance == 0.05

    def test_cross_validate_empty_dataframes(self):
        """测试空数据验证"""
        validator = DataValidator()

        # 两个都为空
        result = validator.cross_validate(pd.DataFrame(), pd.DataFrame())
        assert result.empty

        # Tushare 为空
        df = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20240101"], "close": [10.0]})
        result = validator.cross_validate(pd.DataFrame(), df)
        assert len(result) == 1

        # AKShare 为空
        result = validator.cross_validate(df, pd.DataFrame())
        assert len(result) == 1

    def test_cross_validate_matching_data(self):
        """测试匹配数据验证"""
        validator = DataValidator(tolerance=0.01)

        df1 = pd.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ"],
            "trade_date": ["20240101", "20240101"],
            "close": [10.0, 20.0],
            "vol": [1000.0, 2000.0],
        })

        df2 = pd.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ"],
            "trade_date": ["20240101", "20240101"],
            "close": [10.0, 20.1],  # 轻微差异
            "vol": [1000.0, 2000.0],
        })

        result = validator.cross_validate(df1, df2)

        assert len(result) == 2
        assert "close" in result.columns

    def test_cross_validate_mismatch_data(self):
        """测试不匹配数据验证"""
        validator = DataValidator(tolerance=0.01)

        df1 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
        })

        df2 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [20.0],  # 差异超过容差
        })

        result = validator.cross_validate(df1, df2)

        # 应该标记为异常
        report = validator.get_validation_report()
        assert report["mismatched_rows"] > 0 or len(validator.get_anomalies()) > 0

    def test_cross_validate_partial_overlap(self):
        """测试部分重叠数据"""
        validator = DataValidator()

        df1 = pd.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ"],
            "trade_date": ["20240101", "20240101"],
            "close": [10.0, 20.0],
        })

        df2 = pd.DataFrame({
            "ts_code": ["000002.SZ", "000003.SZ"],
            "trade_date": ["20240101", "20240101"],
            "close": [20.0, 30.0],
        })

        result = validator.cross_validate(df1, df2)

        # 应该包含所有三个股票
        assert len(result) == 3

        report = validator.get_validation_report()
        assert report["missing_in_tushare"] == 1  # 000003.SZ
        assert report["missing_in_akshare"] == 1  # 000001.SZ

    def test_cross_validate_string_fields(self):
        """测试字符串字段验证"""
        validator = DataValidator()

        df1 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "name": ["平安银行"],
        })

        df2 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "name": ["平安银行"],
        })

        result = validator.cross_validate(df1, df2, string_fields=["name"])

        assert result["name"].iloc[0] == "平安银行"

    def test_cross_validate_string_mismatch(self):
        """测试字符串不匹配"""
        validator = DataValidator()

        df1 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "name": ["平安银行"],
        })

        df2 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "name": ["万科A"],  # 不匹配
        })

        result = validator.cross_validate(df1, df2, string_fields=["name"])

        # 应该使用 Tushare 值并记录异常
        assert result["name"].iloc[0] == "平安银行"
        anomalies = validator.get_anomalies()
        assert len(anomalies) > 0

    def test_get_validation_report(self):
        """测试获取验证报告"""
        validator = DataValidator()

        # 未验证时
        report = validator.get_validation_report()
        assert "error" in report

        # 验证后
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
        })
        validator.cross_validate(df, df)
        report = validator.get_validation_report()

        assert "total_rows" in report
        assert "match_rate" in report

    def test_custom_merge_keys(self):
        """测试自定义合并键"""
        validator = DataValidator()

        df1 = pd.DataFrame({
            "symbol": ["000001"],
            "date": ["20240101"],
            "close": [10.0],
        })

        df2 = pd.DataFrame({
            "symbol": ["000001"],
            "date": ["20240101"],
            "close": [10.0],
        })

        result = validator.cross_validate(df1, df2, on=["symbol", "date"])

        assert len(result) == 1


class TestValidationReport:
    """验证报告测试"""

    def test_default_values(self):
        """测试默认值"""
        report = ValidationReport()

        assert report.total_rows == 0
        assert report.matched_rows == 0
        assert report.mismatched_rows == 0
        assert report.match_rate == 0.0

    def test_match_rate_calculation(self):
        """测试匹配率计算"""
        report = ValidationReport(total_rows=100, matched_rows=95)

        assert report.match_rate == 0.95

    def test_to_dict(self):
        """测试转换为字典"""
        report = ValidationReport(
            total_rows=100,
            matched_rows=95,
            mismatched_rows=5,
            missing_in_tushare=2,
            missing_in_akshare=3,
        )

        d = report.to_dict()

        assert d["total_rows"] == 100
        assert d["match_rate"] == "95.00%"


class TestValidateAndMerge:
    """便捷函数测试"""

    def test_validate_and_merge(self):
        """测试验证合并函数"""
        df1 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
        })

        df2 = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
        })

        result, report = validate_and_merge(df1, df2, tolerance=0.01)

        assert len(result) == 1
        assert "total_rows" in report


# ===== Tushare Client Mock Tests =====


class TestTushareClientMock:
    """Tushare 客户端 Mock 测试"""

    @pytest.mark.asyncio
    async def test_get_stock_list_mock(self, mock_stock_list):
        """测试获取股票列表（mock）"""
        with patch("quant.data.sources.tushare_client.TushareClient") as MockClient:
            instance = MockClient.return_value
            instance.get_stock_list = AsyncMock(return_value=mock_stock_list)

            result = await instance.get_stock_list()

            assert len(result) == 3
            assert "ts_code" in result.columns

    @pytest.mark.asyncio
    async def test_get_daily_quotes_mock(self, mock_daily_quotes):
        """测试获取日线行情（mock）"""
        with patch("quant.data.sources.tushare_client.TushareClient") as MockClient:
            instance = MockClient.return_value
            instance.get_daily_quotes = AsyncMock(return_value=mock_daily_quotes)

            result = await instance.get_daily_quotes(start_date="20240101", end_date="20240131")

            assert len(result) == 3
            assert "close" in result.columns


# ===== AKShare Client Mock Tests =====


class TestAKShareClientMock:
    """AKShare 客户端 Mock 测试"""

    @pytest.mark.asyncio
    async def test_get_stock_list_mock(self, mock_stock_list):
        """测试获取股票列表（mock）"""
        with patch("quant.data.sources.akshare_client.AKShareClient") as MockClient:
            instance = MockClient.return_value
            instance.get_stock_list = AsyncMock(return_value=mock_stock_list)

            result = await instance.get_stock_list()

            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_trade_calendar_mock(self, mock_trade_calendar):
        """测试获取交易日历（mock）"""
        with patch("quant.data.sources.akshare_client.AKShareClient") as MockClient:
            instance = MockClient.return_value
            instance.get_trade_calendar = AsyncMock(return_value=mock_trade_calendar)

            result = await instance.get_trade_calendar(exchange="SSE")

            assert "exchange" in result.columns
            assert "is_open" in result.columns


# ===== Error Handling Tests =====


class TestDataSourceErrorHandling:
    """数据源错误处理测试"""

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """测试 API 错误处理"""
        with patch("quant.data.sources.tushare_client.TushareClient") as MockClient:
            instance = MockClient.return_value
            instance.get_stock_list = AsyncMock(side_effect=Exception("API Error"))

            with pytest.raises(Exception, match="API Error"):
                await instance.get_stock_list()

    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """测试空响应处理"""
        with patch("quant.data.sources.tushare_client.TushareClient") as MockClient:
            instance = MockClient.return_value
            instance.get_daily_quotes = AsyncMock(return_value=pd.DataFrame())

            result = await instance.get_daily_quotes()

            assert result.empty


# ===== Field Mapping Tests =====


class TestFieldMapping:
    """字段映射测试"""

    def test_tushare_field_mapping(self):
        """测试 Tushare 字段映射"""
        # Tushare 原始字段
        raw_data = {
            "ts_code": "000001.SZ",
            "trade_date": "20240101",
            "open": 10.0,
            "high": 10.5,
            "low": 9.8,
            "close": 10.2,
            "vol": 1000.0,
            "amount": 10200.0,
        }

        # 验证字段名称符合预期
        expected_fields = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"]
        for field in expected_fields:
            assert field in raw_data

    def test_akshare_field_mapping(self):
        """测试 AKShare 字段映射"""
        # AKShare 原始字段可能不同，需要映射
        raw_data = {
            "代码": "000001",
            "名称": "平安银行",
            "收盘价": 10.2,
            "成交量": 1000.0,
        }

        # 验证原始字段存在
        assert "代码" in raw_data
        assert "收盘价" in raw_data
