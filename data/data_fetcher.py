# data/data_fetcher.py
"""
行情数据获取模块

通过统一的平台连接器(BaseConnector)获取行情数据，支持:
- MT5: MetaTrader 5
- MT4: MetaTrader 4 (通过ZeroMQ桥接)

提供:
- K线数据 (OHLCV)
- Tick 数据 (实时报价)
- 品种信息 (交易规则)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core.base_classes import BaseDataSource
from core.connector_base import BaseConnector
from core.connector_factory import create_connector

logger = logging.getLogger(__name__)


class DataFetcher(BaseDataSource):
    """
    行情数据获取器

    通过平台连接器获取K线、Tick和品种信息。
    自动适配MT4/MT5，调用方无需关心底层平台差异。

    所有方法在调用前会自动检查并确保连接器已连接。
    """

    # 支持的时间周期
    SUPPORTED_TIMEFRAMES = [
        "M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"
    ]

    def __init__(self, connector: Optional[BaseConnector] = None):
        """
        初始化数据获取器

        Args:
            connector: 平台连接器实例(BaseConnector)。
                      为None时根据config.settings.platform自动创建。
        """
        if connector is not None:
            self._connector = connector
        else:
            # 根据配置自动创建连接器
            from config.settings import settings
            platform = settings.platform
            if platform == "mt5":
                self._connector = create_connector("mt5", path=settings.mt5_path)
            elif platform == "mt4":
                self._connector = create_connector(
                    "mt4",
                    zmq_host=settings.mt4_zmq_host,
                    push_host=settings.mt4_zmq_push_host,
                )
            else:
                raise ValueError(f"不支持的平台: {platform}")

        logger.info(f"DataFetcher 初始化完成, 平台: {self.__class__.__name__}")

    def _ensure_connection(self) -> bool:
        """
        确保平台连接状态

        Returns:
            bool: 连接是否正常
        """
        if not self._connector.is_connected:
            logger.info("连接器未连接，尝试初始化...")
            return self._connector.initialize()
        return True

    def _validate_timeframe(self, timeframe: str) -> str:
        """
        验证时间周期是否有效

        Args:
            timeframe: 时间周期字符串，如 "M1", "H1", "D1"

        Returns:
            str: 大写的时间周期字符串

        Raises:
            ValueError: 不支持的时间周期
        """
        timeframe_upper = timeframe.upper()
        if timeframe_upper not in self.SUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"不支持的时间周期: {timeframe}，"
                f"支持的周期: {self.SUPPORTED_TIMEFRAMES}"
            )
        return timeframe_upper

    def get_rates(
        self,
        symbol: str,
        timeframe: str,
        count: int = 500
    ) -> pd.DataFrame:
        """
        获取K线数据（从最新位置开始获取指定数量）

        Args:
            symbol: 交易品种代码，如 "XAUUSD"
            timeframe: 时间周期，如 "M1", "H1", "D1"
            count: 获取的K线数量

        Returns:
            pandas.DataFrame，包含列:
            - time: datetime 格式的时间戳
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - tick_volume: 成交量
            - spread: 点差

        Raises:
            ConnectionError: 平台未连接
            ValueError: 获取数据失败
        """
        if not self._ensure_connection():
            raise ConnectionError("平台未连接，无法获取数据")

        tf = self._validate_timeframe(timeframe)

        try:
            df = self._connector.copy_rates_from_pos(symbol, tf, 0, count)

            if df is None or df.empty:
                logger.warning(
                    f"未获取到数据，品种={symbol}, 周期={timeframe}"
                )
                return pd.DataFrame()

            logger.debug(
                f"获取K线数据成功: {symbol} {timeframe}, "
                f"数量={len(df)}, 时间范围={df['time'].min()} ~ {df['time'].max()}"
            )

            return df

        except Exception as e:
            logger.error(f"获取K线数据失败: {e}", exc_info=True)
            raise

    def get_rates_range(
        self,
        symbol: str,
        timeframe: str,
        start_dt: datetime,
        end_dt: datetime
    ) -> pd.DataFrame:
        """
        获取指定时间范围的K线数据

        注意: 此方法依赖连接器实现copy_rates_range。
        如果连接器不支持，将回退到获取大量数据后过滤。

        Args:
            symbol: 交易品种代码
            timeframe: 时间周期
            start_dt: 起始时间
            end_dt: 结束时间

        Returns:
            pandas.DataFrame: K线数据，格式同 get_rates()
        """
        if not self._ensure_connection():
            raise ConnectionError("平台未连接，无法获取数据")

        tf = self._validate_timeframe(timeframe)

        try:
            # 尝试调用连接器的copy_rates_range（如果支持）
            if hasattr(self._connector, 'copy_rates_range'):
                df = self._connector.copy_rates_range(
                    symbol, tf, start_dt, end_dt
                )
            else:
                # 回退方案: 获取大量数据后按时间过滤
                # 估算需要的bar数（保守估计）
                df = self._connector.copy_rates_from_pos(symbol, tf, 0, 5000)
                if df is not None and not df.empty:
                    df = df[(df['time'] >= start_dt) & (df['time'] <= end_dt)]

            if df is None or df.empty:
                logger.warning(
                    f"未获取到数据，品种={symbol}, 周期={timeframe}, "
                    f"时间范围={start_dt} ~ {end_dt}"
                )
                return pd.DataFrame()

            logger.debug(
                f"获取范围K线成功: {symbol} {timeframe}, "
                f"数量={len(df)}, 时间范围={df['time'].min()} ~ {df['time'].max()}"
            )

            return df

        except Exception as e:
            logger.error(f"获取范围K线失败: {e}", exc_info=True)
            raise

    def get_tick(self, symbol: str) -> Dict[str, Any]:
        """
        获取最新Tick数据

        Args:
            symbol: 交易品种代码

        Returns:
            dict 包含:
            - bid: 买价
            - ask: 卖价
            - last: 最新成交价
            - volume: 成交量
            - time: 更新时间

        Raises:
            ConnectionError: 平台未连接
        """
        if not self._ensure_connection():
            raise ConnectionError("平台未连接，无法获取数据")

        try:
            tick = self._connector.symbol_info_tick(symbol)

            if tick is None:
                logger.warning(f"未获取到Tick数据，品种={symbol}")
                return {}

            return tick

        except Exception as e:
            logger.error(f"获取Tick数据失败: {e}", exc_info=True)
            raise

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取品种交易信息

        Args:
            symbol: 交易品种代码

        Returns:
            dict 包含:
            - name: 品种名称
            - point: 最小价格变动单位
            - digits: 小数位数
            - volume_min: 最小交易量
            - volume_max: 最大交易量
            - volume_step: 交易量步长
            - contract_size: 合约规模
            - bid: 买价
            - ask: 卖价
            - spread: 点差
        """
        if not self._ensure_connection():
            raise ConnectionError("平台未连接，无法获取数据")

        try:
            info = self._connector.symbol_info(symbol)

            if info is None:
                logger.warning(f"未获取到品种信息: {symbol}")
                return {}

            # 转换为dict返回
            if hasattr(info, '__dict__'):
                return {k: v for k, v in info.__dict__.items()}
            elif hasattr(info, '_asdict'):
                return info._asdict()
            else:
                return dict(info)

        except Exception as e:
            logger.error(f"获取品种信息失败: {e}", exc_info=True)
            raise

    def get_available_symbols(self, pattern: str = "") -> List[str]:
        """
        获取可用品种列表

        Args:
            pattern: 模糊匹配模式，如 "USD" 返回所有包含USD的品种

        Returns:
            List[str]: 品种代码列表
        """
        if not self._ensure_connection():
            raise ConnectionError("平台未连接，无法获取数据")

        try:
            symbols = self._connector.symbols_get(pattern)

            if not symbols:
                logger.warning("未获取到品种列表")
                return []

            logger.debug(f"获取品种列表成功，数量={len(symbols)}")

            return symbols

        except Exception as e:
            logger.error(f"获取品种列表失败: {e}", exc_info=True)
            raise


# 便捷函数
def fetch_rates(
    symbol: str,
    timeframe: str,
    count: int = 500,
    connector: Optional[BaseConnector] = None
) -> pd.DataFrame:
    """
    便捷函数：获取K线数据

    Args:
        symbol: 交易品种
        timeframe: 时间周期
        count: K线数量
        connector: 平台连接器(可选)

    Returns:
        K线数据DataFrame
    """
    fetcher = DataFetcher(connector=connector)
    return fetcher.get_rates(symbol, timeframe, count)
