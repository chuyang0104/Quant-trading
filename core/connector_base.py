# core/connector_base.py
"""
交易平台连接器抽象基类

本模块定义了量化交易系统与不同交易平台(MT4/MT5/加密货币)通信的统一接口。
所有平台连接器都必须实现此接口，确保上层代码可以无缝切换平台。

支持的平台:
- MT5: MetaTrader 5 (官方Python库)
- MT4: MetaTrader 4 (通过ZeroMQ桥接)
- 未来扩展: Binance, OKX等加密货币交易所
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import pandas as pd
from datetime import datetime


@dataclass
class AccountInfo:
    """
    统一的账户信息数据类

    所有平台连接器返回的账户信息都应使用此格式，确保上层代码一致处理。

    Attributes:
        login: 账户号码
        server: 交易服务器名称
        balance: 账户余额
        equity: 账户净值(余额+浮动盈亏)
        margin: 已用保证金
        free_margin: 可用保证金
        margin_level: 保证金水平百分比
        currency: 账户基础货币
        leverage: 杠杆倍数
        profit: 当前浮动盈亏
    """
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    currency: str
    leverage: int
    profit: float

    def __repr__(self) -> str:
        return f"<AccountInfo #{self.login} {self.server} balance={self.balance} {self.currency}>"


@dataclass
class PositionInfo:
    """
    统一的持仓信息数据类

    所有平台连接器返回的持仓信息都应使用此格式。

    Attributes:
        ticket: 持仓单号(唯一标识)
        symbol: 交易品种代码
        type: 持仓方向，0=买入/多头，1=卖出/空头
        volume: 持仓手数
        price_open: 开仓价格
        price_current: 当前价格
        sl: 止损价格
        tp: 止盈价格
        profit: 当前浮动盈亏
        comment: 订单注释
    """
    ticket: int
    symbol: str
    type: int  # 0=买入, 1=卖出
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    comment: str

    def __repr__(self) -> str:
        direction = "BUY" if self.type == 0 else "SELL"
        return f"<PositionInfo #{self.ticket} {self.symbol} {direction} {self.volume} lots profit={self.profit}>"


@dataclass
class SymbolInfo:
    """
    统一的品种信息数据类

    所有平台连接器返回的品种信息都应使用此格式。

    Attributes:
        name: 品种代码
        point: 最小价格变动单位
        digits: 价格小数位数
        volume_min: 最小下单手数
        volume_max: 最大下单手数
        volume_step: 手数步长(增量)
        contract_size: 合约大小(1手的基准货币数量)
        bid: 当前买价
        ask: 当前卖价
        spread: 点差(points)
    """
    name: str
    point: float
    digits: int
    volume_min: float
    volume_max: float
    volume_step: float
    contract_size: float
    bid: float
    ask: float
    spread: int

    def __repr__(self) -> str:
        return f"<SymbolInfo {self.name} bid={self.bid} ask={self.ask} spread={self.spread}>"


@dataclass
class OrderResult:
    """
    统一的下单结果数据类

    所有平台连接器返回的下单结果都应使用此格式。

    Attributes:
        success: 下单是否成功
        ticket: 成功时的订单号，失败时为0
        retcode: 返回码，0表示成功
        comment: 结果描述信息
    """
    success: bool
    ticket: int
    retcode: int
    comment: str

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"<OrderResult {status} ticket={self.ticket} code={self.retcode} '{self.comment}'>"


class BaseConnector(ABC):
    """
    交易平台连接器抽象基类

    定义了所有交易平台必须实现的统一接口。子类需要实现所有抽象方法。
    此设计使得策略、风控、监控等上层模块可以无缝切换不同交易平台。

    抽象方法说明:
        - initialize(): 初始化与平台的连接
        - shutdown(): 关闭连接，释放资源
        - is_connected: 当前连接状态
        - account_info(): 获取账户信息
        - copy_rates_from_pos(): 获取K线数据
        - symbol_info_tick(): 获取品种最新报价
        - symbols_get(): 获取品种列表
        - symbol_info(): 获取品种详细信息
        - order_send(): 发送交易订单
        - positions_get(): 获取持仓列表
        - positions_total(): 获取持仓数量

    使用示例:
        >>> connector = create_connector("mt5", path="...")
        >>> if connector.initialize():
        ...     account = connector.account_info()
        ...     print(f"余额: {account.balance}")
        ...     connector.shutdown()
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化与交易平台的连接

        建立与MT4/MT5终端或交易所API的连接，进行必要的认证和握手。

        Returns:
            bool: 连接是否成功，True表示成功，False表示失败
        """
        pass

    @abstractmethod
    def shutdown(self):
        """
        关闭与交易平台的连接

        释放资源，断开与平台终端或API的连接。
        建议在程序退出前调用此方法进行优雅关闭。
        """
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        当前连接状态

        Returns:
            bool: 是否已连接到交易平台
        """
        pass

    @abstractmethod
    def account_info(self) -> Optional[AccountInfo]:
        """
        获取账户信息

        获取当前交易账户的详细信息，包括余额、净值、保证金等。

        Returns:
            AccountInfo: 账户信息对象，连接失败时返回None
        """
        pass

    @abstractmethod
    def copy_rates_from_pos(
        self, symbol: str, timeframe: str, start: int, count: int
    ) -> pd.DataFrame:
        """
        获取K线数据

        从指定位置开始获取指定数量的K线(蜡烛图)数据。

        Args:
            symbol: 交易品种代码，如 "XAUUSD", "EURUSD"
            timeframe: 时间周期字符串，如 "M1", "M5", "H1", "H4", "D1"
            start: 起始位置，0表示最新K线，正数向历史方向偏移
            count: 获取K线的数量

        Returns:
            pandas.DataFrame: K线数据，包含以下列:
                - time: 时间(datetime)
                - open: 开盘价
                - high: 最高价
                - low: 最低价
                - close: 收盘价
                - tick_volume: 成交量
                - spread: 点差
        """
        pass

    @abstractmethod
    def symbol_info_tick(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        获取品种最新报价(Tick)

        获取指定品种当前的买价、卖价等报价信息。

        Args:
            symbol: 交易品种代码

        Returns:
            dict: 包含bid(买价)、ask(卖价)、last(最新价)、time(时间)的字典
                  获取失败时返回None
        """
        pass

    @abstractmethod
    def symbols_get(self, pattern: str = "") -> List[str]:
        """
        获取品种列表

        获取交易平台中可交易品种的代码列表。

        Args:
            pattern: 过滤模式字符串，支持通配符(*)，空字符串表示获取所有品种

        Returns:
            list[str]: 品种代码列表，如 ["XAUUSD", "EURUSD", "GBPUSD"]
        """
        pass

    @abstractmethod
    def symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """
        获取品种详细信息

        获取指定品种的交易规则、手数限制等详细信息。

        Args:
            symbol: 交易品种代码

        Returns:
            SymbolInfo: 品种详细信息对象，品种不存在时返回None
        """
        pass

    @abstractmethod
    def order_send(self, request: Dict[str, Any]) -> OrderResult:
        """
        发送交易订单

        执行市价单或挂单交易请求。

        Args:
            request: 订单请求字典，统一格式包含:
                - action: "DEAL"(市价单) 或 "PENDING"(挂单)
                - symbol: 交易品种代码
                - type: "BUY" 或 "SELL"
                - volume: 下单手数
                - price: 下单价格(挂单必需)
                - sl: 止损价格
                - tp: 止盈价格
                - deviation: 最大滑点(点数)
                - magic: EA魔术编号
                - comment: 订单注释

        Returns:
            OrderResult: 下单结果对象，包含成功状态、订单号等
        """
        pass

    @abstractmethod
    def positions_get(self, symbol: str = None) -> List[PositionInfo]:
        """
        获取持仓列表

        获取当前所有持仓或指定品种的持仓信息。

        Args:
            symbol: 可选的品种过滤条件，None表示获取所有品种的持仓

        Returns:
            list[PositionInfo]: 持仓信息列表，无持仓时返回空列表
        """
        pass

    @abstractmethod
    def positions_total(self) -> int:
        """
        获取持仓数量

        Returns:
            int: 当前持仓总数
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} connected={self.is_connected}>"


# 便捷的时间框架常量映射
TIMEFRAME_CONSTANTS = {
    "M1": 1,      # 1分钟
    "M5": 5,      # 5分钟
    "M15": 15,    # 15分钟
    "M30": 30,    # 30分钟
    "H1": 60,     # 1小时
    "H4": 240,    # 4小时
    "D1": 1440,   # 日线
    "W1": 10080,  # 周线
    "MN1": 43200, # 月线
}
