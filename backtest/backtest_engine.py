"""
事件驱动回测引擎

逐bar遍历K线数据, 模拟策略信号执行, 记录交易和资金曲线。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
from datetime import datetime
import pandas as pd
import numpy as np
import logging

from backtest import metrics

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """单笔交易记录"""
    entry_time: datetime           # 开仓时间
    exit_time: Optional[datetime]  # 平仓时间 (持仓中为None)
    direction: int                  # 方向: 1=多头, -1=空头
    entry_price: float             # 开仓价
    exit_price: Optional[float]    # 平仓价 (持仓中为None)
    volume: float                   # 手数
    pnl: float = 0.0               # 盈亏金额
    pnl_pct: float = 0.0           # 盈亏百分比

    def __repr__(self) -> str:
        direction_str = "多头" if self.direction == 1 else "空头"
        return (f"Trade({direction_str}, {self.entry_time} -> {self.exit_time}, "
                f"entry={self.entry_price:.5f}, exit={self.exit_price}, "
                f"pnl={self.pnl:.2f})")


@dataclass
class BacktestResult:
    """回测结果"""
    trades: List[Trade] = field(default_factory=list)      # 交易记录列表
    equity_curve: pd.Series = field(default_factory=pd.Series)  # 资金曲线
    metrics: dict = field(default_factory=dict)            # 性能指标
    signals_df: pd.DataFrame = field(default_factory=pd.DataFrame)  # 带信号的K线数据

    def __repr__(self) -> str:
        return f"BacktestResult(trades={len(self.trades)}, final_equity={self.equity_curve.iloc[-1] if not self.equity_curve.empty else 0:.2f})"


class BacktestEngine:
    """
    事件驱动回测引擎

    模拟策略信号在历史K线上的执行情况, 记录每笔交易和每日权益变化。

    Attributes:
        initial_capital: 初始资金
        volume: 默认交易手数
        spread: 点差 (点)
        commission: 每手手续费
        sl_points: 止损点数 (0表示不设)
        tp_points: 止盈点数 (0表示不设)
    """

    def __init__(
        self,
        initial_capital: float = 10000.0,
        volume: float = 0.1,
        spread: float = 0.0,
        commission: float = 0.0,
        sl_points: float = 0.0,
        tp_points: float = 0.0
    ):
        """
        初始化回测引擎

        Args:
            initial_capital: 初始资金, 默认10000
            volume: 每笔交易手数, 默认0.1手
            spread: 点差 (点), 开仓时计入成本
            commission: 每手手续费, 默认0
            sl_points: 止损点数, 0表示不设止损
            tp_points: 止盈点数, 0表示不设止盈
        """
        self.initial_capital = initial_capital
        self.volume = volume
        self.spread = spread
        self.commission = commission
        self.sl_points = sl_points
        self.tp_points = tp_points

    def run(self, df: pd.DataFrame, strategy: Any) -> BacktestResult:
        """
        运行回测

        Args:
            df: K线数据, 必须包含 time, open, high, low, close 列
            strategy: 策略对象, 必须实现 generate_signals(df) -> pd.DataFrame 方法

        Returns:
            BacktestResult: 包含交易记录、资金曲线、性能指标的结果对象
        """
        # 验证输入
        required_cols = ['time', 'open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame缺少必需列: {col}")

        # 生成策略信号
        logger.info("生成策略信号...")
        signals_df = strategy.generate_signals(df.copy())

        if 'signal' not in signals_df.columns:
            raise ValueError("策略generate_signals()未返回signal列")

        # 确保time列为索引或便于访问
        if 'time' in signals_df.columns:
            signals_df = signals_df.set_index('time')

        # 初始化
        capital = self.initial_capital
        trades: List[Trade] = []
        equity_values = [capital]

        # 持仓状态
        current_trade: Optional[Trade] = None

        logger.info(f"开始回测, 共{len(signals_df)}根K线...")

        # 逐bar遍历
        for idx, row in signals_df.iterrows():
            bar_time = idx
            open_price = row['open']
            high_price = row['high']
            low_price = row['low']
            close_price = row['close']
            signal = row['signal']

            # 检查止损止盈 (仅当有持仓时)
            if current_trade is not None:
                should_close = False
                exit_price = None
                exit_reason = ""

                # 检查止损
                if self.sl_points > 0:
                    if current_trade.direction == 1:  # 多头
                        sl_price = current_trade.entry_price - self.sl_points * 0.0001
                        if low_price <= sl_price:
                            should_close = True
                            exit_price = sl_price
                            exit_reason = "止损"
                    else:  # 空头
                        sl_price = current_trade.entry_price + self.sl_points * 0.0001
                        if high_price >= sl_price:
                            should_close = True
                            exit_price = sl_price
                            exit_reason = "止损"

                # 检查止盈
                if not should_close and self.tp_points > 0:
                    if current_trade.direction == 1:  # 多头
                        tp_price = current_trade.entry_price + self.tp_points * 0.0001
                        if high_price >= tp_price:
                            should_close = True
                            exit_price = tp_price
                            exit_reason = "止盈"
                    else:  # 空头
                        tp_price = current_trade.entry_price - self.tp_points * 0.0001
                        if low_price <= tp_price:
                            should_close = True
                            exit_price = tp_price
                            exit_reason = "止盈"

                # 检查平仓信号
                if not should_close and signal == -1:
                    should_close = True
                    exit_price = close_price
                    exit_reason = "信号平仓"

                # 执行平仓
                if should_close:
                    current_trade.exit_time = bar_time
                    current_trade.exit_price = exit_price

                    # 计算盈亏
                    if current_trade.direction == 1:  # 多头
                        current_trade.pnl = (exit_price - current_trade.entry_price) * current_trade.volume * 100
                    else:  # 空头
                        current_trade.pnl = (current_trade.entry_price - exit_price) * current_trade.volume * 100

                    # 扣除点差和手续费
                    current_trade.pnl -= self.spread * current_trade.volume
                    current_trade.pnl -= self.commission * current_trade.volume

                    # 计算盈亏百分比
                    capital_in_trade = current_trade.entry_price * current_trade.volume * 100
                    current_trade.pnl_pct = (current_trade.pnl / capital_in_trade) * 100

                    capital += current_trade.pnl
                    trades.append(current_trade)
                    current_trade = None

                    logger.debug(f"{bar_time} {exit_reason}: 平仓价={exit_price:.5f}, 盈亏={current_trade.pnl:.2f}")

            # 开仓逻辑
            if current_trade is None and signal == 1:
                # 多头开仓
                entry_price = open_price + self.spread * 0.0001  # 加点差
                current_trade = Trade(
                    entry_time=bar_time,
                    exit_time=None,
                    direction=1,
                    entry_price=entry_price,
                    exit_price=None,
                    volume=self.volume
                )
                logger.debug(f"{bar_time} 开多: 价格={entry_price:.5f}")

            # 记录权益
            equity_values.append(capital)

        # 强制平仓未结束的交易
        if current_trade is not None:
            last_row = signals_df.iloc[-1]
            last_close = last_row['close']
            last_time = signals_df.index[-1]

            current_trade.exit_time = last_time
            current_trade.exit_price = last_close

            if current_trade.direction == 1:
                current_trade.pnl = (last_close - current_trade.entry_price) * current_trade.volume * 100
            else:
                current_trade.pnl = (current_trade.entry_price - last_close) * current_trade.volume * 100

            current_trade.pnl -= self.spread * current_trade.volume
            current_trade.pnl -= self.commission * current_trade.volume

            capital_in_trade = current_trade.entry_price * current_trade.volume * 100
            current_trade.pnl_pct = (current_trade.pnl / capital_in_trade) * 100

            capital += current_trade.pnl
            trades.append(current_trade)
            logger.debug(f"强制平仓: 价格={last_close:.5f}, 盈亏={current_trade.pnl:.2f}")

        # 构建资金曲线
        equity_curve = pd.Series(equity_values, index=[signals_df.index[0] - pd.Timedelta(seconds=1)] + list(signals_df.index))

        # 计算性能指标
        logger.info("计算性能指标...")
        calculated_metrics = metrics.calculate_metrics(equity_curve, trades)

        logger.info(f"回测完成, 共{len(trades)}笔交易, 最终资金={capital:.2f}")

        return BacktestResult(
            trades=trades,
            equity_curve=equity_curve,
            metrics=calculated_metrics,
            signals_df=signals_df.reset_index()
        )
