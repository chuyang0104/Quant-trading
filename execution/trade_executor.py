"""
交易执行模块 - 对接MetaTrader 5

封装MT5下单、平仓、修改、查询等操作。
"""

import logging
from typing import List, Dict, Optional, Literal, Any
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


class TradeExecutor:
    """
    MT5交易执行器

    封装常用MT5交易操作, 提供统一的错误处理和日志记录。

    Attributes:
        magic_number: EA魔术号, 用于标识策略订单
        deviation: 允许的最大滑点 (点)
    """

    def __init__(self, magic_number: int = 234000, deviation: int = 20):
        """
        初始化交易执行器

        Args:
            magic_number: EA魔术号, 默认234000
            deviation: 允许的最大滑点, 默认20点
        """
        self.magic_number = magic_number
        self.deviation = deviation

        # 确保MT5已初始化
        if not mt5.initialize():
            logger.error(f"MT5初始化失败: {mt5.last_error()}")
            raise ConnectionError("无法连接到MetaTrader 5")

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
            symbol: 交易品种, 如 "XAUUSD"
            direction: 方向, "BUY" 或 "SELL"
            volume: 手数
            sl: 止损价, 0表示不设
            tp: 止盈价, 0表示不设
            comment: 订单备注

        Returns:
            Dict[str, any]: 结果字典
                - success (bool): 是否成功
                - order_ticket (int): 订单号, 成功时返回
                - retcode (int): MT5返回码
                - comment (str): 结果描述
        """
        try:
            # 获取品种信息
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return {
                    'success': False,
                    'order_ticket': 0,
                    'retcode': -1,
                    'comment': f"品种 {symbol} 不存在"
                }

            # 获取当前报价
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {
                    'success': False,
                    'order_ticket': 0,
                    'retcode': -2,
                    'comment': f"无法获取 {symbol} 报价"
                }

            # 确定订单类型和价格
            if direction.upper() == "BUY":
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
                logger.info(f"准备开多仓 {symbol}, 手数={volume}, 价格={price:.5f}")
            elif direction.upper() == "SELL":
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
                logger.info(f"准备开空仓 {symbol}, 手数={volume}, 价格={price:.5f}")
            else:
                return {
                    'success': False,
                    'order_ticket': 0,
                    'retcode': -3,
                    'comment': f"无效的方向: {direction}"
                }

            # 构造订单请求
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol,
                'volume': volume,
                'type': order_type,
                'price': price,
                'sl': sl,
                'tp': tp,
                'deviation': self.deviation,
                'magic': self.magic_number,
                'comment': comment,
                'type_filling': mt5.ORDER_FILLING_IOC,
                'type_time': mt5.ORDER_TIME_GTC,
            }

            # 发送订单
            result = mt5.order_send(request)

            if result is None:
                error = mt5.last_error()
                logger.error(f"下单失败: {error}")
                return {
                    'success': False,
                    'order_ticket': 0,
                    'retcode': error[0] if error else -4,
                    'comment': f"下单失败: {error}"
                }

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"下单被拒绝: retcode={result.retcode}, comment={result.comment}")
                return {
                    'success': False,
                    'order_ticket': 0,
                    'retcode': result.retcode,
                    'comment': result.comment
                }

            logger.info(f"下单成功: 订单号={result.order}, comment={result.comment}")

            return {
                'success': True,
                'order_ticket': result.order,
                'retcode': result.retcode,
                'comment': result.comment
            }

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
            # 查找持仓
            position = mt5.positions_get(ticket=ticket)
            if position is None or len(position) == 0:
                logger.error(f"未找到订单 {ticket}")
                return False

            pos = position[0]

            # 获取当前报价
            tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None:
                logger.error(f"无法获取 {pos.symbol} 报价")
                return False

            # 构造平仓请求
            if pos.type == mt5.POSITION_TYPE_BUY:
                close_type = mt5.ORDER_TYPE_SELL
                close_price = tick.bid
            else:  # POSITION_TYPE_SELL
                close_type = mt5.ORDER_TYPE_BUY
                close_price = tick.ask

            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': pos.symbol,
                'volume': pos.volume,
                'type': close_type,
                'position': ticket,
                'price': close_price,
                'deviation': self.deviation,
                'magic': self.magic_number,
                'comment': "平仓",
                'type_filling': mt5.ORDER_FILLING_IOC,
                'type_time': mt5.ORDER_TIME_GTC,
            }

            result = mt5.order_send(request)

            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"平仓失败: retcode={result.retcode if result else 'N/A'}")
                return False

            logger.info(f"平仓成功: 订单号={ticket}")
            return True

        except Exception as e:
            logger.exception(f"平仓异常: {e}")
            return False

    def close_all(self, symbol: Optional[str] = None) -> List[int]:
        """
        平掉所有持仓

        Args:
            symbol: 指定品种, None表示平掉所有品种

        Returns:
            List[int]: 成功平仓的订单号列表
        """
        try:
            # 获取持仓列表
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
                logger.info(f"开始平仓 {symbol} 的所有持仓...")
            else:
                positions = mt5.positions_get()
                logger.info("开始平仓所有持仓...")

            if positions is None or len(positions) == 0:
                logger.info("没有持仓需要平仓")
                return []

            closed_tickets = []

            for pos in positions:
                # 只平仓本魔术号的订单 (可选逻辑)
                # if pos.magic != self.magic_number:
                #     continue

                ticket = pos.ticket
                if self.close_position(ticket):
                    closed_tickets.append(ticket)

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
            # 查找持仓
            position = mt5.positions_get(ticket=ticket)
            if position is None or len(position) == 0:
                logger.error(f"未找到订单 {ticket}")
                return False

            pos = position[0]

            request = {
                'action': mt5.TRADE_ACTION_SLTP,
                'symbol': pos.symbol,
                'position': ticket,
                'sl': sl,
                'tp': tp,
            }

            result = mt5.order_send(request)

            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"修改止损止盈失败: retcode={result.retcode if result else 'N/A'}")
                return False

            logger.info(f"修改止盈止损成功: 订单号={ticket}, SL={sl:.5f}, TP={tp:.5f}")
            return True

        except Exception as e:
            logger.exception(f"修改止盈止损异常: {e}")
            return False

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        查询当前持仓

        Args:
            symbol: 指定品种, None表示查询所有品种

        Returns:
            List[Dict]: 持仓列表, 每个元素包含:
                - ticket: 订单号
                - symbol: 品种
                - type: 类型 (0=BUY, 1=SELL)
                - volume: 手数
                - price_open: 开仓价
                - price_current: 当前价
                - sl: 止损价
                - tp: 止盈价
                - profit: 浮动盈亏
                - comment: 备注
        """
        try:
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()

            if positions is None or len(positions) == 0:
                return []

            result = []
            for pos in positions:
                result.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': pos.type,
                    'type_str': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'price_open': pos.price_open,
                    'price_current': pos.price_current,
                    'sl': pos.sl,
                    'tp': pos.tp,
                    'profit': pos.profit,
                    'comment': pos.comment,
                    'magic': pos.magic,
                })

            return result

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
            count = mt5.positions_total()
            return count if count else 0
        except Exception as e:
            logger.exception(f"获取持仓数量异常: {e}")
            return 0

    def __del__(self):
        """析构时清理MT5连接 (可选, 通常由主程序控制)"""
        # 注意: 不在这里shutdown, 因为可能有其他模块在使用MT5
        pass
