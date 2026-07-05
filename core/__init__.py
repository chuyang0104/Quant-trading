# core/__init__.py
"""核心模块"""

from .base_classes import BaseDataSource, BaseStrategy
from .connector_base import BaseConnector, AccountInfo, PositionInfo, SymbolInfo, OrderResult
from .connector_factory import create_connector
from .mt5_connector import MT5Connector
from .mt4_connector import MT4Connector

__all__ = [
    'BaseDataSource',
    'BaseStrategy',
    'BaseConnector',
    'AccountInfo',
    'PositionInfo',
    'SymbolInfo',
    'OrderResult',
    'create_connector',
    'MT5Connector',
    'MT4Connector',
]
