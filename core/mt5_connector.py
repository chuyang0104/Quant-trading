# core/mt5_connector.py
"""
MT5 连接管理模块

提供 MT5 终端连接的单例管理，支持:
- 自动初始化和连接
- 连接状态检查和自动重连
- 优雅关闭
- 实现BaseConnector统一接口
"""

import logging
import threading
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    raise ImportError(
        "未安装 MetaTrader5 库，请运行: pip install MetaTrader5"
    )

from core.connector_base import (
    BaseConnector,
    AccountInfo,
    PositionInfo,
    SymbolInfo,
    OrderResult,
    TIMEFRAME_CONSTANTS
)

logger = logging.getLogger(__name__)


class MT5Connector(BaseConnector):
    """
    MT5 连接管理器 - 单例模式

    负责与 MT5 终端的连接管理，实现BaseConnector接口，提供:
    - 连接初始化
    - 连接状态检查
    - 自动重连
    - 优雅关闭
    - 统一的数据获取接口
    """

    # MT5时间周期常量映射
    TIMEFRAME_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }

    # 订单类型映射
    ORDER_TYPE_MAP = {
        "BUY": mt5.ORDER_TYPE_BUY,
        "SELL": mt5.ORDER_TYPE_SELL,
    }

    _instance: Optional['MT5Connector'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """确保单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, path: Optional[str] = None):
        """
        初始化 MT5 连接管理器

        Args:
            path: MT5 terminal64.exe 的完整路径
        """
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._path = path
        self._connected = False
        self._initialized = True
        logger.info(f"MT5连接管理器已创建, 路径: {path or '默认'}")

    def initialize(self) -> bool:
        """
        初始化 MT5 连接

        Returns:
            bool: 连接是否成功
        """
        if self._connected:
            logger.debug("MT5 已经连接，跳过初始化")
            return True

        try:
            # 调用 MT5 初始化
            if self._path:
                result = mt5.initialize(path=self._path)
            else:
                result = mt5.initialize()

            if not result:
                error_code = mt5.last_error()
                logger.error(f"MT5 初始化失败: {error_code}")
                self._connected = False
                return False

            self._connected = True
            logger.info("MT5 连接初始化成功")

            # 打印 MT5 版本信息
            version_info = mt5.version()
            logger.info(
                f"MT5 版本: {version_info.build} "
                f"(发布于 {version_info.date})"
            )

            return True

        except Exception as e:
            logger.error(f"MT5 初始化异常: {e}", exc_info=True)
            self._connected = False
            return False

    def ensure_connected(self) -> bool:
        """
        确保连接状态，断线时自动重连

        Returns:
            bool: 当前是否已连接
        """
        if not self._connected:
            logger.warning("检测到 MT5 未连接，尝试重新连接...")
            return self.initialize()

        # 验证连接是否仍然有效
        try:
            # 尝试获取账户信息来验证连接
            account = mt5.account_info()
            if account is None:
                self._connected = False
                logger.warning("MT5 连接已断开，尝试重新连接...")
                return self.initialize()
        except Exception as e:
            self._connected = False
            logger.error(f"验证连接状态时出错: {e}")
            return self.initialize()

        return True

    def shutdown(self):
        """
        关闭 MT5 连接

        Returns:
            bool: 关闭是否成功
        """
        try:
            if self._connected:
                mt5.shutdown()
                self._connected = False
                logger.info("MT5 连接已关闭")
            else:
                logger.debug("MT5 未连接，无需关闭")
        except Exception as e:
            logger.error(f"关闭 MT5 连接时出错: {e}", exc_info=True)

    @property
    def is_connected(self) -> bool:
        """
        当前连接状态

        Returns:
            bool: 是否已连接
        """
        return self._connected

    def account_info(self) -> Optional[AccountInfo]:
        """
        获取账户信息

        Returns:
            AccountInfo: 账户信息对象，连接失败时返回None
        """
        if not self.ensure_connected():
            logger.warning("MT5 未连接，无法获取账户信息")
            return None

        try:
            info = mt5.account_info()
            if info is None:
                logger.error("获取账户信息失败")
                return None

            return AccountInfo(
                login=info.login,
                server=info.server,
                balance=info.balance,
                equity=info.equity,
                margin=info.margin,
                free_margin=info.margin_free,
                margin_level=info.margin_level,
                currency=info.currency,
                leverage=info.leverage,
                profit=info.profit,
            )
        except Exception as e:
            logger.error(f"获取账户信息异常: {e}", exc_info=True)
            return None

    def copy_rates_from_pos(
        self, symbol: str, timeframe: str, start: int, count: int
    ) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 交易品种代码，如 "XAUUSD"
            timeframe: 时间周期字符串，如 "M1", "H1", "D1"
            start: 起始位置，0表示最新K线
            count: 获取K线的数量

        Returns:
            pandas.DataFrame: K线数据
        """
        if not self.ensure_connected():
            logger.warning("MT5 未连接，无法获取K线数据")
            return pd.DataFrame()

        try:
            # 映射时间周期字符串到MT5常量
            mt5_timeframe = self.TIMEFRAME_MAP.get(timeframe.upper())
            if mt5_timeframe is None:
                logger.error(f"不支持的时间周期: {timeframe}")
                return pd.DataFrame()

            # 获取K线数据
            rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, start, count)
            if rates is None or len(rates) == 0:
                logger.warning(f"获取 {symbol} {timeframe} K线数据为空")
                return pd.DataFrame()

            # 转换为DataFrame
            df = pd.DataFrame(rates)

            # 转换时间戳为datetime
            df['time'] = pd.to_datetime(df['time'], unit='s')

            return df

        except Exception as e:
            logger.error(f"获取K线数据异常: {e}", exc_info=True)
            return pd.DataFrame()

    def symbol_info_tick(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        获取品种最新报价

        Args:
            symbol: 交易品种代码

        Returns:
            dict: 包含bid、ask、last、time的字典，失败时返回None
        """
        if not self.ensure_connected():
            logger.warning("MT5 未连接，无法获取报价")
            return None

        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning(f"获取 {symbol} 报价失败")
                return None

            return {
                "bid": tick.bid,
                "ask": tick.ask,
                "last": tick.last,
                "time": datetime.fromtimestamp(tick.time),
            }
        except Exception as e:
            logger.error(f"获取报价异常: {e}", exc_info=True)
            return None

    def symbols_get(self, pattern: str = "") -> List[str]:
        """
        获取品种列表

        Args:
            pattern: 过滤模式字符串，支持通配符

        Returns:
            list[str]: 品种代码列表
        """
        if not self.ensure_connected():
            logger.warning("MT5 未连接，无法获取品种列表")
            return []

        try:
            symbols = mt5.symbols_get(pattern)
            if symbols is None:
                return []

            return [s.name for s in symbols]
        except Exception as e:
            logger.error(f"获取品种列表异常: {e}", exc_info=True)
            return []

    def symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """
        获取品种详细信息

        Args:
            symbol: 交易品种代码

        Returns:
            SymbolInfo: 品种详细信息对象
        """
        if not self.ensure_connected():
            logger.warning("MT5 未连接，无法获取品种信息")
            return None

        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                logger.warning(f"品种 {symbol} 不存在")
                return None

            tick = mt5.symbol_info_tick(symbol)
            bid = tick.bid if tick else 0
            ask = tick.ask if tick else 0
            spread = int((ask - bid) / info.point) if (ask > 0 and bid > 0) else 0

            return SymbolInfo(
                name=info.name,
                point=info.point,
                digits=info.digits,
                volume_min=info.volume_min,
                volume_max=info.volume_max,
                volume_step=info.volume_step,
                contract_size=info.contract_size,
                bid=bid,
                ask=ask,
                spread=spread,
            )
        except Exception as e:
            logger.error(f"获取品种信息异常: {e}", exc_info=True)
            return None

    def order_send(self, request: Dict[str, Any]) -> OrderResult:
        """
        发送交易订单

        Args:
            request: 订单请求字典

        Returns:
            OrderResult: 下单结果对象
        """
        if not self.ensure_connected():
            logger.warning("MT5 未连接，无法下单")
            return OrderResult(success=False, ticket=0, retcode=-1, comment="MT5 未连接")

        try:
            # 解析统一格式的请求
            action = request.get("action", "DEAL")
            symbol = request.get("symbol")
            order_type_str = request.get("type", "BUY")
            volume = request.get("volume", 0.01)
            price = request.get("price", 0)
            sl = request.get("sl", 0)
            tp = request.get("tp", 0)
            deviation = request.get("deviation", 10)
            magic = request.get("magic", 0)
            comment = request.get("comment", "")

            if not symbol:
                return OrderResult(success=False, ticket=0, retcode=-1, comment="缺少品种代码")

            # 映射订单类型
            order_type = self.ORDER_TYPE_MAP.get(order_type_str.upper())
            if order_type is None:
                return OrderResult(success=False, ticket=0, retcode=-1, comment=f"不支持订单类型: {order_type_str}")

            # 获取品种信息
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return OrderResult(success=False, ticket=0, retcode=-1, comment=f"品种 {symbol} 不存在")

            # 构造MT5订单请求
            mt5_request = {
                "action": mt5.TRADE_ACTION_DEAL if action == "DEAL" else mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": deviation,
                "magic": magic,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # 发送订单
            result = mt5.order_send(mt5_request)

            if result is None:
                error = mt5.last_error()
                return OrderResult(success=False, ticket=0, retcode=error[0], comment=error[1])

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return OrderResult(
                    success=True,
                    ticket=result.order,
                    retcode=result.retcode,
                    comment="下单成功"
                )
            else:
                return OrderResult(
                    success=False,
                    ticket=result.order if result.order else 0,
                    retcode=result.retcode,
                    comment=result.comment or "下单失败"
                )

        except Exception as e:
            logger.error(f"下单异常: {e}", exc_info=True)
            return OrderResult(success=False, ticket=0, retcode=-1, comment=str(e))

    def positions_get(self, symbol: str = None) -> List[PositionInfo]:
        """
        获取持仓列表

        Args:
            symbol: 可选的品种过滤条件

        Returns:
            list[PositionInfo]: 持仓信息列表
        """
        if not self.ensure_connected():
            logger.warning("MT5 未连接，无法获取持仓")
            return []

        try:
            positions = mt5.positions_get(symbol=symbol)
            if positions is None or len(positions) == 0:
                return []

            result = []
            for pos in positions:
                result.append(PositionInfo(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    type=pos.type,  # 0=买入, 1=卖出
                    volume=pos.volume,
                    price_open=pos.price_open,
                    price_current=pos.price_current,
                    sl=pos.sl,
                    tp=pos.tp,
                    profit=pos.profit,
                    comment=pos.comment,
                ))

            return result

        except Exception as e:
            logger.error(f"获取持仓异常: {e}", exc_info=True)
            return []

    def positions_total(self) -> int:
        """
        获取持仓数量

        Returns:
            int: 当前持仓总数
        """
        if not self.ensure_connected():
            return 0

        try:
            return mt5.positions_total() or 0
        except Exception as e:
            logger.error(f"获取持仓数量异常: {e}", exc_info=True)
            return 0

    def __enter__(self):
        """支持上下文管理器协议"""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议"""
        self.shutdown()

    def __repr__(self) -> str:
        return f"<MT5Connector connected={self._connected} path={self._path}>"


# 全局连接器单例
_connector: Optional[MT5Connector] = None
_connector_lock = threading.Lock()


def get_connector(path: Optional[str] = None) -> MT5Connector:
    """
    获取 MT5 连接器单例

    Args:
        path: MT5 terminal64.exe 的完整路径 (首次调用时有效)

    Returns:
        MT5Connector: 全局唯一的连接器实例
    """
    global _connector

    if _connector is None:
        with _connector_lock:
            if _connector is None:
                _connector = MT5Connector(path=path)
                logger.info("创建全局 MT5 连接器单例")

    return _connector


def reset_connector() -> None:
    """
    重置全局连接器 (主要用于测试)

    注意: 会先关闭现有连接
    """
    global _connector

    with _connector_lock:
        if _connector is not None:
            _connector.shutdown()
            _connector = None
            logger.info("全局 MT5 连接器已重置")


if __name__ == "__main__":
    # 配置日志用于测试
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 50)
    print("MT5 连接器测试")
    print("=" * 50)

    # 使用上下文管理器
    with MT5Connector(path=r"D:\交易盘\DLSM MT5\terminal64.exe") as conn:
        print(f"连接状态: {conn.is_connected}")
        if conn.is_connected:
            # 获取账户信息
            account = conn.account_info()
            if account:
                print(f"账户: #{account.login}")
                print(f"服务器: {account.server}")
                print(f"余额: {account.balance}")
                print(f"净值: {account.equity}")
