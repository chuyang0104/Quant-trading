# core/connector_factory.py
"""
交易平台连接器工厂

根据配置创建对应的平台连接器实例，支持:
- MT5: MetaTrader 5
- MT4: MetaTrader 4
- 未来扩展: 加密货币交易所

使用示例:
    # 创建MT5连接器
    connector = create_connector("mt5", path="...")

    # 创建MT4连接器
    connector = create_connector("mt4", zmq_host="tcp://127.0.0.1:5555")

    # 统一使用BaseConnector接口
    if connector.initialize():
        account = connector.account_info()
"""

import logging
from typing import Optional
from core.connector_base import BaseConnector

logger = logging.getLogger(__name__)


def create_connector(platform: str = "mt5", **kwargs) -> BaseConnector:
    """
    创建交易平台连接器

    工厂模式，根据平台类型创建对应的连接器实例。
    所有连接器都实现BaseConnector接口，可以统一使用。

    Args:
        platform: 平台类型，支持:
            - "mt5": MetaTrader 5
            - "mt4": MetaTrader 4
        **kwargs: 平台特定的参数:
            MT5参数:
                - path: MT5 terminal64.exe的完整路径(可选)
            MT4参数:
                - zmq_host: ZMQ连接地址(默认tcp://127.0.0.1:5555)
                - push_host: ZMQ推送地址(默认tcp://127.0.0.1:5556)
                - timeout: ZMQ超时毫秒(默认5000)

    Returns:
        BaseConnector: 连接器实例

    Raises:
        ValueError: 不支持的平台类型

    Examples:
        >>> # MT5连接器
        >>> conn = create_connector("mt5", path=r"C:\\MT5\\terminal64.exe")
        >>>
        >>> # MT4连接器
        >>> conn = create_connector("mt4", zmq_host="tcp://127.0.0.1:5555")
        >>>
        >>> # 统一使用
        >>> if conn.initialize():
        ...     account = conn.account_info()
        ...     print(f"账户: {account.login}")
        ...     conn.shutdown()
    """
    platform_lower = platform.lower()

    if platform_lower == "mt5":
        from core.mt5_connector import MT5Connector
        path = kwargs.get("path")
        logger.info(f"创建 MT5 连接器, 路径: {path or '默认'}")
        return MT5Connector(path=path)

    elif platform_lower == "mt4":
        from core.mt4_connector import MT4Connector
        zmq_host = kwargs.get("zmq_host", "tcp://127.0.0.1:5555")
        push_host = kwargs.get("push_host", "tcp://127.0.0.1:5556")
        timeout = kwargs.get("timeout", 5000)
        logger.info(f"创建 MT4 连接器, ZMQ: {zmq_host}")
        return MT4Connector(zmq_host=zmq_host, push_host=push_host, timeout=timeout)

    else:
        supported = ["mt5", "mt4"]
        raise ValueError(
            f"不支持的平台: {platform}。支持的平台: {', '.join(supported)}"
        )


# 便捷的单例获取函数
_connector_cache = {}


def get_cached_connector(platform: str = "mt5", **kwargs) -> BaseConnector:
    """
    获取缓存的连接器实例

    对于相同配置的平台，返回已创建的连接器实例(单例模式)。

    Args:
        platform: 平台类型
        **kwargs: 平台参数

    Returns:
        BaseConnector: 连接器实例
    """
    cache_key = (platform, str(sorted(kwargs.items())))

    if cache_key not in _connector_cache:
        _connector_cache[cache_key] = create_connector(platform, **kwargs)

    return _connector_cache[cache_key]


def clear_cache():
    """
    清除连接器缓存

    关闭所有缓存的连接器并清空缓存。
    """
    for connector in _connector_cache.values():
        try:
            if hasattr(connector, 'shutdown'):
                connector.shutdown()
        except Exception:
            pass

    _connector_cache.clear()
