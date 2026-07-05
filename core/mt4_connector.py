# core/mt4_connector.py
"""
MT4 连接管理模块

提供 MT4 终端连接的单例管理，通过ZeroMQ与MT4 EA通信。
MT4没有官方Python API，需要配合MT4 EA桥接使用。

使用前需要:
1. 在MT4终端安装并运行 dwx_zmq_bridge.mq4 EA
2. 安装Python ZeroMQ库: pip install pyzmq
3. 确保EA监听的端口与连接器配置一致(默认5555/5556)
"""

import logging
import threading
import json
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime

try:
    import zmq
except ImportError:
    raise ImportError(
        "未安装 pyzmq 库，请运行: pip install pyzmq\n"
        "MT4连接器需要通过ZeroMQ与MT4 EA通信。"
    )

from core.connector_base import (
    BaseConnector,
    AccountInfo,
    PositionInfo,
    SymbolInfo,
    OrderResult,
)

logger = logging.getLogger(__name__)


class MT4Connector(BaseConnector):
    """
    MT4 连接管理器 - 单例模式

    通过ZeroMQ REQ/REP模式与MT4 EA通信，实现BaseConnector接口。

    架构说明:
        Python端(ZMQ REQ) <----> MT4 EA(ZMQ REP)
        - 发送JSON命令
        - 接收JSON响应

    使用前确保MT4 EA已启动并监听配置的端口。
    """

    # MT4时间周期映射 (EA会处理这些常量)
    TIMEFRAME_MAP = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
        "W1": 10080,
        "MN1": 43200,
    }

    _instance: Optional['MT4Connector'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """确保单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        zmq_host: str = "tcp://127.0.0.1:5555",
        push_host: str = "tcp://127.0.0.1:5556",
        timeout: int = 5000,
    ):
        """
        初始化 MT4 连接管理器

        Args:
            zmq_host: ZMQ REQ连接地址，EA的REP socket端口
            push_host: ZMQ SUB连接地址(预留)，EA的PUSH socket端口
            timeout: ZMQ请求超时时间(毫秒)
        """
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._zmq_host = zmq_host
        self._push_host = push_host
        self._timeout = timeout
        self._context = None
        self._socket = None
        self._connected = False
        self._initialized = True

        logger.info(f"MT4连接管理器已创建, ZMQ地址: {zmq_host}")

    def initialize(self) -> bool:
        """
        初始化 MT4 连接

        创建ZMQ上下文和REQ socket，连接到MT4 EA。

        Returns:
            bool: 连接是否成功
        """
        if self._connected:
            logger.debug("MT4 已经连接，跳过初始化")
            return True

        try:
            # 创建ZMQ上下文
            self._context = zmq.Context()

            # 创建REQ socket
            self._socket = self._context.socket(zmq.REQ)
            self._socket.setsockopt(zmq.LINGER, 0)

            # 连接到EA
            self._socket.connect(self._zmq_host)

            # 测试连接 - 发送ping命令
            self._socket.send_json({"action": "ping"})
            poller = zmq.Poller()
            poller.register(self._socket, zmq.POLLIN)

            if poller.poll(self._timeout):
                response = self._socket.recv_json()
                if response.get("status") == "success":
                    self._connected = True
                    logger.info("MT4 连接初始化成功 (ZMQ桥接)")
                    return True
                else:
                    logger.warning(f"MT4 EA返回错误: {response}")
            else:
                logger.error("MT4 EA无响应，请确保EA已启动并监听指定端口")

            self._cleanup()
            return False

        except Exception as e:
            logger.error(f"MT4 初始化异常: {e}", exc_info=True)
            self._cleanup()
            return False

    def shutdown(self):
        """关闭 MT4 连接"""
        self._cleanup()
        logger.info("MT4 连接已关闭")

    def _cleanup(self):
        """清理ZMQ资源"""
        try:
            if self._socket:
                self._socket.close(linger=0)
                self._socket = None
            if self._context:
                self._context.term()
                self._context = None
        except Exception as e:
            logger.error(f"清理ZMQ资源时出错: {e}")
        finally:
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """当前连接状态"""
        return self._connected

    def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送命令到MT4 EA并接收响应

        Args:
            command: 命令字典，必须包含 "action" 字段

        Returns:
            dict: EA响应的JSON数据
        """
        if not self._connected or not self._socket:
            logger.warning("MT4 未连接，无法发送命令")
            return {"status": "error", "message": "未连接"}

        try:
            # 发送命令
            self._socket.send_json(command)

            # 等待响应(带超时)
            poller = zmq.Poller()
            poller.register(self._socket, zmq.POLLIN)

            if poller.poll(self._timeout):
                response = self._socket.recv_json()
                return response
            else:
                logger.error("MT4 EA响应超时")
                return {"status": "error", "message": "响应超时"}

        except zmq.ZMQError as e:
            logger.error(f"ZMQ通信错误: {e}")
            self._connected = False
            return {"status": "error", "message": f"ZMQ错误: {e}"}
        except Exception as e:
            logger.error(f"发送命令异常: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def account_info(self) -> Optional[AccountInfo]:
        """
        获取账户信息

        Returns:
            AccountInfo: 账户信息对象
        """
        response = self._send_command({"action": "account_info"})

        if response.get("status") != "success":
            logger.error(f"获取账户信息失败: {response}")
            return None

        data = response.get("data", {})
        return AccountInfo(
            login=data.get("login", 0),
            server=data.get("server", ""),
            balance=data.get("balance", 0.0),
            equity=data.get("equity", 0.0),
            margin=data.get("margin", 0.0),
            free_margin=data.get("free_margin", 0.0),
            margin_level=data.get("margin_level", 0.0),
            currency=data.get("currency", ""),
            leverage=data.get("leverage", 0),
            profit=data.get("profit", 0.0),
        )

    def copy_rates_from_pos(
        self, symbol: str, timeframe: str, start: int, count: int
    ) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 交易品种代码
            timeframe: 时间周期字符串
            start: 起始位置
            count: 获取数量

        Returns:
            pandas.DataFrame: K线数据
        """
        tf_value = self.TIMEFRAME_MAP.get(timeframe.upper())
        if tf_value is None:
            logger.error(f"不支持的时间周期: {timeframe}")
            return pd.DataFrame()

        response = self._send_command({
            "action": "copy_rates",
            "symbol": symbol,
            "timeframe": tf_value,
            "start": start,
            "count": count,
        })

        if response.get("status") != "success":
            logger.warning(f"获取K线数据失败: {response}")
            return pd.DataFrame()

        rates = response.get("data", [])
        if not rates:
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'])
        return df

    def symbol_info_tick(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        获取品种最新报价

        Args:
            symbol: 交易品种代码

        Returns:
            dict: 包含bid、ask的字典
        """
        response = self._send_command({
            "action": "symbol_info_tick",
            "symbol": symbol,
        })

        if response.get("status") != "success":
            return None

        data = response.get("data", {})
        return {
            "bid": data.get("bid", 0.0),
            "ask": data.get("ask", 0.0),
            "last": data.get("last", 0.0),
            "time": data.get("time", ""),
        }

    def symbols_get(self, pattern: str = "") -> List[str]:
        """
        获取品种列表

        Args:
            pattern: 过滤模式字符串

        Returns:
            list[str]: 品种代码列表
        """
        response = self._send_command({
            "action": "symbols_get",
            "pattern": pattern,
        })

        if response.get("status") != "success":
            return []

        return response.get("data", [])

    def symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """
        获取品种详细信息

        Args:
            symbol: 交易品种代码

        Returns:
            SymbolInfo: 品种详细信息
        """
        response = self._send_command({
            "action": "symbol_info",
            "symbol": symbol,
        })

        if response.get("status") != "success":
            return None

        data = response.get("data", {})
        return SymbolInfo(
            name=data.get("name", symbol),
            point=data.get("point", 0.0),
            digits=data.get("digits", 0),
            volume_min=data.get("volume_min", 0.01),
            volume_max=data.get("volume_max", 100.0),
            volume_step=data.get("volume_step", 0.01),
            contract_size=data.get("contract_size", 100000.0),
            bid=data.get("bid", 0.0),
            ask=data.get("ask", 0.0),
            spread=data.get("spread", 0),
        )

    def order_send(self, request: Dict[str, Any]) -> OrderResult:
        """
        发送交易订单

        Args:
            request: 订单请求字典

        Returns:
            OrderResult: 下单结果
        """
        # 解析订单类型
        type_map = {"BUY": 0, "SELL": 1}  # MT4: 0=BUY, 1=SELL

        order_type_str = request.get("type", "BUY")
        order_type = type_map.get(order_type_str.upper())

        if order_type is None:
            return OrderResult(
                success=False, ticket=0, retcode=-1, comment=f"不支持订单类型: {order_type_str}"
            )

        # 构造EA命令
        ea_request = {
            "action": "order_send",
            "symbol": request.get("symbol", ""),
            "type": order_type,
            "volume": request.get("volume", 0.01),
            "price": request.get("price", 0),
            "sl": request.get("sl", 0),
            "tp": request.get("tp", 0),
            "magic": request.get("magic", 0),
            "comment": request.get("comment", ""),
            "deviation": request.get("deviation", 10),
        }

        response = self._send_command(ea_request)

        if response.get("status") != "success":
            return OrderResult(
                success=False,
                ticket=0,
                retcode=response.get("code", -1),
                comment=response.get("message", "下单失败"),
            )

        return OrderResult(
            success=True,
            ticket=response.get("ticket", 0),
            retcode=0,
            comment=response.get("message", "下单成功"),
        )

    def positions_get(self, symbol: str = None) -> List[PositionInfo]:
        """
        获取持仓列表

        Args:
            symbol: 可选的品种过滤

        Returns:
            list[PositionInfo]: 持仓列表
        """
        command = {"action": "positions_get"}
        if symbol:
            command["symbol"] = symbol

        response = self._send_command(command)

        if response.get("status") != "success":
            return []

        positions = response.get("data", [])
        result = []

        for pos in positions:
            result.append(PositionInfo(
                ticket=pos.get("ticket", 0),
                symbol=pos.get("symbol", ""),
                type=pos.get("type", 0),  # MT4: 0=BUY, 1=SELL
                volume=pos.get("volume", 0.0),
                price_open=pos.get("price_open", 0.0),
                price_current=pos.get("price_current", 0.0),
                sl=pos.get("sl", 0.0),
                tp=pos.get("tp", 0.0),
                profit=pos.get("profit", 0.0),
                comment=pos.get("comment", ""),
            ))

        return result

    def positions_total(self) -> int:
        """
        获取持仓数量

        Returns:
            int: 持仓总数
        """
        response = self._send_command({"action": "positions_total"})

        if response.get("status") != "success":
            return 0

        return response.get("data", 0)

    def __enter__(self):
        """支持上下文管理器协议"""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议"""
        self.shutdown()

    def __repr__(self) -> str:
        return f"<MT4Connector connected={self._connected} zmq={self._zmq_host}>"


# 全局连接器单例
_connector: Optional[MT4Connector] = None
_connector_lock = threading.Lock()


def get_connector(
    zmq_host: str = "tcp://127.0.0.1:5555",
    push_host: str = "tcp://127.0.0.1:5556",
) -> MT4Connector:
    """
    获取 MT4 连接器单例

    Args:
        zmq_host: ZMQ REQ连接地址
        push_host: ZMQ SUB连接地址

    Returns:
        MT4Connector: 全局唯一的连接器实例
    """
    global _connector

    if _connector is None:
        with _connector_lock:
            if _connector is None:
                _connector = MT4Connector(zmq_host=zmq_host, push_host=push_host)
                logger.info("创建全局 MT4 连接器单例")

    return _connector


def reset_connector() -> None:
    """
    重置全局连接器 (主要用于测试)
    """
    global _connector

    with _connector_lock:
        if _connector is not None:
            _connector.shutdown()
            _connector = None
            logger.info("全局 MT4 连接器已重置")
