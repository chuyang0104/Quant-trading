# strategy/rsi_strategy.py
"""
RSI 超买超卖策略

基于相对强弱指数(RSI)的反转策略。
当RSI低于超卖线时买入，高于超买线时卖出。
"""
from typing import Dict, Any
import pandas as pd
from strategy.base_strategy import BaseStrategyEx


class RSI_Strategy(BaseStrategyEx):
    """
    RSI 超买超卖策略

    使用相对强弱指数(RSI)识别超买超卖区域。
    当RSI低于超卖线时产生买入信号。
    当RSI高于超买线时产生卖出信号。

    参数:
        period: RSI周期，默认14
        oversold: 超卖阈值，默认30
        overbought: 超买阈值，默认70
    """

    # 策略名称
    name = "RSI超买超卖"
    description = "基于RSI指标的超买超卖反转策略"

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0
    ):
        """
        初始化RSI策略

        Args:
            period: RSI计算周期
            oversold: 超卖阈值，低于此值产生买入信号
            overbought: 超买阈值，高于此值产生卖出信号

        Raises:
            ValueError: 参数无效时
        """
        if period < 2:
            raise ValueError("RSI周期必须大于等于2")
        if not (0 < oversold < 100):
            raise ValueError("超卖阈值必须在0到100之间")
        if not (0 < overbought < 100):
            raise ValueError("超买阈值必须在0到100之间")
        if oversold >= overbought:
            raise ValueError("超卖阈值必须小于超买阈值")

        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def _calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """
        计算RSI指标

        Args:
            df: K线数据DataFrame，必须包含close列

        Returns:
            Series: RSI值序列
        """
        if 'close' not in df.columns:
            raise ValueError("DataFrame必须包含close列")

        close = df['close']

        # 计算价格变化
        delta = close.diff()

        # 分离上涨和下跌
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # 计算平均涨跌幅（使用Wilder平滑方法）
        avg_gain = gain.ewm(alpha=1 / self.period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.period, adjust=False).mean()

        # 避免除零
        rs = avg_gain / avg_loss.replace(0, float('inf'))

        # 计算RSI
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算RSI指标

        Args:
            df: K线数据DataFrame，必须包含close列

        Returns:
            DataFrame: 添加了rsi列的DataFrame
        """
        result = df.copy()
        result['rsi'] = self._calculate_rsi(df)
        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号

        信号规则:
        - RSI从超卖区域向上穿越: signal = 1 (买入)
        - RSI从超买区域向下穿越: signal = -1 (卖出)
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

        # 获取RSI序列
        rsi = result['rsi']

        # 上一根K线的RSI
        rsi_prev = rsi.shift(1)

        # 买入信号: RSI从超卖区域向上穿越（上一根低于超卖线，当前高于或等于）
        buy_signal = (rsi_prev < self.oversold) & (rsi >= self.oversold)

        # 卖出信号: RSI从超买区域向下穿越（上一根高于超买线，当前低于或等于）
        sell_signal = (rsi_prev > self.overbought) & (rsi <= self.overbought)

        # 生成信号
        result.loc[buy_signal, 'signal'] = 1
        result.loc[sell_signal, 'signal'] = -1

        return result

    def get_params(self) -> Dict[str, Any]:
        """
        获取策略参数

        Returns:
            Dict[str, Any]: 策略参数字典
        """
        return {
            'period': self.period,
            'oversold': self.oversold,
            'overbought': self.overbought,
        }

    def validate_params(self) -> bool:
        """
        验证参数有效性

        Returns:
            bool: 参数是否有效
        """
        return (
            self.period >= 2
            and 0 < self.oversold < 100
            and 0 < self.overbought < 100
            and self.oversold < self.overbought
        )


if __name__ == "__main__":
    # 测试代码
    import numpy as np

    # 创建测试数据
    np.random.seed(42)
    n = 100
    dates = pd.date_range('2024-01-01', periods=n, freq='H')

    # 生成模拟价格数据
    close_prices = 2000 + np.cumsum(np.random.randn(n) * 10)

    df = pd.DataFrame({
        'time': dates,
        'open': close_prices + np.random.randn(n) * 2,
        'high': close_prices + np.abs(np.random.randn(n) * 5),
        'low': close_prices - np.abs(np.random.randn(n) * 5),
        'close': close_prices,
    })

    # 创建策略实例
    strategy = RSI_Strategy(period=14, oversold=30, overbought=70)

    print("=" * 50)
    print("RSI 策略测试")
    print("=" * 50)
    print(f"策略名称: {strategy.name}")
    print(f"策略描述: {strategy.description}")
    print(f"策略参数: {strategy.get_params()}")

    # 生成信号
    result = strategy.generate_signals(df)

    print(f"\n数据形状: {result.shape}")
    print(f"包含列: {list(result.columns)}")

    # 显示信号
    signals = result[result['signal'] != 0]
    print(f"\n生成信号数量: {len(signals)}")
    if len(signals) > 0:
        print("\n信号详情:")
        print(signals[['time', 'close', 'rsi', 'signal']].head())
