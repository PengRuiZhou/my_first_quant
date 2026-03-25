"""数据调度器

使用 APScheduler 管理定时数据更新任务。
"""

from collections.abc import Callable, Coroutine
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from quant.data.etl import create_minimal_pipeline
from quant.data.sources.base import BaseDataSource
from quant.data.sources.tushare_client import TushareClient

from .repository import DataRepository


class DataScheduler:
    """数据调度器

    管理定时数据更新任务：
    - 每日行情更新
    - 每周股票列表更新
    - 每周交易日历更新
    """

    def __init__(
        self,
        repository: DataRepository | None = None,
        data_source: BaseDataSource | None = None,
    ):
        """初始化调度器

        Args:
            repository: 数据仓库实例
            data_source: 数据源实例，默认使用 Tushare
        """
        self.repository = repository or DataRepository()
        self.data_source = data_source or TushareClient()
        self._scheduler = AsyncIOScheduler()
        self._is_running = False

    # ===== 调度控制 =====

    def start(self) -> None:
        """启动调度器"""
        if self._is_running:
            logger.warning("调度器已在运行")
            return

        self._scheduler.start()
        self._is_running = True
        logger.info("数据调度器已启动")

    def stop(self, wait: bool = True) -> None:
        """停止调度器

        Args:
            wait: 是否等待当前任务完成
        """
        if not self._is_running:
            logger.warning("调度器未在运行")
            return

        self._scheduler.shutdown(wait=wait)
        self._is_running = False
        logger.info("数据调度器已停止")

    def get_jobs(self) -> list[dict]:
        """获取所有任务

        Returns:
            任务信息列表
        """
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name or job.id,
                    "next_run": job.next_run_time,
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    def get_job(self, job_id: str) -> Job | None:
        """获取指定任务

        Args:
            job_id: 任务 ID

        Returns:
            任务对象，不存在则返回 None
        """
        return self._scheduler.get_job(job_id)

    # ===== 任务管理 =====

    def add_job(
        self,
        job_id: str,
        func: Callable[[], Coroutine[Any, Any, None]],
        cron: str | None = None,
        interval_seconds: int | None = None,
        replace: bool = True,
        name: str | None = None,
    ) -> Job:
        """添加定时任务

        Args:
            job_id: 任务唯一标识
            func: 异步任务函数
            cron: Cron 表达式（如 "0 18 * * *" 表示每天 18:00）
            interval_seconds: 间隔秒数（与 cron 二选一）
            replace: 是否替换已存在的任务
            name: 任务名称

        Returns:
            任务对象
        """
        if cron:
            parts = cron.split()
            trigger = CronTrigger(
                minute=parts[0] if len(parts) > 0 else "*",
                hour=parts[1] if len(parts) > 1 else "*",
                day=parts[2] if len(parts) > 2 else "*",
                month=parts[3] if len(parts) > 3 else "*",
                day_of_week=parts[4] if len(parts) > 4 else "*",
            )
        elif interval_seconds:
            trigger = IntervalTrigger(seconds=interval_seconds)
        else:
            raise ValueError("必须提供 cron 或 interval_seconds")

        job = self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=name or job_id,
            replace_existing=replace,
        )

        logger.info(f"添加任务: {job_id}, trigger: {trigger}")
        return job

    def remove_job(self, job_id: str) -> bool:
        """移除任务

        Args:
            job_id: 任务 ID

        Returns:
            是否成功移除
        """
        job = self._scheduler.get_job(job_id)
        if job:
            self._scheduler.remove_job(job_id)
            logger.info(f"移除任务: {job_id}")
            return True
        return False

    def pause_job(self, job_id: str) -> bool:
        """暂停任务"""
        job = self._scheduler.get_job(job_id)
        if job:
            self._scheduler.pause_job(job_id)
            logger.info(f"暂停任务: {job_id}")
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        """恢复任务"""
        job = self._scheduler.get_job(job_id)
        if job:
            self._scheduler.resume_job(job_id)
            logger.info(f"恢复任务: {job_id}")
            return True
        return False

    # ===== 默认任务 =====

    def setup_default_jobs(self) -> None:
        """设置默认定时任务

        任务列表：
        - 每日 18:00 更新行情数据
        - 每日 18:30 更新每日指标
        - 每周六 10:00 更新股票列表
        - 每周六 10:30 更新交易日历
        """
        # 每日 18:00 更新行情
        self.add_job(
            job_id="update_daily_quotes",
            func=self._update_daily_quotes,
            cron="0 18 * * *",
            name="每日行情更新",
        )

        # 每日 18:30 更新每日指标
        self.add_job(
            job_id="update_daily_basic",
            func=self._update_daily_basic,
            cron="30 18 * * *",
            name="每日指标更新",
        )

        # 每周六 10:00 更新股票列表
        self.add_job(
            job_id="update_stock_list",
            func=self._update_stock_list,
            cron="0 10 * * 6",
            name="股票列表更新",
        )

        # 每周六 10:30 更新交易日历
        self.add_job(
            job_id="update_trade_calendar",
            func=self._update_trade_calendar,
            cron="30 10 * * 6",
            name="交易日历更新",
        )

        logger.info("默认任务设置完成")

    # ===== 任务实现 =====

    async def _update_daily_quotes(self) -> None:
        """更新日线行情"""
        try:
            logger.info("开始更新日线行情...")

            # 获取最新交易日
            latest = await self.repository.get_latest_trade_date()
            today = datetime.now().date()

            # 获取数据
            df = await self.data_source.get_daily_quotes(
                start_date=latest.strftime("%Y%m%d") if latest else None,
                end_date=today.strftime("%Y%m%d"),
            )

            if df.empty:
                logger.info("没有新的行情数据")
                return

            # ETL 处理
            pipeline = create_minimal_pipeline()
            df_clean = pipeline.run(df)

            # 存储
            count = await self.repository.upsert_daily_quotes(df_clean)
            logger.info(f"日线行情更新完成，插入 {count} 条记录")

        except Exception as e:
            logger.error(f"更新日线行情失败: {e}")

    async def _update_daily_basic(self) -> None:
        """更新每日指标"""
        try:
            logger.info("开始更新每日指标...")

            latest = await self.repository.get_latest_trade_date()
            today = datetime.now().date()

            df = await self.data_source.get_daily_basic(
                start_date=latest.strftime("%Y%m%d") if latest else None,
                end_date=today.strftime("%Y%m%d"),
            )

            if df.empty:
                logger.info("没有新的每日指标数据")
                return

            count = await self.repository.upsert_daily_basic(df)
            logger.info(f"每日指标更新完成，插入 {count} 条记录")

        except Exception as e:
            logger.error(f"更新每日指标失败: {e}")

    async def _update_stock_list(self) -> None:
        """更新股票列表"""
        try:
            logger.info("开始更新股票列表...")

            df = await self.data_source.get_stock_list()

            if df.empty:
                logger.info("没有股票列表数据")
                return

            count = await self.repository.upsert_stock_info(df)
            logger.info(f"股票列表更新完成，插入 {count} 条记录")

        except Exception as e:
            logger.error(f"更新股票列表失败: {e}")

    async def _update_trade_calendar(self) -> None:
        """更新交易日历"""
        try:
            logger.info("开始更新交易日历...")

            df = await self.data_source.get_trade_calendar(exchange="SSE")

            if df.empty:
                logger.info("没有交易日历数据")
                return

            count = await self.repository.upsert_trade_calendar(df)
            logger.info(f"交易日历更新完成，插入 {count} 条记录")

        except Exception as e:
            logger.error(f"更新交易日历失败: {e}")

    # ===== 手动触发 =====

    async def run_job(self, job_id: str) -> bool:
        """手动运行指定任务

        Args:
            job_id: 任务 ID

        Returns:
            是否成功运行
        """
        job_map = {
            "update_daily_quotes": self._update_daily_quotes,
            "update_daily_basic": self._update_daily_basic,
            "update_stock_list": self._update_stock_list,
            "update_trade_calendar": self._update_trade_calendar,
        }

        func = job_map.get(job_id)
        if func:
            logger.info(f"手动触发任务: {job_id}")
            await func()
            return True

        logger.error(f"未知的任务 ID: {job_id}")
        return False

    # ===== 初始化数据 =====

    async def init_historical_data(self, years: int = 3) -> dict[str, int]:
        """初始化历史数据

        Args:
            years: 初始化多少年的数据

        Returns:
            各类型数据的记录数
        """
        end_date = date_type.today()
        start_date = end_date - timedelta(days=years * 365)

        logger.info(f"开始初始化 {years} 年历史数据...")
        stats: dict[str, int] = {}

        try:
            # 1. 股票列表
            logger.info("获取股票列表...")
            stock_df = await self.data_source.get_stock_list()
            stats["stock_list"] = await self.repository.upsert_stock_info(stock_df)

            # 2. 交易日历
            logger.info("获取交易日历...")
            cal_df = await self.data_source.get_trade_calendar(
                exchange="SSE",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            stats["trade_calendar"] = await self.repository.upsert_trade_calendar(cal_df)

            # 3. 日线行情（分批获取）
            logger.info("获取日线行情...")
            quotes_df = await self.data_source.get_daily_quotes(
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            if not quotes_df.empty:
                pipeline = create_minimal_pipeline()
                quotes_df = pipeline.run(quotes_df)
            stats["daily_quotes"] = await self.repository.upsert_daily_quotes(quotes_df)

            # 4. 每日指标
            logger.info("获取每日指标...")
            basic_df = await self.data_source.get_daily_basic(
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            stats["daily_basic"] = await self.repository.upsert_daily_basic(basic_df)

            # 5. 指数行情
            logger.info("获取指数行情...")
            index_df = await self.data_source.get_index_quotes(
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            stats["index_quotes"] = await self.repository.upsert_index_quotes(index_df)

            logger.info(f"历史数据初始化完成: {stats}")

        except Exception as e:
            logger.error(f"历史数据初始化失败: {e}")
            raise

        return stats

    @property
    def is_running(self) -> bool:
        """调度器是否在运行"""
        return self._is_running
