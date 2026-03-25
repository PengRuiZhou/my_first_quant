"""数据调度器单元测试

使用 mock 测试调度器功能，避免真实任务执行。
"""

from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from quant.data.storage.scheduler import DataScheduler, create_minimal_pipeline

# ===== Fixtures =====


@pytest.fixture
def mock_repository():
    """创建模拟数据仓库"""
    repo = MagicMock()
    repo.get_latest_trade_date = AsyncMock(return_value=None)
    repo.upsert_daily_quotes = AsyncMock(return_value=100)
    repo.upsert_daily_basic = AsyncMock(return_value=100)
    repo.upsert_stock_info = AsyncMock(return_value=50)
    repo.upsert_trade_calendar = AsyncMock(return_value=365)
    repo.upsert_index_quotes = AsyncMock(return_value=100)
    return repo


@pytest.fixture
def mock_data_source():
    """创建模拟数据源"""
    source = MagicMock()
    source.get_stock_list = AsyncMock(
        return_value=pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "symbol": ["000001", "000002"],
                "name": ["平安银行", "万科A"],
            }
        )
    )
    source.get_daily_quotes = AsyncMock(
        return_value=pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "trade_date": ["20240101", "20240101"],
                "open": [10.0, 20.0],
                "close": [10.5, 20.5],
                "vol": [1000.0, 2000.0],
            }
        )
    )
    source.get_daily_basic = AsyncMock(
        return_value=pd.DataFrame(
            {
                "ts_code": ["000001.SZ"],
                "trade_date": ["20240101"],
                "pe": [10.0],
            }
        )
    )
    source.get_trade_calendar = AsyncMock(
        return_value=pd.DataFrame(
            {
                "exchange": ["SSE"],
                "cal_date": ["20240101"],
                "is_open": [1],
            }
        )
    )
    source.get_index_quotes = AsyncMock(
        return_value=pd.DataFrame(
            {
                "ts_code": ["000001.SH"],
                "trade_date": ["20240101"],
                "close": [3000.0],
            }
        )
    )
    source.close = AsyncMock()
    return source


@pytest.fixture
def scheduler(mock_repository, mock_data_source):
    """创建调度器实例"""
    return DataScheduler(
        repository=mock_repository,
        data_source=mock_data_source,
    )


# ===== Scheduler Initialization Tests =====


class TestDataSchedulerInit:
    """调度器初始化测试"""

    def test_init_with_dependencies(self, mock_repository, mock_data_source):
        """测试使用依赖注入初始化"""
        sched = DataScheduler(
            repository=mock_repository,
            data_source=mock_data_source,
        )
        assert sched.repository == mock_repository
        assert sched.data_source == mock_data_source
        assert sched._is_running is False


# ===== Scheduler Control Tests =====


class TestSchedulerControl:
    """调度器控制测试"""

    @pytest.mark.skip(reason="需要运行中的事件循环，在集成测试中验证")
    def test_start_scheduler(self, scheduler):
        """测试启动调度器"""
        scheduler.start()

        assert scheduler._is_running is True

    @pytest.mark.skip(reason="需要运行中的事件循环，在集成测试中验证")
    def test_start_already_running(self, scheduler):
        """测试重复启动调度器"""
        scheduler.start()
        # 应该不会报错
        scheduler.start()

        assert scheduler._is_running is True

    @pytest.mark.skip(reason="需要运行中的事件循环，在集成测试中验证")
    def test_stop_scheduler(self, scheduler):
        """测试停止调度器"""
        scheduler.start()
        scheduler.stop()

        assert scheduler._is_running is False

    def test_stop_not_running(self, scheduler):
        """测试停止未运行的调度器"""
        # 应该不会报错
        scheduler.stop()

        assert scheduler._is_running is False

    @pytest.mark.skip(reason="需要运行中的事件循环，在集成测试中验证")
    def test_is_running_property(self, scheduler):
        """测试 is_running 属性"""
        assert scheduler.is_running is False

        scheduler.start()
        assert scheduler.is_running is True

        scheduler.stop()
        assert scheduler.is_running is False


# ===== Job Management Tests =====


class TestJobManagement:
    """任务管理测试"""

    async def dummy_task():
        """用于测试的异步任务"""
        pass

    def test_add_cron_job(self, scheduler):
        """测试添加 Cron 任务"""
        job = scheduler.add_job(
            job_id="test_job",
            func=self.dummy_task,
            cron="0 18 * * *",
            name="测试任务",
        )

        assert job.id == "test_job"
        assert job in scheduler._scheduler.get_jobs()

    def test_add_interval_job(self, scheduler):
        """测试添加间隔任务"""
        job = scheduler.add_job(
            job_id="interval_job",
            func=self.dummy_task,
            interval_seconds=60,
            name="间隔任务",
        )

        assert job.id == "interval_job"

    def test_add_job_without_trigger(self, scheduler):
        """测试添加没有触发器的任务"""
        with pytest.raises(ValueError, match="必须提供 cron 或 interval_seconds"):
            scheduler.add_job(
                job_id="invalid_job",
                func=self.dummy_task,
            )

    def test_remove_job(self, scheduler):
        """测试移除任务"""
        scheduler.add_job(
            job_id="to_remove",
            func=self.dummy_task,
            cron="0 18 * * *",
        )

        result = scheduler.remove_job("to_remove")

        assert result is True
        assert scheduler.get_job("to_remove") is None

    def test_remove_nonexistent_job(self, scheduler):
        """测试移除不存在的任务"""
        result = scheduler.remove_job("nonexistent")
        assert result is False

    def test_pause_job(self, scheduler):
        """测试暂停任务"""
        scheduler.add_job(
            job_id="to_pause",
            func=self.dummy_task,
            cron="0 18 * * *",
        )

        result = scheduler.pause_job("to_pause")
        assert result is True

    def test_resume_job(self, scheduler):
        """测试恢复任务"""
        scheduler.add_job(
            job_id="to_resume",
            func=self.dummy_task,
            cron="0 18 * * *",
        )
        scheduler.pause_job("to_resume")

        result = scheduler.resume_job("to_resume")
        assert result is True

    def test_get_jobs(self, scheduler):
        """测试获取所有任务"""

        async def dummy_task():
            pass

        scheduler.add_job(
            job_id="job1",
            func=dummy_task,
            cron="0 18 * * *",
        )
        scheduler.add_job(
            job_id="job2",
            func=dummy_task,
            cron="30 18 * * *",
        )

        jobs = scheduler._scheduler.get_jobs()

        assert len(jobs) == 2
        job_ids = [j.id for j in jobs]
        assert "job1" in job_ids
        assert "job2" in job_ids

    def test_get_job(self, scheduler):
        """测试获取单个任务"""
        scheduler.add_job(
            job_id="specific_job",
            func=self.dummy_task,
            cron="0 18 * * *",
        )

        job = scheduler.get_job("specific_job")

        assert job is not None
        assert job.id == "specific_job"


# ===== Default Jobs Tests =====


class TestDefaultJobs:
    """默认任务测试"""

    def test_setup_default_jobs(self, scheduler):
        """测试设置默认任务"""
        scheduler.setup_default_jobs()

        jobs = scheduler._scheduler.get_jobs()
        job_ids = [j.id for j in jobs]

        assert "update_daily_quotes" in job_ids
        assert "update_daily_basic" in job_ids
        assert "update_stock_list" in job_ids
        assert "update_trade_calendar" in job_ids

    def test_default_jobs_trigger_times(self, scheduler):
        """测试默认任务触发时间"""
        scheduler.setup_default_jobs()

        jobs = {j.id: j for j in scheduler._scheduler.get_jobs()}

        # 检查每日行情更新任务存在
        daily_quotes = jobs.get("update_daily_quotes")
        assert daily_quotes is not None
        # 验证有触发器配置
        assert daily_quotes.trigger is not None


# ===== Task Implementation Tests =====


class TestTaskImplementation:
    """任务实现测试"""

    @pytest.mark.asyncio
    async def test_update_daily_quotes(self, scheduler, mock_data_source, mock_repository):
        """测试更新日线行情任务"""
        mock_repository.get_latest_trade_date = AsyncMock(return_value=None)

        await scheduler._update_daily_quotes()

        mock_data_source.get_daily_quotes.assert_called_once()
        mock_repository.upsert_daily_quotes.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_daily_quotes_empty_data(
        self, scheduler, mock_data_source, mock_repository
    ):
        """测试更新日线行情（空数据）"""
        mock_data_source.get_daily_quotes = AsyncMock(return_value=pd.DataFrame())

        await scheduler._update_daily_quotes()

        # 不应该调用 upsert
        mock_repository.upsert_daily_quotes.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_daily_basic(self, scheduler, mock_data_source, mock_repository):
        """测试更新每日指标任务"""
        await scheduler._update_daily_basic()

        mock_data_source.get_daily_basic.assert_called_once()
        mock_repository.upsert_daily_basic.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stock_list(self, scheduler, mock_data_source, mock_repository):
        """测试更新股票列表任务"""
        await scheduler._update_stock_list()

        mock_data_source.get_stock_list.assert_called_once()
        mock_repository.upsert_stock_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_trade_calendar(self, scheduler, mock_data_source, mock_repository):
        """测试更新交易日历任务"""
        await scheduler._update_trade_calendar()

        mock_data_source.get_trade_calendar.assert_called_once()
        mock_repository.upsert_trade_calendar.assert_called_once()


# ===== Manual Job Execution Tests =====


class TestManualJobExecution:
    """手动执行任务测试"""

    @pytest.mark.asyncio
    async def test_run_job_daily_quotes(self, scheduler, mock_data_source):
        """测试手动运行行情更新"""
        result = await scheduler.run_job("update_daily_quotes")

        assert result is True
        mock_data_source.get_daily_quotes.assert_called()

    @pytest.mark.asyncio
    async def test_run_job_unknown(self, scheduler):
        """测试运行未知任务"""
        result = await scheduler.run_job("unknown_job")

        assert result is False


# ===== Historical Data Initialization Tests =====


class TestHistoricalDataInit:
    """历史数据初始化测试"""

    @pytest.mark.asyncio
    async def test_init_historical_data(self, scheduler, mock_data_source, mock_repository):
        """测试初始化历史数据"""
        stats = await scheduler.init_historical_data(years=1)

        assert "stock_list" in stats
        assert "trade_calendar" in stats
        assert "daily_quotes" in stats
        assert "daily_basic" in stats
        assert "index_quotes" in stats

        mock_data_source.get_stock_list.assert_called_once()
        mock_data_source.get_trade_calendar.assert_called_once()
        mock_data_source.get_daily_quotes.assert_called_once()
        mock_data_source.get_daily_basic.assert_called_once()
        mock_data_source.get_index_quotes.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_historical_data_with_error(self, scheduler, mock_data_source):
        """测试初始化历史数据时的错误处理"""
        mock_data_source.get_stock_list = AsyncMock(side_effect=Exception("API Error"))

        with pytest.raises(Exception, match="API Error"):
            await scheduler.init_historical_data(years=1)


# ===== Pipeline Tests =====


class TestCreateMinimalPipeline:
    """创建最小管道测试"""

    def test_create_minimal_pipeline(self):
        """测试创建最小管道"""
        pipeline = create_minimal_pipeline()

        assert pipeline is not None
        assert len(pipeline.cleaners) == 3  # DateConverter + DuplicateCleaner + MissingValueCleaner
        assert pipeline.adjuster is None

    def test_pipeline_can_run(self):
        """测试管道可以运行"""
        pipeline = create_minimal_pipeline()

        df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000001.SZ"],
                "trade_date": ["20240101", "20240102"],
                "close": [10.0, 10.5],
            }
        )

        result = pipeline.run(df)

        assert len(result) == 2


# ===== Edge Cases Tests =====


class TestEdgeCases:
    """边缘情况测试"""

    @pytest.mark.asyncio
    async def test_update_with_none_latest_date(self, scheduler, mock_repository, mock_data_source):
        """测试无最新日期时的更新"""
        mock_repository.get_latest_trade_date = AsyncMock(return_value=None)

        await scheduler._update_daily_quotes()

        # 应该仍然调用 get_daily_quotes
        mock_data_source.get_daily_quotes.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_task_with_exception(self, scheduler, mock_data_source):
        """测试任务执行异常"""
        mock_data_source.get_daily_quotes = AsyncMock(side_effect=Exception("Network Error"))

        # 不应该抛出异常
        await scheduler._update_daily_quotes()

    def test_scheduler_replace_existing_job(self, scheduler):
        """测试替换已存在的任务"""

        async def task1():
            pass

        async def task2():
            pass

        scheduler.add_job(
            job_id="replace_test",
            func=task1,
            cron="0 18 * * *",
        )

        # 替换为新的任务
        new_job = scheduler.add_job(
            job_id="replace_test",
            func=task2,
            cron="0 19 * * *",
            replace=True,
        )

        # 验证任务存在
        assert new_job is not None
        assert new_job.id == "replace_test"
