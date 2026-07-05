"""
实时监控模块

提供账户状态、持仓信息的实时监控功能。
在后台线程中定期采集MT5数据，提供统一的状态查询接口。
"""

import threading
import time
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None
    logging.warning("MetaTrader5 库未安装")

logger = logging.getLogger(__name__)


@dataclass
class PositionDetail:
    """
    持仓详情

    Attributes:
        ticket: 订单号
        symbol: 交易品种
        type: 订单类型 (0=BUY, 1=SELL)
        volume: 手数
        price_open: 开仓价
        price_current: 当前价
        profit: 浮动盈亏
        comment: 订单备注
    """
    ticket: int
    symbol: str
    type: int
    volume: float
    price_open: float
    price_current: float
    profit: float
    comment: str = ""


@dataclass
class AccountInfo:
    """
    账户信息

    Attributes:
        balance: 余额
        equity: 净值
        margin: 已用保证金
        free_margin: 可用保证金
        margin_level: 保证金水平
        profit: 浮动盈亏
        currency: 账户货币
    """
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    profit: float
    currency: str = "USD"


class Monitor:
    """
    实时监控器

    在后台线程中定期采集MT5数据，提供统一的状态查询接口。

    监控内容：
    - 账户信息（余额、净值、保证金等）
    - 持仓明细（品种、手数、盈亏等）
    - 连接状态
    - 监控运行状态

    Attributes:
        interval_seconds: 数据采集间隔（秒）
        is_running: 监控是否正在运行
        connection_ok: MT5连接是否正常
    """

    def __init__(self, interval_seconds: int = 5):
        """
        初始化监控器

        Args:
            interval_seconds: 数据采集间隔，默认5秒
        """
        self.interval_seconds = interval_seconds
        self._is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # 数据缓存
        self._account_info: Optional[AccountInfo] = None
        self._positions: List[Dict[str, Any]] = []
        self._position_count: int = 0
        self._last_update: Optional[datetime] = None
        self._connection_ok: bool = False

        # 监控指标
        self._equity_history: List[float] = []
        self._max_history_length: int = 1000
        self._last_alert_time: Optional[datetime] = None
        self._alert_cooldown: int = 300  # 5分钟

        # 上一周期的净值（用于检测大幅波动）
        self._previous_equity: Optional[float] = None
        self._equity_change_threshold: float = 0.05  # 5%变化触发警告

        logger.info(f"监控器初始化完成, 采集间隔: {interval_seconds}秒")

    def start(self) -> bool:
        """
        启动后台监控线程

        Returns:
            bool: 是否成功启动
        """
        if self._is_running:
            logger.warning("监控器已在运行中")
            return False

        if mt5 is None:
            logger.error("MetaTrader5 库未安装，无法启动监控")
            return False

        self._is_running = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            name="MonitorThread",
            daemon=True
        )
        self._thread.start()

        logger.info("监控器已启动")
        return True

    def stop(self) -> None:
        """
        停止监控器

        等待监控线程安全退出。
        """
        if not self._is_running:
            logger.warning("监控器未在运行")
            return

        logger.info("正在停止监控器...")
        self._is_running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                logger.warning("监控线程未能在10秒内退出")

        logger.info("监控器已停止")

    def _run(self) -> None:
        """
        监控线程主循环

        定期采集MT5数据并更新缓存。
        """
        logger.info("监控线程开始运行")

        while self._is_running and not self._stop_event.is_set():
            try:
                self._collect_data()
                self._check_alerts()
            except Exception as e:
                logger.error(f"监控数据采集异常: {e}", exc_info=True)

            # 等待下一次采集或停止信号
            self._stop_event.wait(timeout=self.interval_seconds)

        logger.info("监控线程已退出")

    def _collect_data(self) -> None:
        """
        采集MT5数据并更新缓存

        包括账户信息和持仓信息。
        """
        # 检查连接状态
        if not mt5.initialize():
            self._connection_ok = False
            logger.error("MT5连接失败")
            return

        self._connection_ok = True

        # 获取账户信息
        account = mt5.account_info()
        if account is None:
            logger.error("无法获取账户信息")
            return

        # 转换为AccountInfo
        self._account_info = AccountInfo(
            balance=account.balance,
            equity=account.equity,
            margin=account.margin,
            free_margin=account.margin_free,
            margin_level=account.margin_level if account.margin > 0 else 0,
            profit=account.profit,
            currency=account.currency
        )

        # 记录净值历史
        self._equity_history.append(account.equity)
        if len(self._equity_history) > self._max_history_length:
            self._equity_history.pop(0)

        # 检测净值大幅波动
        if self._previous_equity is not None:
            equity_change = abs(account.equity - self._previous_equity)
            if self._previous_equity > 0:
                change_percent = equity_change / self._previous_equity
                if change_percent > self._equity_change_threshold:
                    logger.warning(
                        f"净值大幅波动: {self._previous_equity:.2f} -> {account.equity:.2f} "
                        f"({change_percent:.1%})"
                    )
        self._previous_equity = account.equity

        # 获取持仓信息
        positions = mt5.positions_get()
        if positions is None:
            self._positions = []
            self._position_count = 0
        else:
            self._position_count = len(positions)
            self._positions = []
            for pos in positions:
                self._positions.append({
                    "ticket": pos.ticket,
                    "symbol": pos.symbol,
                    "type": pos.type,  # 0=BUY, 1=SELL
                    "volume": pos.volume,
                    "price_open": pos.price_open,
                    "price_current": pos.price_current,
                    "profit": pos.profit,
                    "comment": pos.comment,
                    "sl": pos.sl,
                    "tp": pos.tp
                })

        self._last_update = datetime.now()

        logger.debug(
            f"监控数据已更新: 余额={self._account_info.balance:.2f}, "
            f"净值={self._account_info.equity:.2f}, 持仓={self._position_count}"
        )

    def _check_alerts(self) -> None:
        """
        检查并触发告警

        检查项：
        - 连接断开
        - 净值大幅波动
        - 保证金水平过低
        """
        if not self._connection_ok:
            self._trigger_alert("MT5连接断开")
            return

        if self._account_info:
            # 检查保证金水平
            if 0 < self._account_info.margin_level < 100:
                self._trigger_alert(
                    f"保证金水平过低: {self._account_info.margin_level:.1f}%"
                )

    def _trigger_alert(self, message: str) -> None:
        """
        触发告警（带冷却时间）

        Args:
            message: 告警消息
        """
        now = datetime.now()

        # 检查冷却时间
        if self._last_alert_time is not None:
            elapsed = (now - self._last_alert_time).total_seconds()
            if elapsed < self._alert_cooldown:
                return

        self._last_alert_time = now
        logger.warning(f"监控告警: {message}")

    def get_status(self) -> Dict[str, Any]:
        """
        获取当前监控状态

        Returns:
            dict: 包含以下字段的字典
                - account: 账户信息字典
                - positions: 持仓详情列表
                - position_count: 持仓数量
                - is_running: 监控是否运行中
                - last_update: 最后更新时间
                - connection_ok: 连接是否正常
        """
        status = {
            "is_running": self._is_running,
            "connection_ok": self._connection_ok,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "position_count": self._position_count,
            "positions": self._positions.copy(),
            "account": {}
        }

        if self._account_info:
            status["account"] = {
                "balance": self._account_info.balance,
                "equity": self._account_info.equity,
                "margin": self._account_info.margin,
                "free_margin": self._account_info.free_margin,
                "margin_level": self._account_info.margin_level,
                "profit": self._account_info.profit,
                "currency": self._account_info.currency
            }

        return status

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        获取账户信息

        Returns:
            dict: 账户信息字典，如果未运行则返回None
        """
        if self._account_info is None:
            return None

        return {
            "balance": self._account_info.balance,
            "equity": self._account_info.equity,
            "margin": self._account_info.margin,
            "free_margin": self._account_info.free_margin,
            "margin_level": self._account_info.margin_level,
            "profit": self._account_info.profit,
            "currency": self._account_info.currency
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        获取持仓详情

        Returns:
            list[dict]: 持仓详情列表，每项包含
                ticket, symbol, type, volume, price_open, price_current, profit, comment
        """
        return self._positions.copy()

    def get_positions_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """
        获取指定品种的持仓

        Args:
            symbol: 交易品种代码

        Returns:
            list[dict]: 该品种的持仓列表
        """
        return [p for p in self._positions if p["symbol"] == symbol]

    def check_connection(self) -> bool:
        """
        检查MT5连接状态

        Returns:
            bool: 连接是否正常
        """
        if mt5 is None:
            return False

        try:
            connected = mt5.initialize()
            self._connection_ok = connected
            return connected
        except Exception as e:
            logger.error(f"检查MT5连接时异常: {e}")
            self._connection_ok = False
            return False

    def get_equity_history(self) -> List[float]:
        """
        获取净值历史记录

        Returns:
            list[float]: 净值历史列表
        """
        return self._equity_history.copy()

    def get_equity_change(self) -> Optional[float]:
        """
        获取净值变化百分比

        Returns:
            float: 净值变化百分比，如果无历史数据则返回None
        """
        if len(self._equity_history) < 2:
            return None

        current = self._equity_history[-1]
        previous = self._equity_history[0]

        if previous == 0:
            return None

        return (current - previous) / previous

    @property
    def is_running(self) -> bool:
        """监控是否正在运行"""
        return self._is_running

    @property
    def connection_ok(self) -> bool:
        """MT5连接是否正常"""
        return self._connection_ok

    @property
    def position_count(self) -> int:
        """当前持仓数量"""
        return self._position_count

    def clear_history(self) -> None:
        """清空历史数据"""
        self._equity_history.clear()
        self._previous_equity = None
        logger.info("监控历史数据已清空")


# 导出
__all__ = ["Monitor", "AccountInfo", "PositionDetail"]
