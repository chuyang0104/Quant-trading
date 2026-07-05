# strategy/base_strategy.py
"""
策略基类扩展

扩展核心BaseStrategy类，提供策略通用功能。
所有具体策略应继承此类。
"""
from abc import abstractmethod
from typing import Dict, Any
import pandas as pd
from core.base_classes import BaseStrategy


class BaseStrategyEx(BaseStrategy):
    """
    策略基类扩展

    在 BaseStrategy 基础上添加更多实用方法，提供策略开发的基础框架。

    子类需要实现:
    - name 属性（策略名称）
    - description 属性（策略描述）
    - calculate_indicators 方法（计算技术指标，抽象方法）
    - generate_signals 方法（生成交易信号）
    - get_params 方法（获取策略参数）

    属性:
        name: 策略名称，子类必须定义为类属性
        description: 策略描述，子类可以覆盖
    """

    # 子类必须设置这些类属性
    name: str = "未命名策略"
    description: str = "暂无描述"

    @abstractmethod
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标（子类必须实现）

        子类在此方法中实现自定义技术指标的计算逻辑。
        计算出的指标将添加到 DataFrame 中供信号生成使用。

        Args:
            df: K线数据DataFrame，至少包含: time, open, high, low, close 列

        Returns:
            DataFrame: 添加了指标列的DataFrame
        """
        pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号（子类必须实现）

        根据K线数据和技术指标生成买卖信号。
        信号定义: 1=买入, -1=卖出, 0=持有/无信号

        Args:
            df: K线数据DataFrame

        Returns:
            DataFrame: 添加了signal列的DataFrame
        """
        pass

    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """
        获取策略参数（子类必须实现）

        Returns:
            Dict[str, Any]: 策略参数字典
        """
        pass

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        准备数据

        在生成信号前对数据进行预处理，包括计算指标等。

        Args:
            df: K线数据DataFrame

        Returns:
            DataFrame: 处理后的DataFrame，包含所需指标
        """
        # 调用子类实现的指标计算
        return self.calculate_indicators(df)

    def validate_params(self) -> bool:
        """
        验证策略参数有效性（可选实现）

        子类可重写此方法添加参数校验逻辑。

        Returns:
            bool: 参数是否有效
        """
        return True

    def __str__(self) -> str:
        """字符串表示"""
        params = self.get_params()
        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
        return f"{self.name}({param_str})"

    def __repr__(self) -> str:
        """对象表示"""
        return f"<{self.__class__.__name__} name='{self.name}'>"
