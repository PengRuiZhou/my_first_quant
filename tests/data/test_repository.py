"""数据仓库层单元测试

使用 mock 测试数据仓库操作，避免真实数据库连接。
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from quant.data.storage.repository import DataRepository


# ===== Fixtures =====


@pytest.fixture
def mock_session_factory():
    """创建模拟会话工厂"""
    factory = MagicMock(spec=async_sessionmaker)
    return factory


@pytest.fixture
def mock_session():
    """创建模拟会话"""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def sample_stock_df():
    """示例股票数据"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ", "600000.SH"],
        "symbol": ["000001", "000002", "600000"],
        "name": ["平安银行", "万科A", "浦发银行"],
        "area": ["深圳", "深圳", "上海"],
        "industry": ["银行", "房地产", "银行"],
        "market": ["主板", "主板", "主板"],
        "list_date": [date(1991, 4, 3), date(1991, 1, 29), date(1999, 11, 10)],
        "is_active": [True, True, True],
    })


@pytest.fixture
def sample_quotes_df():
    """示例行情数据"""
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ"],
        "trade_date": [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 1)],
        "open": [10.0, 10.5, 20.0],
        "high": [10.5, 10.8, 20.5],
        "low": [9.8, 10.2, 19.5],
        "close": [10.2, 10.6, 20.2],
        "vol": [1000.0, 1200.0, 2000.0],
        "amount": [10200.0, 12600.0, 40400.0],
        "pct_chg": [1.0, 3.9, 1.0],
    })


@pytest.fixture
def sample_trade_calendar_df():
    """示例交易日历数据"""
    return pd.DataFrame({
        "exchange": ["SSE", "SSE", "SSE"],
        "cal_date": [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)],
        "is_open": [False, True, True],
        "pretrade_date": [None, date(2024, 1, 1), date(2024, 1, 2)],
    })


# ===== Repository Initialization Tests =====


class TestDataRepositoryInit:
    """数据仓库初始化测试"""

    @pytest.mark.skipif(
        True,  # 跳过需要 asyncpg 的测试
        reason="需要 asyncpg 模块，在 CI 环境中测试"
    )
    def test_init_with_db_url(self):
        """测试使用数据库 URL 初始化"""
        repo = DataRepository(db_url="postgresql+asyncpg://user:pass@localhost/test")
        assert repo.db_url == "postgresql+asyncpg://user:pass@localhost/test"

    def test_init_with_session_factory(self, mock_session_factory):
        """测试使用会话工厂初始化"""
        repo = DataRepository(session_factory=mock_session_factory)
        assert repo._session_factory == mock_session_factory


# ===== Stock Info Tests =====


class TestStockInfo:
    """股票信息操作测试"""

    @pytest.mark.asyncio
    async def test_get_stock_list_empty(self, mock_session_factory, mock_session):
        """测试获取空股票列表"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        result = await repo.get_stock_list()

        assert result.empty

    @pytest.mark.asyncio
    async def test_upsert_stock_info(self, mock_session_factory, mock_session, sample_stock_df):
        """测试更新/插入股票信息"""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.upsert_stock_info(sample_stock_df)

        assert count == 3
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_empty_dataframe(self, mock_session_factory, mock_session):
        """测试插入空数据框"""
        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.upsert_stock_info(pd.DataFrame())

        assert count == 0
        mock_session.execute.assert_not_called()


# ===== Daily Quotes Tests =====


class TestDailyQuotes:
    """日线行情操作测试"""

    @pytest.mark.asyncio
    async def test_get_daily_quotes_with_filter(self, mock_session_factory, mock_session):
        """测试带过滤条件获取日线行情"""
        mock_stock = MagicMock()
        mock_stock.ts_code = "000001.SZ"
        mock_stock.trade_date = date(2024, 1, 1)
        mock_stock.open = 10.0
        mock_stock.high = 10.5
        mock_stock.low = 9.8
        mock_stock.close = 10.2
        mock_stock.vol = 1000.0
        mock_stock.amount = 10200.0
        mock_stock.pct_chg = 1.0
        mock_stock.pre_close = 10.1
        mock_stock.change = 0.1
        mock_stock.turnover_rate = 0.5

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_stock]
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        result = await repo.get_daily_quotes(ts_code="000001.SZ", start_date=date(2024, 1, 1))

        assert len(result) == 1
        assert result["ts_code"].iloc[0] == "000001.SZ"

    @pytest.mark.asyncio
    async def test_upsert_daily_quotes(self, mock_session_factory, mock_session, sample_quotes_df):
        """测试更新/插入日线行情"""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.upsert_daily_quotes(sample_quotes_df)

        assert count == 3

    @pytest.mark.asyncio
    async def test_delete_daily_quotes(self, mock_session_factory, mock_session):
        """测试删除日线行情"""
        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.delete_daily_quotes(ts_code="000001.SZ", before_date=date(2023, 1, 1))

        assert count == 10


# ===== Trade Calendar Tests =====


class TestTradeCalendar:
    """交易日历操作测试"""

    @pytest.mark.asyncio
    async def test_get_trade_dates(self, mock_session_factory, mock_session):
        """测试获取交易日列表"""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (date(2024, 1, 2),),
            (date(2024, 1, 3),),
            (date(2024, 1, 4),),
        ]
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        dates = await repo.get_trade_dates(exchange="SSE", is_open=True)

        assert len(dates) == 3
        assert all(isinstance(d, date) for d in dates)

    @pytest.mark.asyncio
    async def test_get_latest_trade_date(self, mock_session_factory, mock_session):
        """测试获取最新交易日"""
        mock_result = MagicMock()
        mock_result.first.return_value = (date(2024, 1, 5),)
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        latest = await repo.get_latest_trade_date(exchange="SSE")

        assert latest == date(2024, 1, 5)

    @pytest.mark.asyncio
    async def test_get_latest_trade_date_empty(self, mock_session_factory, mock_session):
        """测试空数据库获取最新交易日"""
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        latest = await repo.get_latest_trade_date(exchange="SSE")

        assert latest is None

    @pytest.mark.asyncio
    async def test_upsert_trade_calendar(
        self, mock_session_factory, mock_session, sample_trade_calendar_df
    ):
        """测试更新/插入交易日历"""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.upsert_trade_calendar(sample_trade_calendar_df)

        assert count == 3


# ===== Index Quotes Tests =====


class TestIndexQuotes:
    """指数行情操作测试"""

    @pytest.mark.asyncio
    async def test_get_index_quotes(self, mock_session_factory, mock_session):
        """测试获取指数行情"""
        mock_index = MagicMock()
        mock_index.ts_code = "000001.SH"
        mock_index.trade_date = date(2024, 1, 1)
        mock_index.open = 3000.0
        mock_index.high = 3050.0
        mock_index.low = 2980.0
        mock_index.close = 3020.0
        mock_index.vol = 1000000.0
        mock_index.amount = 100000000.0
        mock_index.pct_chg = 0.5
        mock_index.pre_close = 3005.0
        mock_index.change = 15.0

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_index]
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        result = await repo.get_index_quotes(ts_code="000001.SH")

        assert len(result) == 1
        assert result["ts_code"].iloc[0] == "000001.SH"


# ===== Daily Basic Tests =====


class TestDailyBasic:
    """每日指标操作测试"""

    @pytest.mark.asyncio
    async def test_get_daily_basic(self, mock_session_factory, mock_session):
        """测试获取每日指标"""
        mock_basic = MagicMock()
        mock_basic.ts_code = "000001.SZ"
        mock_basic.trade_date = date(2024, 1, 1)
        mock_basic.close = 10.0
        mock_basic.turnover_rate = 0.5
        mock_basic.pe = 10.0
        mock_basic.pb = 1.0
        mock_basic.total_mv = 1000000.0
        mock_basic.circ_mv = 500000.0
        mock_basic.turnover_rate_f = 0.6
        mock_basic.volume_ratio = 1.0
        mock_basic.pe_ttm = 11.0
        mock_basic.ps = 2.0

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_basic]
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        result = await repo.get_daily_basic(ts_code="000001.SZ")

        assert len(result) == 1
        assert "pe" in result.columns


# ===== Financial Indicator Tests =====


class TestFinancialIndicator:
    """财务指标操作测试"""

    @pytest.mark.asyncio
    async def test_get_financial_indicator(self, mock_session_factory, mock_session):
        """测试获取财务指标"""
        mock_fi = MagicMock()
        mock_fi.ts_code = "000001.SZ"
        mock_fi.ann_date = date(2024, 1, 1)
        mock_fi.end_date = date(2023, 12, 31)
        mock_fi.roe = 12.0
        mock_fi.roe_dt = 11.5
        mock_fi.roa = 1.5
        mock_fi.netprofit_margin = 25.0
        mock_fi.grossprofit_margin = 50.0
        mock_fi.debt_to_assets = 60.0
        mock_fi.current_ratio = 1.5
        mock_fi.quick_ratio = 1.2
        mock_fi.eps = 1.5
        mock_fi.bvps = 15.0
        mock_fi.pe = 10.0
        mock_fi.pe_ttm = 11.0
        mock_fi.pb = 1.0

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_fi]
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        result = await repo.get_financial_indicator(ts_code="000001.SZ")

        assert len(result) == 1
        assert "roe" in result.columns


# ===== Count Tests =====


class TestCountMethods:
    """计数方法测试"""

    @pytest.mark.asyncio
    async def test_get_daily_quote_count(self, mock_session_factory, mock_session):
        """测试获取日线行情数量"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1000
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.get_daily_quote_count()

        assert count == 1000

    @pytest.mark.asyncio
    async def test_get_stock_count(self, mock_session_factory, mock_session):
        """测试获取股票数量"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5000
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.get_stock_count(active_only=True)

        assert count == 5000


# ===== NaN Handling Tests =====


class TestNaNHandling:
    """NaN 值处理测试"""

    @pytest.mark.asyncio
    async def test_upsert_with_nan_values(self, mock_session_factory, mock_session):
        """测试包含 NaN 值的插入"""
        df_with_nan = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "symbol": ["000001"],
            "name": ["平安银行"],
            "area": [None],  # NaN 值
            "industry": ["银行"],
            "market": ["主板"],
            "list_date": [date(1991, 4, 3)],
            "is_active": [True],
        })

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = DataRepository(session_factory=mock_session_factory)
        count = await repo.upsert_stock_info(df_with_nan)

        # 应该成功插入，NaN 被转换为 None
        assert count == 1


# ===== Table Creation Tests =====


class TestTableCreation:
    """表创建测试"""

    @pytest.mark.asyncio
    async def test_create_tables(self, mock_session_factory):
        """测试创建表"""
        mock_conn = AsyncMock()

        with patch("quant.data.storage.repository.create_async_engine") as mock_engine:
            engine_instance = MagicMock()
            engine_instance.begin = MagicMock(return_value=AsyncMock())
            engine_instance.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            engine_instance.begin.return_value.__aexit__ = AsyncMock(return_value=None)
            engine_instance.dispose = AsyncMock()
            mock_engine.return_value = engine_instance

            repo = DataRepository(session_factory=mock_session_factory)
            await repo.create_tables()

            # 验证调用了 run_sync
            mock_conn.run_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_drop_tables(self, mock_session_factory):
        """测试删除表"""
        mock_conn = AsyncMock()

        with patch("quant.data.storage.repository.create_async_engine") as mock_engine:
            engine_instance = MagicMock()
            engine_instance.begin = MagicMock(return_value=AsyncMock())
            engine_instance.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            engine_instance.begin.return_value.__aexit__ = AsyncMock(return_value=None)
            engine_instance.dispose = AsyncMock()
            mock_engine.return_value = engine_instance

            repo = DataRepository(session_factory=mock_session_factory)
            await repo.drop_tables()

            mock_conn.run_sync.assert_called_once()
