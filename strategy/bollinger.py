# strategy/bollinger.py
"""
布林带策略

基于布林带的均值回归策略。
当价格触及下轨时买入，触及上轨时卖出。
"""
from typing import Dict, Any
import pandas as pd
from strategy.base_strategy import BaseStrategyEx


class Bollinger(BaseStrategyEx):
    """
    布林带策略

    使用布林带识别价格偏离均线的程度。
    布林带由中轨（移动平均线）、上轨（中轨+N倍标准差）、下轨（中轨-N倍标准差）组成。

    当价格触及或穿越下轨时产生买入信号（超卖）。
    当价格触及或穿越上轨时产生卖出信号（超买）。

    参数:
        period: 移动平均周期，默认20
        num_std: 标准差倍数，默认2.0
    """

    # 策略名称
    name = "布林带"
    description = "基于布林带的均值回归策略，价格触及下轨买入，触及上轨卖出"

    def __init__(self, period: int = 20, num_std: float = 2.0):
        """
        初始化布林带策略

        Args:
            period: 移动平均线和标准差计算周期
            num_std: 标准差倍数，控制带宽

        Raises:
            ValueError: 参数无效时
        """
        if period < 2:
            raise ValueError("周期必须大于等于2")
        if num_std <= 0:
            raise ValueError("标准差倍数必须大于0")

        self.period = period
        self.num_std = num_std

    def _calculate_bollinger_bands(
        self,
        df: pd.DataFrame
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        计算布林带

        Args:
            df: K线数据DataFrame，必须包含close列

        Returns:
            tuple: (中轨, 上轨, 下轨) 的Series元组
        """
        if 'close' not in df.columns:
            raise ValueError("DataFrame必须包含close列")

        close = df['close']

        # 中轨：简单移动平均
        middle = close.rolling(window=self.period).mean()

        # 标准差
        std = close.rolling(window=self.period).std()

        # 上轨：中轨 + N倍标准差
        upper = middle + (std * self.num_std)

        # 下轨：中轨 - N倍标准差
        lower = middle - (std * self.num_std)

        return middle, upper, lower

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算布林带指标

        Args:
            df: K线数据DataFrame，必须包含close列

        Returns:
            DataFrame: 添加了bb_middle, bb_upper, bb_lower列的DataFrame
        """
        result = df.copy()

        middle, upper, lower = self._calculate_bollinger_bands(df)

        result['bb_middle'] = middle
        result['bb_upper'] = upper
        result['bb_lower'] = lower

        # 计算%带宽（可选指标）
        # %B = (价格 - 下轨) / (上轨 - 下轨)
        result['bb_percent'] = (result['close'] - lower) / (upper - lower)

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号

        信号规则:
        - 价格触及或穿越下轨: signal = 1 (买入)
        - 价格触及或穿越上轨: signal = -1 (卖出)
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

        # 获取价格和布林带
        close = result['close']
        lower = result['bb_lower']
        upper = result['bb_upper']

        # 买入信号: 收盘价低于或等于下轨
        buy_signal = close <= lower

        # 卖出信号: 收盘价高于或等于上轨
        sell_signal = close >= upper

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
            'num_std': self.num_std,
        }

    def validate_params(self) -> bool:
        """
        验证参数有效性

        Returns:
            bool: 参数是否有效
        """
        return self.period >= 2 and self.num_std > 0


if __name__ == "__main__":
    # 测试代码
    import numpy as np

    # 创建测试数据
    np.random.seed(42)
    n = 100
    dates = pd.date_range('2024-01-01', periods=n, freq='H')

    # 生成模拟价格数据（带波动）
    close_prices = 2000 + np.cumsum(np.random.randn(n) * 10)

    df = pd.DataFrame({
        'time': dates,
        'open': close_prices + np.random.randn(n) * 2,
        'high': close_prices + np.abs(np.random.randn(n) * 5),
        'low': close_prices - np.abs(np.random.randn(n) * 5),
        'close': close_prices,
    })

    # 创建策略实例
    strategy = Bollinger(period=20, num_std=2.0)

    print("=" * 50)
    print("布林带策略测试")
    print("=" * 50)
    print(f"策略名称: {strategy.name}")
    print(f"策略描述: {strategy.description}")
    print(f"策略参数: {strategy.get_params()}")

    # 生成信号
    result = strategy.generate_signals(df)

    print(f"\n数据形状: {result.shape}")
    print(f"包含列: {list(result.columns)}")

    # 显示最后几行的布林带值
    print("\n最新数据（最后5行）:")
    print(result[['time', 'close', 'bb_middle', 'bb_upper', 'bb_lower']].tail())

    # 显示信号
    signals = result[result['signal'] != 0]
    print(f"\n生成信号数量: {len(signals)}")
    if len(signals) > 0:
        print("\n信号详情:")
        print(signals[['time', 'close', 'bb_lower', 'bb_upper', 'signal']].head())
