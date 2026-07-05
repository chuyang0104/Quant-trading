"""
双均线交叉策略

当快速均线上穿慢速均线时买入（金叉），下穿时卖出（死叉）。
"""
from typing import Dict, Any
import pandas as pd
from strategy.base_strategy import BaseStrategyEx


class MA_Cross(BaseStrategyEx):
    """
    双均线交叉策略

    使用两条不同周期的指数移动平均线(EMA)。
    当快速EMA上穿慢速EMA时产生买入信号（金叉）。
    当快速EMA下穿慢速EMA时产生卖出信号（死叉）。

    参数:
        fast_period: 快速均线周期，默认10
        slow_period: 慢速均线周期，默认30
    """

    # 策略名称
    name = "双均线交叉"

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        """
        初始化双均线策略

        Args:
            fast_period: 快速均线周期
            slow_period: 慢速均线周期

        Raises:
            ValueError: 参数无效时
        """
        if fast_period >= slow_period:
            raise ValueError("快速周期必须小于慢速周期")
        if fast_period < 2:
            raise ValueError("快速周期必须大于等于2")

        self.fast_period = fast_period
        self.slow_period = slow_period

    @property
    def description(self) -> str:
        """策略描述"""
        return (
            f"双均线交叉策略: "
            f"EMA{self.fast_period}上穿EMA{self.slow_period}买入, "
            f"下穿卖出"
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算EMA指标

        Args:
            df: K线数据DataFrame，必须包含close列

        Returns:
            DataFrame: 添加了ema_fast和ema_slow列的DataFrame
        """
        if 'close' not in df.columns:
            raise ValueError("DataFrame必须包含close列")

        result = df.copy()

        # 计算快速EMA
        result['ema_fast'] = df['close'].ewm(
            span=self.fast_period,
            adjust=False
        ).mean()

        # 计算慢速EMA
        result['ema_slow'] = df['close'].ewm(
            span=self.slow_period,
            adjust=False
        ).mean()

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号

        信号规则:
        - 金叉（ema_fast上穿ema_slow）: signal = 1 (买入)
        - 死叉（ema_fast下穿ema_slow）: signal = -1 (卖出)
        - 其他情况: signal = 0 (持有)

        Args:
            df: K线数据DataFrame

        Returns:
            DataFrame: 添加了signal列的DataFrame
        """
        # 计算指标
        result = self.prepare_data(df)

        # 初始化signal列
        result['signal'] = 0

        # 计算交叉状态
        # 当前快线 > 慢线
        fast_above = result['ema_fast'] > result['ema_slow']
        # 上一根快线 <= 慢线
        fast_above_prev = fast_above.shift(1).fillna(False)

        # 金叉: 当前上穿（之前在下方，现在在上方）
        golden_cross = (~fast_above_prev) & fast_above

        # 死叉: 当前下穿（之前在上方，现在在下方）
        death_cross = fast_above_prev & (~fast_above)

        # 生成信号
        result.loc[golden_cross, 'signal'] = 1
        result.loc[death_cross, 'signal'] = -1

        return result

    def get_params(self) -> Dict[str, Any]:
        """
        获取策略参数

        Returns:
            Dict[str, Any]: 策略参数字典
        """
        return {
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
        }

    def validate_params(self) -> bool:
        """
        验证参数有效性

        Returns:
            bool: 参数是否有效
        """
        return (
            2 <= self.fast_period < self.slow_period
            and self.slow_period >= 3
        )
