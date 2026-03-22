"""ETL 清洗器基类

定义所有清洗器的抽象接口，支持管道式组合。
"""

from abc import ABC, abstractmethod

import pandas as pd


class BaseCleaner(ABC):
    """清洗器抽象基类

    所有清洗器都需要继承此类并实现 clean 方法。
    清洗器设计为无状态的（除了配置参数），便于复用和测试。

    Example:
        >>> class MyCleaner(BaseCleaner):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_cleaner"
        ...
        ...     def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        ...         return df.dropna()
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """清洗器名称，用于日志和调试"""
        ...

    @abstractmethod
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行清洗操作

        Args:
            df: 待清洗的 DataFrame

        Returns:
            清洗后的 DataFrame

        Note:
            - 不应修改原始 DataFrame（返回新对象）
            - 可以添加新列（如标记列）
            - 应记录清洗统计信息
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class BaseTransformer(ABC):
    """数据转换器基类

    用于需要额外数据的转换操作（如复权需要复权因子）。
    与 Cleaner 不同，Transformer 可能需要外部数据。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """转换器名称"""
        ...

    @abstractmethod
    def transform(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """执行转换操作

        Args:
            df: 待转换的 DataFrame
            **kwargs: 额外参数（如复权因子数据）

        Returns:
            转换后的 DataFrame
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class BaseFilter(ABC):
    """过滤器基类

    用于过滤不符合条件的记录。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """过滤器名称"""
        ...

    @abstractmethod
    def filter(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """执行过滤操作

        Args:
            df: 待过滤的 DataFrame
            **kwargs: 过滤条件参数

        Returns:
            过滤后的 DataFrame
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class CleaningStats:
    """清洗统计信息

    记录清洗过程中的统计信息，用于日志和报告。
    """

    def __init__(self, cleaner_name: str):
        self.cleaner_name = cleaner_name
        self.input_rows = 0
        self.output_rows = 0
        self.removed_rows = 0
        self.modified_rows = 0
        self.details: dict = {}

    @property
    def removal_rate(self) -> float:
        """移除率"""
        if self.input_rows == 0:
            return 0.0
        return self.removed_rows / self.input_rows

    def to_dict(self) -> dict:
        return {
            "cleaner": self.cleaner_name,
            "input_rows": self.input_rows,
            "output_rows": self.output_rows,
            "removed_rows": self.removed_rows,
            "modified_rows": self.modified_rows,
            "removal_rate": f"{self.removal_rate:.2%}",
            "details": self.details,
        }

    def __repr__(self) -> str:
        return (
            f"CleaningStats({self.cleaner_name}: "
            f"in={self.input_rows}, out={self.output_rows}, "
            f"removed={self.removed_rows})"
        )
