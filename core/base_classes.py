# core/base_classes.py
"""
核心抽象基类定义

本模块定义了量化交易系统的抽象基类，为数据源、策略等组件提供统一接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
import pandas as pd


class BaseDataSource(ABC):
    """
    数据源抽象基类

    预留扩展接口，支持多种数据源：
    - MT5: MetaTrader5行情数据
    - 加密货币: Binance/OKX等交易所API
    - 其他: 可通过继承扩展

    所有数据源子类需要实现获取K线和Tick数据的统一接口。
    """

    @abstractmethod
    def get_rates(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 交易品种代码，如 "XAUUSD"
            timeframe: 时间周期，如 "M1", "H1", "D1"
            count: 获取的K线数量

        Returns:
            pandas.DataFrame，包含列: time(datetime), open, high, low, close, tick_volume, spread
        """
        pass

    @abstractmethod
    def get_tick(self, symbol: str) -> Dict[str, Any]:
        """
        获取最新Tick数据

        Args:
            symbol: 交易品种代码

        Returns:
            dict包含: bid(买价), ask(卖价), last(最新价), volume(成交量)
        """
        pass


class BaseStrategy(ABC):
    """
    策略抽象基类

    所有交易策略需要继承此类并实现统一的信号生成接口。
    策略接收K线数据，计算技术指标，生成买卖信号。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        策略名称

        Returns:
            str: 策略的唯一标识名称
        """
        pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号

        根据K线数据计算技术指标，生成买卖信号。
        信号定义: 1=买入, -1=卖出, 0=持有/无信号

        Args:
            df: K线数据DataFrame，至少包含: time, open, high, low, close 列

        Returns:
            DataFrame: 添加了signal列的DataFrame，signal列值为 1/-1/0
        """
        pass

    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """
        获取策略参数

        返回当前策略的所有参数配置，用于参数展示和回测配置。

        Returns:
            Dict[str, Any]: 策略参数字典，key为参数名，value为参数值
        """
        pass

    def __repr__(self) -> str:
        """策略的字符串表示"""
        return f"<{self.__class__.__name__} name={self.name}>"
