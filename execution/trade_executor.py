"""
交易执行模块 - 统一连接器接口

封装交易平台交易操作，使用 BaseConnector 接口。
支持 MT4/MT5 等平台，通过工厂函数创建连接器。
"""

import logging
from typing import List, Dict, Optional, Literal, Any

from core.connector_base import BaseConnector, OrderResult, PositionInfo
from core.connector_factory import create_connector
from config.settings import settings

logger = logging.getLogger(__name__)


class TradeExecutor:
    """
    交易执行器 - 统一接口

    封装常用交易操作，通过 BaseConnector 接口支持多平台。
    提供统一的错误处理和日志记录。

    Attributes:
        connector: 平台连接器实例
        magic_number: EA魔术号，用于标识策略订单
        deviation: 允许的最大滑点 (点)
    """

    def __init__(
        self,
        connector: Optional[BaseConnector] = None,
        magic_number: int = 234000,
        deviation: int = 20
    ):
        """
        初始化交易执行器

        Args:
            connector: 平台连接器，None 时自动创建
            magic_number: EA魔术号，默认234000
            deviation: 允许的最大滑点，默认20点
        """
        self.magic_number = magic_number
        self.deviation = deviation

        # 创建或使用传入的连接器
        if connector is None:
            # 使用配置的平台类型创建连接器
            platform = settings.platform
            if platform == "mt5":
                self.connector = create_connector("mt5", path=settings.mt5_path)
            elif platform == "mt4":
                self.connector = create_connector("mt4")
            else:
                raise ValueError(f"不支持的平台类型: {platform}")
        else:
            self.connector = connector

        logger.info(f"TradeExecutor初始化成功, magic={magic_number}")

    def open_position(
        self,
        symbol: str,
        direction: Literal["BUY", "SELL"],
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = ""
    ) -> Dict[str, Any]:
        """
        开仓 (市价单)

        Args:
            symbol: 交易品种，如 "XAUUSD"
            direction: 方向，"BUY" 或 "SELL"
            volume: 手数
            sl: 止损价，0表示不设
            tp: 止盈价，0表示不设
            comment: 订单备注

        Returns:
            Dict[str, any]: 结果字典
                - success (bool): 是否成功
                - order_ticket (int): 订单号，成功时返回
                - retcode (int): 返回码
                - comment (str): 结果描述
        """
        try:
            # 获取当前报价
            tick = self.connector.symbol_info_tick(symbol)
            if tick is None:
                return {
                    'success': False,
                    'order_ticket': 0,
                    'retcode': -2,
                    'comment': f"无法获取 {symbol} 报价"
                }

            # 确定订单类型和价格
            if direction.upper() == "BUY":
                price = tick["ask"]
                logger.info(f"准备开多仓 {symbol}, 手数={volume}, 价格={price:.5f}")
            elif direction.upper() == "SELL":
                price = tick["bid"]
                logger.info(f"准备开空仓 {symbol}, 手数={volume}, 价格={price:.5f}")
            else:
                return {
                    'success': False,
                    'order_ticket': 0,
                    'retcode': -3,
                    'comment': f"无效的方向: {direction}"
                }

            # 构造统一格式的订单请求
            request = {
                "action": "DEAL",
                "symbol": symbol,
                "type": direction.upper(),
                "volume": volume,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": self.deviation,
                "magic": self.magic_number,
                "comment": comment
            }

            # 发送订单
            result = self.connector.order_send(request)

            return result.to_dict()

        except Exception as e:
            logger.exception(f"开仓异常: {e}")
            return {
                'success': False,
                'order_ticket': 0,
                'retcode': -99,
                'comment': f"系统异常: {str(e)}"
            }

    def close_position(self, ticket: int) -> bool:
        """
        平仓指定订单

        Args:
            ticket: 持仓订单号

        Returns:
            bool: 是否成功
        """
        try:
            # 获取持仓信息 (通过 ticket 过滤)
            # 注意: connector.positions_get 需要支持 ticket 参数，
            # 如果不支持则获取全部后筛选
            positions = self.connector.positions_get()
            position = None
            for pos in positions:
                if pos.ticket == ticket:
                    position = pos
                    break

            if position is None:
                logger.error(f"未找到订单 {ticket}")
                return False

            # 获取当前报价
            tick = self.connector.symbol_info_tick(position.symbol)
            if tick is None:
                logger.error(f"无法获取 {position.symbol} 报价")
                return False

            # 确定平仓类型和价格
            # position.type: 0=BUY, 1=SELL
            if position.type == 0:  # 多单，用卖价平仓
                close_type = "SELL"
                close_price = tick["bid"]
            else:  # 空单，用买价平仓
                close_type = "BUY"
                close_price = tick["ask"]

            # 构造平仓请求
            request = {
                "action": "DEAL",
                "symbol": position.symbol,
                "type": close_type,
                "volume": position.volume,
                "position": ticket,
                "price": close_price,
                "deviation": self.deviation,
                "magic": self.magic_number,
                "comment": "平仓"
            }

            result = self.connector.order_send(request)

            if result.success:
                logger.info(f"平仓成功: 订单号={ticket}")
                return True
            else:
                logger.error(f"平仓失败: retcode={result.retcode}, comment={result.comment}")
                return False

        except Exception as e:
            logger.exception(f"平仓异常: {e}")
            return False

    def close_all(self, symbol: Optional[str] = None) -> List[int]:
        """
        平掉所有持仓

        Args:
            symbol: 指定品种，None 表示平掉所有品种

        Returns:
            List[int]: 成功平仓的订单号列表
        """
        try:
            # 获取持仓列表
            positions = self.connector.positions_get(symbol=symbol)

            if symbol:
                logger.info(f"开始平仓 {symbol} 的所有持仓...")
            else:
                logger.info("开始平仓所有持仓...")

            if not positions:
                logger.info("没有持仓需要平仓")
                return []

            closed_tickets = []

            for pos in positions:
                if self.close_position(pos.ticket):
                    closed_tickets.append(pos.ticket)

            logger.info(f"平仓完成, 成功平仓 {len(closed_tickets)}/{len(positions)} 单")
            return closed_tickets

        except Exception as e:
            logger.exception(f"批量平仓异常: {e}")
            return []

    def modify_position(
        self,
        ticket: int,
        sl: float,
        tp: float
    ) -> bool:
        """
        修改持仓的止盈止损

        Args:
            ticket: 持仓订单号
            sl: 新止损价
            tp: 新止盈价

        Returns:
            bool: 是否成功
        """
        try:
            # 构造修改请求
            request = {
                "action": "MODIFY",
                "position": ticket,
                "sl": sl,
                "tp": tp
            }

            result = self.connector.order_send(request)

            if result.success:
                logger.info(f"修改止盈止损成功: 订单号={ticket}, SL={sl:.5f}, TP={tp:.5f}")
                return True
            else:
                logger.error(f"修改止损止盈失败: retcode={result.retcode}, comment={result.comment}")
                return False

        except Exception as e:
            logger.exception(f"修改止盈止损异常: {e}")
            return False

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        查询当前持仓

        Args:
            symbol: 指定品种，None 表示查询所有品种

        Returns:
            List[Dict]: 持仓列表，每个元素包含:
                - ticket: 订单号
                - symbol: 品种
                - type: 类型 (0=BUY, 1=SELL)
                - type_str: 类型字符串
                - volume: 手数
                - price_open: 开仓价
                - price_current: 当前价
                - sl: 止损价
                - tp: 止盈价
                - profit: 浮动盈亏
                - comment: 备注
        """
        try:
            positions = self.connector.positions_get(symbol=symbol)

            return [pos.to_dict() for pos in positions]

        except Exception as e:
            logger.exception(f"查询持仓异常: {e}")
            return []

    def get_position_count(self) -> int:
        """
        获取当前持仓数量

        Returns:
            int: 持仓数量
        """
        try:
            return self.connector.positions_total()
        except Exception as e:
            logger.exception(f"获取持仓数量异常: {e}")
            return 0
