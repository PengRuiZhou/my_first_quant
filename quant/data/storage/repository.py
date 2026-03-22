"""数据仓库层

提供数据的 CRUD 操作，封装数据库访问逻辑。
"""

from datetime import date
from typing import TypeVar

import pandas as pd
from loguru import logger
from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from quant.core.config import get_settings
from quant.data.models import (
    Base,
    DailyBasic,
    DailyQuote,
    FinancialIndicator,
    IndexDailyQuote,
    IndexInfo,
    StockInfo,
    TradeCalendar,
)

ModelType = TypeVar("ModelType", bound=Base)


class DataRepository:
    """数据仓库

    提供所有数据类型的 CRUD 操作。
    使用异步 SQLAlchemy 2.0。
    """

    def __init__(
        self,
        db_url: str | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ):
        """初始化数据仓库

        Args:
            db_url: 数据库连接 URL，默认从配置读取
            session_factory: 会话工厂，用于测试注入
        """
        self.db_url = db_url or get_settings().db.async_url

        if session_factory:
            self._session_factory = session_factory
        else:
            engine = create_async_engine(self.db_url, echo=False, pool_pre_ping=True)
            self._session_factory = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )

    async def create_tables(self) -> None:
        """创建所有表"""
        engine = create_async_engine(self.db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        logger.info("数据库表创建完成")

    async def drop_tables(self) -> None:
        """删除所有表"""
        engine = create_async_engine(self.db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        logger.info("数据库表删除完成")

    # ===== 通用方法 =====

    async def _bulk_insert(
        self,
        model_class: type[ModelType],
        df: pd.DataFrame,
        on_conflict: str = "do_nothing",
        index_elements: list[str] | None = None,
    ) -> int:
        """批量插入数据

        Args:
            model_class: 模型类
            df: 数据 DataFrame
            on_conflict: 冲突处理策略 (do_nothing/do_update)
            index_elements: 冲突检测的索引列

        Returns:
            插入的行数
        """
        if df.empty:
            return 0

        # 转换 DataFrame 为字典列表
        records = df.to_dict(orient="records")

        # 处理 NaN 值
        cleaned_records = []
        for record in records:
            cleaned = {k: (None if pd.isna(v) else v) for k, v in record.items()}
            cleaned_records.append(cleaned)

        async with self._session_factory() as session:
            stmt = insert(model_class).values(cleaned_records)

            if on_conflict == "do_update" and index_elements:
                # PostgreSQL upsert
                update_cols = {
                    c.name: stmt.excluded[c.name]
                    for c in model_class.__table__.columns
                    if c.name not in index_elements
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=index_elements,
                    set_=update_cols,
                )
            else:
                stmt = stmt.on_conflict_do_nothing()

            result = await session.execute(stmt)
            await session.commit()

            # rowcount returns number of rows affected (inserted or updated)
            inserted = getattr(result, "rowcount", 0) or 0
            logger.debug(f"{model_class.__tablename__}: 插入 {inserted} 行")
            return inserted

    # ===== 股票信息 =====

    async def get_stock_list(
        self,
        active_only: bool = True,
    ) -> pd.DataFrame:
        """获取股票列表

        Args:
            active_only: 仅返回在市股票

        Returns:
            股票信息 DataFrame
        """
        async with self._session_factory() as session:
            stmt = select(StockInfo)
            if active_only:
                stmt = stmt.where(StockInfo.is_active.is_(True))

            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return pd.DataFrame()

            data = [
                {
                    "ts_code": r.ts_code,
                    "symbol": r.symbol,
                    "name": r.name,
                    "area": r.area,
                    "industry": r.industry,
                    "market": r.market,
                    "list_date": r.list_date,
                    "delist_date": r.delist_date,
                    "is_active": r.is_active,
                    "full_name": r.full_name,
                    "exchange": r.exchange,
                }
                for r in rows
            ]
            return pd.DataFrame(data)

    async def upsert_stock_info(self, df: pd.DataFrame) -> int:
        """更新/插入股票信息

        Args:
            df: 股票信息 DataFrame

        Returns:
            影响的行数
        """
        return await self._bulk_insert(
            StockInfo,
            df,
            on_conflict="do_update",
            index_elements=["ts_code"],
        )

    # ===== 指数信息 =====

    async def get_index_list(self) -> pd.DataFrame:
        """获取指数列表"""
        async with self._session_factory() as session:
            stmt = select(IndexInfo)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return pd.DataFrame()

            data = [
                {
                    "ts_code": r.ts_code,
                    "name": r.name,
                    "full_name": r.full_name,
                    "market": r.market,
                    "publisher": r.publisher,
                    "base_date": r.base_date,
                    "base_point": r.base_point,
                }
                for r in rows
            ]
            return pd.DataFrame(data)

    async def upsert_index_info(self, df: pd.DataFrame) -> int:
        """更新/插入指数信息"""
        return await self._bulk_insert(
            IndexInfo,
            df,
            on_conflict="do_update",
            index_elements=["ts_code"],
        )

    # ===== 日线行情 =====

    async def get_daily_quotes(
        self,
        ts_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取日线行情

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            日线行情 DataFrame
        """
        async with self._session_factory() as session:
            stmt = select(DailyQuote)

            conditions = []
            if ts_code:
                conditions.append(DailyQuote.ts_code == ts_code)
            if start_date:
                conditions.append(DailyQuote.trade_date >= start_date)
            if end_date:
                conditions.append(DailyQuote.trade_date <= end_date)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.order_by(DailyQuote.trade_date)

            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return pd.DataFrame()

            data = [
                {
                    "ts_code": r.ts_code,
                    "trade_date": r.trade_date,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "pre_close": r.pre_close,
                    "change": r.change,
                    "pct_chg": r.pct_chg,
                    "vol": r.vol,
                    "amount": r.amount,
                    "turnover_rate": r.turnover_rate,
                }
                for r in rows
            ]
            return pd.DataFrame(data)

    async def upsert_daily_quotes(self, df: pd.DataFrame) -> int:
        """更新/插入日线行情"""
        return await self._bulk_insert(
            DailyQuote,
            df,
            on_conflict="do_update",
            index_elements=["ts_code", "trade_date"],
        )

    async def delete_daily_quotes(
        self,
        ts_code: str | None = None,
        before_date: date | None = None,
    ) -> int:
        """删除日线行情

        Args:
            ts_code: 股票代码
            before_date: 删除此日期之前的数据

        Returns:
            删除的行数
        """
        async with self._session_factory() as session:
            stmt = delete(DailyQuote)

            conditions = []
            if ts_code:
                conditions.append(DailyQuote.ts_code == ts_code)
            if before_date:
                conditions.append(DailyQuote.trade_date < before_date)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await session.execute(stmt)
            await session.commit()
            return getattr(result, "rowcount", 0) or 0

    # ===== 指数行情 =====

    async def get_index_quotes(
        self,
        ts_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取指数行情"""
        async with self._session_factory() as session:
            stmt = select(IndexDailyQuote)

            conditions = []
            if ts_code:
                conditions.append(IndexDailyQuote.ts_code == ts_code)
            if start_date:
                conditions.append(IndexDailyQuote.trade_date >= start_date)
            if end_date:
                conditions.append(IndexDailyQuote.trade_date <= end_date)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.order_by(IndexDailyQuote.trade_date)

            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return pd.DataFrame()

            data = [
                {
                    "ts_code": r.ts_code,
                    "trade_date": r.trade_date,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "pre_close": r.pre_close,
                    "change": r.change,
                    "pct_chg": r.pct_chg,
                    "vol": r.vol,
                    "amount": r.amount,
                }
                for r in rows
            ]
            return pd.DataFrame(data)

    async def upsert_index_quotes(self, df: pd.DataFrame) -> int:
        """更新/插入指数行情"""
        return await self._bulk_insert(
            IndexDailyQuote,
            df,
            on_conflict="do_update",
            index_elements=["ts_code", "trade_date"],
        )

    # ===== 交易日历 =====

    async def get_trade_dates(
        self,
        exchange: str = "SSE",
        start_date: date | None = None,
        end_date: date | None = None,
        is_open: bool = True,
    ) -> list[date]:
        """获取交易日列表

        Args:
            exchange: 交易所
            start_date: 开始日期
            end_date: 结束日期
            is_open: 是否交易日

        Returns:
            交易日列表
        """
        async with self._session_factory() as session:
            stmt = select(TradeCalendar.cal_date).where(
                TradeCalendar.exchange == exchange,
                TradeCalendar.is_open == is_open,
            )

            if start_date:
                stmt = stmt.where(TradeCalendar.cal_date >= start_date)
            if end_date:
                stmt = stmt.where(TradeCalendar.cal_date <= end_date)

            stmt = stmt.order_by(TradeCalendar.cal_date)

            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_latest_trade_date(
        self,
        exchange: str = "SSE",
    ) -> date | None:
        """获取最新交易日

        Args:
            exchange: 交易所

        Returns:
            最新交易日，如果没有则返回 None
        """
        async with self._session_factory() as session:
            stmt = (
                select(TradeCalendar.cal_date)
                .where(
                    TradeCalendar.exchange == exchange,
                    TradeCalendar.is_open.is_(True),
                )
                .order_by(TradeCalendar.cal_date.desc())
                .limit(1)
            )

            result = await session.execute(stmt)
            row = result.first()
            return row[0] if row else None

    async def upsert_trade_calendar(self, df: pd.DataFrame) -> int:
        """更新/插入交易日历"""
        return await self._bulk_insert(
            TradeCalendar,
            df,
            on_conflict="do_update",
            index_elements=["exchange", "cal_date"],
        )

    # ===== 每日指标 =====

    async def get_daily_basic(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取每日指标"""
        async with self._session_factory() as session:
            stmt = select(DailyBasic)

            conditions = []
            if ts_code:
                conditions.append(DailyBasic.ts_code == ts_code)
            if trade_date:
                conditions.append(DailyBasic.trade_date == trade_date)
            if start_date:
                conditions.append(DailyBasic.trade_date >= start_date)
            if end_date:
                conditions.append(DailyBasic.trade_date <= end_date)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return pd.DataFrame()

            data = [
                {
                    "ts_code": r.ts_code,
                    "trade_date": r.trade_date,
                    "close": r.close,
                    "turnover_rate": r.turnover_rate,
                    "turnover_rate_f": r.turnover_rate_f,
                    "volume_ratio": r.volume_ratio,
                    "pe": r.pe,
                    "pe_ttm": r.pe_ttm,
                    "pb": r.pb,
                    "ps": r.ps,
                    "total_mv": r.total_mv,
                    "circ_mv": r.circ_mv,
                }
                for r in rows
            ]
            return pd.DataFrame(data)

    async def upsert_daily_basic(self, df: pd.DataFrame) -> int:
        """更新/插入每日指标"""
        return await self._bulk_insert(
            DailyBasic,
            df,
            on_conflict="do_update",
            index_elements=["ts_code", "trade_date"],
        )

    # ===== 财务指标 =====

    async def get_financial_indicator(
        self,
        ts_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取财务指标"""
        async with self._session_factory() as session:
            stmt = select(FinancialIndicator)

            conditions = []
            if ts_code:
                conditions.append(FinancialIndicator.ts_code == ts_code)
            if start_date:
                conditions.append(FinancialIndicator.end_date >= start_date)
            if end_date:
                conditions.append(FinancialIndicator.end_date <= end_date)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return pd.DataFrame()

            data = [
                {
                    "ts_code": r.ts_code,
                    "ann_date": r.ann_date,
                    "end_date": r.end_date,
                    "roe": r.roe,
                    "roe_dt": r.roe_dt,
                    "roa": r.roa,
                    "netprofit_margin": r.netprofit_margin,
                    "grossprofit_margin": r.grossprofit_margin,
                    "debt_to_assets": r.debt_to_assets,
                    "current_ratio": r.current_ratio,
                    "quick_ratio": r.quick_ratio,
                    "eps": r.eps,
                    "bvps": r.bvps,
                    "pe": r.pe,
                    "pe_ttm": r.pe_ttm,
                    "pb": r.pb,
                }
                for r in rows
            ]
            return pd.DataFrame(data)

    async def upsert_financial_indicator(self, df: pd.DataFrame) -> int:
        """更新/插入财务指标"""
        return await self._bulk_insert(
            FinancialIndicator,
            df,
            on_conflict="do_update",
            index_elements=["ts_code", "ann_date", "end_date"],
        )

    # ===== 统计方法 =====

    async def get_daily_quote_count(
        self,
        ts_code: str | None = None,
    ) -> int:
        """获取日线行情数量"""
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(DailyQuote)
            if ts_code:
                stmt = stmt.where(DailyQuote.ts_code == ts_code)

            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_stock_count(self, active_only: bool = True) -> int:
        """获取股票数量"""
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(StockInfo)
            if active_only:
                stmt = stmt.where(StockInfo.is_active.is_(True))

            result = await session.execute(stmt)
            return result.scalar() or 0
