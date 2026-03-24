"""配置管理模块

使用 pydantic-settings 管理配置，支持环境变量和 .env 文件。
"""

from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """数据库配置"""

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=5432, description="数据库端口")
    user: str = Field(default="postgres", description="数据库用户")
    password: str = Field(default="", description="数据库密码")
    database: str = Field(default="quant", description="数据库名称")

    @property
    def url(self) -> str:
        """获取数据库连接 URL"""
        encoded_password = quote_plus(self.password)
        return f"postgresql://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_url(self) -> str:
        """获取异步数据库连接 URL"""
        encoded_password = quote_plus(self.password)
        return f"postgresql+asyncpg://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.database}"


class TushareConfig(BaseSettings):
    """Tushare 数据源配置"""

    model_config = SettingsConfigDict(
        env_prefix="TUSHARE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    token: str = Field(default="", description="Tushare API Token")
    api_url: str = Field(
        default="http://api.tushare.pro",
        description="Tushare API 地址"
    )
    timeout: int = Field(default=30, description="请求超时时间(秒)")
    retry_times: int = Field(default=3, description="重试次数")


class AKShareConfig(BaseSettings):
    """AKShare 数据源配置"""

    model_config = SettingsConfigDict(env_prefix="AKSHARE_")

    timeout: int = Field(default=30, description="请求超时时间(秒)")
    retry_times: int = Field(default=3, description="重试次数")


class BacktestConfig(BaseSettings):
    """回测配置"""

    model_config = SettingsConfigDict(env_prefix="BACKTEST_")

    initial_capital: float = Field(default=1_000_000.0, description="初始资金")
    commission_rate: float = Field(default=0.0003, description="佣金费率")
    stamp_duty: float = Field(default=0.001, description="印花税率(卖出)")
    slippage: float = Field(default=0.001, description="滑点")
    min_trade_unit: int = Field(default=100, description="最小交易单位(股)")


class RiskConfig(BaseSettings):
    """风控配置"""

    model_config = SettingsConfigDict(env_prefix="RISK_")

    max_position_pct: float = Field(default=0.1, description="单只股票最大仓位比例")
    max_industry_pct: float = Field(default=0.3, description="单个行业最大仓位比例")
    max_turnover: float = Field(default=0.5, description="最大换手率")
    stop_loss_pct: float = Field(default=0.1, description="止损比例")


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 环境
    env: Literal["development", "testing", "production"] = Field(
        default="development",
        description="运行环境"
    )
    debug: bool = Field(default=False, description="调试模式")

    # 日志
    log_level: str = Field(default="INFO", description="日志级别")
    log_dir: str = Field(default="logs", description="日志目录")

    # 子配置
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    tushare: TushareConfig = Field(default_factory=TushareConfig)
    akshare: AKShareConfig = Field(default_factory=AKShareConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
