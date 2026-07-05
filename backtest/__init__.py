"""
回测模块

包含事件驱动回测引擎和性能指标计算功能。
"""

from backtest.metrics import (
    calculate_metrics,
    print_metrics,
    format_metrics_table
)
from backtest.backtest_engine import BacktestEngine, BacktestResult, Trade

__all__ = [
    'BacktestEngine',
    'BacktestResult',
    'Trade',
    'calculate_metrics',
    'print_metrics',
    'format_metrics_table'
]
