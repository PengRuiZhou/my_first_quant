"""双源交叉验证器

对 Tushare 和 AKShare 数据进行交叉验证，提高数据质量。
"""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class ValidationReport:
    """验证报告"""

    total_rows: int = 0
    matched_rows: int = 0
    mismatched_rows: int = 0
    missing_in_tushare: int = 0
    missing_in_akshare: int = 0

    # 字段级别的差异统计
    field_diffs: dict[str, dict] = field(default_factory=dict)

    # 异常记录
    anomalies: list[dict] = field(default_factory=list)

    @property
    def match_rate(self) -> float:
        """匹配率"""
        if self.total_rows == 0:
            return 0.0
        return self.matched_rows / self.total_rows

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_rows": self.total_rows,
            "matched_rows": self.matched_rows,
            "mismatched_rows": self.mismatched_rows,
            "missing_in_tushare": self.missing_in_tushare,
            "missing_in_akshare": self.missing_in_akshare,
            "match_rate": f"{self.match_rate:.2%}",
            "field_diffs": self.field_diffs,
            "anomalies": self.anomalies[:10],  # 只返回前10条异常
        }


class DataValidator:
    """双源数据验证器

    对 Tushare 和 AKShare 的数据进行交叉验证，策略：
    - 数值型：差值在容差内取均值，否则标记异常
    - 字符串：必须完全一致
    - 单源缺失：使用另一源填充
    """

    def __init__(self, tolerance: float = 0.01):
        """初始化验证器

        Args:
            tolerance: 数值型字段容差（默认 1%）
        """
        self.tolerance = tolerance
        self._report: ValidationReport | None = None

    def cross_validate(
        self,
        df_tushare: pd.DataFrame,
        df_akshare: pd.DataFrame,
        on: list[str] | None = None,
        numeric_fields: list[str] | None = None,
        string_fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """交叉验证并合并数据

        Args:
            df_tushare: Tushare 数据
            df_akshare: AKShare 数据
            on: 合并键，默认 ["ts_code", "trade_date"]
            numeric_fields: 数值型字段列表
            string_fields: 字符串字段列表

        Returns:
            合并后的 DataFrame，包含验证结果
        """
        if on is None:
            on = ["ts_code", "trade_date"]

        self._report = ValidationReport()

        # 空数据处理
        if df_tushare.empty and df_akshare.empty:
            logger.warning("两个数据源都为空")
            return pd.DataFrame()

        if df_tushare.empty:
            logger.warning("Tushare 数据为空，使用 AKShare 数据")
            self._report.missing_in_tushare = len(df_akshare)
            return df_akshare

        if df_akshare.empty:
            logger.warning("AKShare 数据为空，使用 Tushare 数据")
            self._report.missing_in_akshare = len(df_tushare)
            return df_tushare

        # 确保合并键存在
        for key in on:
            if key not in df_tushare.columns:
                df_tushare[key] = None
            if key not in df_akshare.columns:
                df_akshare[key] = None

        # 合并数据
        merged = pd.merge(
            df_tushare,
            df_akshare,
            on=on,
            how="outer",
            suffixes=("_tushare", "_akshare"),
            indicator=True,
        )

        self._report.total_rows = len(merged)

        # 统计缺失情况
        self._report.missing_in_tushare = (merged["_merge"] == "right_only").sum()
        self._report.missing_in_akshare = (merged["_merge"] == "left_only").sum()

        # 获取共同字段（排除合并键和 _merge）
        common_fields = set(df_tushare.columns) & set(df_akshare.columns) - set(on)

        # 自动识别字段类型
        if numeric_fields is None:
            numeric_fields = []
            for f in common_fields:
                if df_tushare[f].dtype in [np.float64, np.int64, float, int]:
                    numeric_fields.append(f)

        if string_fields is None:
            string_fields = []
            for f in common_fields:
                if df_tushare[f].dtype == object or df_tushare[f].dtype == str:
                    string_fields.append(f)

        result = merged.copy()

        # 处理数值型字段
        for field in numeric_fields:
            tushare_col = f"{field}_tushare"
            akshare_col = f"{field}_akshare"

            if tushare_col not in result.columns or akshare_col not in result.columns:
                continue

            # 计算差异
            diff = self._calculate_numeric_diff(
                result[tushare_col], result[akshare_col]
            )

            # 记录字段差异统计
            self._report.field_diffs[field] = {
                "mean_diff": float(diff.mean()) if not diff.empty else 0,
                "max_diff": float(diff.max()) if not diff.empty else 0,
                "mismatch_count": int((diff > self.tolerance).sum()),
            }

            # 合并数值：在容差内取均值，超出则标记异常
            result[field] = self._merge_numeric_field(
                result[tushare_col],
                result[akshare_col],
                diff,
                field,
            )

            # 删除原始列
            result.drop(columns=[tushare_col, akshare_col], inplace=True)

        # 处理字符串字段
        for field in string_fields:
            tushare_col = f"{field}_tushare"
            akshare_col = f"{field}_akshare"

            if tushare_col not in result.columns or akshare_col not in result.columns:
                continue

            # 合并字符串：优先使用 Tushare
            result[field] = self._merge_string_field(
                result[tushare_col],
                result[akshare_col],
                field,
            )

            # 删除原始列
            result.drop(columns=[tushare_col, akshare_col], inplace=True)

        # 删除临时列
        result.drop(columns=["_merge"], inplace=True)

        # 计算匹配行数
        self._report.matched_rows = self._report.total_rows - len(
            self._report.anomalies
        )
        self._report.mismatched_rows = len(self._report.anomalies)

        logger.info(
            f"交叉验证完成: 匹配率 {self._report.match_rate:.2%}, "
            f"异常 {self._report.mismatched_rows} 条"
        )

        return result

    def _calculate_numeric_diff(
        self, s1: pd.Series, s2: pd.Series
    ) -> pd.Series:
        """计算数值型差异（相对差异）"""
        # 避免除零
        denominator = s1.abs().replace(0, np.nan)
        diff = (s1 - s2).abs() / denominator
        return diff.fillna(0)

    def _merge_numeric_field(
        self,
        s_tushare: pd.Series,
        s_akshare: pd.Series,
        diff: pd.Series,
        field: str,
    ) -> pd.Series:
        """合并数值型字段"""
        result = pd.Series(index=s_tushare.index, dtype=float)

        for idx in s_tushare.index:
            t_val = s_tushare.get(idx)
            a_val = s_akshare.get(idx)
            d = diff.get(idx, 0)

            # 两个值都存在
            if pd.notna(t_val) and pd.notna(a_val):
                if d <= self.tolerance:
                    # 在容差内，取均值
                    result[idx] = (t_val + a_val) / 2
                else:
                    # 超出容差，标记异常，使用 Tushare 值
                    result[idx] = t_val
                    if self._report is not None:
                        self._report.anomalies.append({
                            "field": field,
                            "index": str(idx),
                            "tushare_value": float(t_val),
                            "akshare_value": float(a_val),
                            "diff": float(d),
                            "type": "numeric_mismatch",
                        })
            # 只有 Tushare 有值
            elif pd.notna(t_val):
                result[idx] = t_val
            # 只有 AKShare 有值
            elif pd.notna(a_val):
                result[idx] = a_val
            # 都没有值
            else:
                result[idx] = np.nan

        return result

    def _merge_string_field(
        self,
        s_tushare: pd.Series,
        s_akshare: pd.Series,
        field: str,
    ) -> pd.Series:
        """合并字符串字段"""
        result = pd.Series(index=s_tushare.index, dtype=object)

        for idx in s_tushare.index:
            t_val = s_tushare.get(idx)
            a_val = s_akshare.get(idx)

            # 两个值都存在
            if pd.notna(t_val) and pd.notna(a_val):
                if str(t_val) == str(a_val):
                    result[idx] = t_val
                else:
                    # 不一致，标记异常，使用 Tushare 值
                    result[idx] = t_val
                    if self._report is not None:
                        self._report.anomalies.append({
                            "field": field,
                            "index": str(idx),
                            "tushare_value": str(t_val),
                            "akshare_value": str(a_val),
                            "type": "string_mismatch",
                        })
            # 只有 Tushare 有值
            elif pd.notna(t_val):
                result[idx] = t_val
            # 只有 AKShare 有值
            elif pd.notna(a_val):
                result[idx] = a_val
            # 都没有值
            else:
                result[idx] = None

        return result

    def get_validation_report(self) -> dict:
        """获取验证报告"""
        if self._report is None:
            return {"error": "尚未进行验证"}
        return self._report.to_dict()

    def get_anomalies(self) -> list[dict]:
        """获取异常记录列表"""
        if self._report is None:
            return []
        return self._report.anomalies


def validate_and_merge(
    df_tushare: pd.DataFrame,
    df_akshare: pd.DataFrame,
    on: list[str] | None = None,
    tolerance: float = 0.01,
) -> tuple[pd.DataFrame, dict]:
    """便捷函数：验证并合并数据

    Args:
        df_tushare: Tushare 数据
        df_akshare: AKShare 数据
        on: 合并键
        tolerance: 容差

    Returns:
        (合并后的数据, 验证报告)
    """
    validator = DataValidator(tolerance=tolerance)
    merged = validator.cross_validate(df_tushare, df_akshare, on=on)
    report = validator.get_validation_report()
    return merged, report
