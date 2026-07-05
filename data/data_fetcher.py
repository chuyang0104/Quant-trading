# data/data_fetcher.py
"""
MT5 行情数据获取模块

提供从 MetaTrader 5 获取行情数据的接口，包括:
- K线数据 (OHLCV)
- Tick 数据 (实时报价)
- 品种信息 (交易规则)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    raise ImportError(
        "未安装 MetaTrader5 库，请运行: pip install MetaTrader5"
    )

from core.base_classes import BaseDataSource
from core.mt5_connector import get_connector

logger = logging.getLogger(__name__)


class DataFetcher(BaseDataSource):
    """
    MT5 行情数据获取器

    继承 BaseDataSource，实现从 MT5 获取 K线和Tick数据。
    所有方法在调用前会自动检查并确保 MT5 连接状态。
    """

    # 时间周期映射表
    TIMEFRAME_MAP: Dict[str, int] = {
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

    def __init__(self, mt5_path: Optional[str] = None):
        """
        初始化数据获取器

        Args:
            mt5_path: MT5 terminal64.exe 的完整路径，为 None 时使用默认路径
        """
        self._connector = get_connector(path=mt5_path)
        logger.info("DataFetcher 初始化完成")

    def _ensure_connection(self) -> bool:
        """
        确保 MT5 连接状态

        Returns:
            bool: 连接是否正常
        """
        return self._connector.ensure_connected()

    def _parse_timeframe(self, timeframe: str) -> int:
        """
        解析时间周期字符串为 MT5 常量

        Args:
            timeframe: 时间周期字符串，如 "M1", "H1", "D1"

        Returns:
            int: MT5 时间周期常量

        Raises:
            ValueError: 不支持的时间周期
        """
        timeframe_upper = timeframe.upper()
        if timeframe_upper not in self.TIMEFRAME_MAP:
            raise ValueError(
                f"不支持的时间周期: {timeframe}，"
                f"支持的周期: {list(self.TIMEFRAME_MAP.keys())}"
            )
        return self.TIMEFRAME_MAP[timeframe_upper]

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
            ConnectionError: MT5 未连接
            ValueError: 获取数据失败
        """
        if not self._ensure_connection():
            raise ConnectionError("MT5 未连接，无法获取数据")

        mt5_timeframe = self._parse_timeframe(timeframe)

        try:
            # 调用 MT5 API 获取数据
            rates = mt5.copy_rates_from_pos(
                symbol,
                mt5_timeframe,
                0,  # 从最新位置开始
                count
            )

            if rates is None or len(rates) == 0:
                error_code = mt5.last_error()
                logger.warning(
                    f"未获取到数据，品种={symbol}, 周期={timeframe}, "
                    f"错误={error_code}"
                )
                return pd.DataFrame()

            # 转换为 DataFrame
            df = pd.DataFrame(rates)

            # 将时间戳转换为 datetime
            df['time'] = pd.to_datetime(df['time'], unit='s')

            # 按时间升序排列
            df = df.sort_values('time').reset_index(drop=True)

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

        Args:
            symbol: 交易品种代码
            timeframe: 时间周期
            start_dt: 起始时间
            end_dt: 结束时间

        Returns:
            pandas.DataFrame: K线数据，格式同 get_rates()
        """
        if not self._ensure_connection():
            raise ConnectionError("MT5 未连接，无法获取数据")

        mt5_timeframe = self._parse_timeframe(timeframe)

        try:
            # MT5 使用 UTC 时间，需要转换
            rates = mt5.copy_rates_range(
                symbol,
                mt5_timeframe,
                start_dt,
                end_dt
            )

            if rates is None or len(rates) == 0:
                logger.warning(
                    f"未获取到数据，品种={symbol}, 周期={timeframe}, "
                    f"时间范围={start_dt} ~ {end_dt}"
                )
                return pd.DataFrame()

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df.sort_values('time').reset_index(drop=True)

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
            ConnectionError: MT5 未连接
            ValueError: 获取数据失败
        """
        if not self._ensure_connection():
            raise ConnectionError("MT5 未连接，无法获取数据")

        try:
            tick = mt5.symbol_info_tick(symbol)

            if tick is None:
                error_code = mt5.last_error()
                logger.warning(
                    f"未获取到Tick数据，品种={symbol}, 错误={error_code}"
                )
                return {}

            return {
                'bid': tick.bid,
                'ask': tick.ask,
                'last': tick.last,
                'volume': tick.volume,
                'time': datetime.fromtimestamp(tick.time) if tick.time > 0 else None
            }

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
            - point: 最小价格变动单位
            - digits: 小数位数
            - volume_min: 最小交易量
            - volume_max: 最大交易量
            - volume_step: 交易量步长
            - trade_contract_size: 合约规模
            - currency_base: 基础货币
            - currency_profit: 利润货币
            - description: 品种描述
        """
        if not self._ensure_connection():
            raise ConnectionError("MT5 未连接，无法获取数据")

        try:
            info = mt5.symbol_info(symbol)

            if info is None:
                logger.warning(f"未获取到品种信息: {symbol}")
                return {}

            return {
                'name': info.name,
                'description': info.description,
                'point': info.point,
                'digits': info.digits,
                'volume_min': info.volume_min,
                'volume_max': info.volume_max,
                'volume_step': info.volume_step,
                'trade_contract_size': info.trade_contract_size,
                'currency_base': info.currency_base,
                'currency_profit': info.currency_profit,
            }

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
            raise ConnectionError("MT5 未连接，无法获取数据")

        try:
            symbols = mt5.symbols_get()

            if symbols is None:
                logger.warning("未获取到品种列表")
                return []

            # 筛选可见品种
            visible_symbols = [
                s.name for s in symbols
                if s.visible and (pattern == "" or pattern.lower() in s.name.lower())
            ]

            logger.debug(f"获取品种列表成功，数量={len(visible_symbols)}")

            return visible_symbols

        except Exception as e:
            logger.error(f"获取品种列表失败: {e}", exc_info=True)
            raise


# 便捷函数
def fetch_rates(
    symbol: str,
    timeframe: str,
    count: int = 500,
    mt5_path: Optional[str] = None
) -> pd.DataFrame:
    """
    便捷函数：获取K线数据

    Args:
        symbol: 交易品种
        timeframe: 时间周期
        count: K线数量
        mt5_path: MT5路径

    Returns:
        K线数据DataFrame
    """
    fetcher = DataFetcher(mt5_path=mt5_path)
    return fetcher.get_rates(symbol, timeframe, count)


if __name__ == "__main__":
    # 配置日志用于测试
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 50)
    print("DataFetcher 测试")
    print("=" * 50)

    # 创建数据获取器
    fetcher = DataFetcher()

    # 确保连接
    if fetcher._ensure_connection():
        # 测试获取K线
        print("\n1. 测试获取K线数据...")
        df = fetcher.get_rates("XAUUSD", "H1", count=10)
        if not df.empty:
            print(df.head())
            print(f"数据形状: {df.shape}")
            print(f"列名: {list(df.columns)}")

        # 测试获取Tick
        print("\n2. 测试获取Tick数据...")
        tick = fetcher.get_tick("XAUUSD")
        if tick:
            print(f"买价: {tick.get('bid')}, 卖价: {tick.get('ask')}")

        # 测试获取品种信息
        print("\n3. 测试获取品种信息...")
        info = fetcher.get_symbol_info("XAUUSD")
        if info:
            print(f"品种信息: {info}")

        # 测试获取可用品种
        print("\n4. 测试获取可用品种...")
        symbols = fetcher.get_available_symbols("USD")
        print(f"包含USD的品种数量: {len(symbols)}")
        if symbols:
            print(f"前5个: {symbols[:5]}")
