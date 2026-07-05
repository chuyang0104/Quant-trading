"""
风控管理模块

提供交易前风控检查、止损止盈计算、仓位管理等功能。
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """
    风控检查结果

    Attributes:
        passed: 是否通过检查
        reason: 未通过的原因描述
        details: 详细信息字典
    """
    passed: bool
    reason: str = ""
    details: dict = field(default_factory=dict)


class RiskManager:
    """
    风控管理器

    负责交易前的风险检查，包括：
    - 仓位大小检查
    - 每日亏损限制检查
    - 最大持仓数量检查
    - 动态止损止盈计算
    - 最优仓位计算

    Attributes:
        max_risk_per_trade: 单笔交易最大风险比例（占账户净值的百分比）
        max_daily_loss: 每日最大亏损比例（占账户净值的百分比）
        max_positions: 最大同时持仓数量
        initial_capital: 初始资金
        day_start_equity: 当日开盘净值
    """

    def __init__(
        self,
        max_risk_per_trade: float = 0.02,
        max_daily_loss: float = 0.05,
        max_positions: int = 5,
        initial_capital: float = 10000.0
    ):
        """
        初始化风控管理器

        Args:
            max_risk_per_trade: 单笔交易最大风险比例，默认2%
            max_daily_loss: 每日最大亏损比例，默认5%
            max_positions: 最大同时持仓数量，默认5个
            initial_capital: 初始资金，默认10000
        """
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_positions = max_positions
        self.initial_capital = initial_capital
        self.day_start_equity: Optional[float] = None

        logger.info(
            f"初始化风控管理器: 单笔风险={max_risk_per_trade:.1%}, "
            f"日亏损限制={max_daily_loss:.1%}, 最大持仓={max_positions}"
        )

    def check_position_size(
        self,
        volume: float,
        balance: float,
        symbol_info: Optional[dict] = None
    ) -> RiskCheckResult:
        """
        检查仓位手数是否合理

        检查项：
        1. 手数是否为正数
        2. 手数是否超过账户余额的一定比例
        3. 手数是否符合品种最小/最大手数要求

        Args:
            volume: 交易手数
            balance: 当前账户余额
            symbol_info: 品种信息字典，包含 volume_min, volume_max, volume_step 等

        Returns:
            RiskCheckResult: 检查结果
        """
        details = {"volume": volume, "balance": balance}

        # 检查手数是否为正数
        if volume <= 0:
            logger.warning(f"手数必须为正数, 当前: {volume}")
            return RiskCheckResult(
                passed=False,
                reason=f"手数必须为正数, 当前: {volume}",
                details=details
            )

        # 检查手数是否过大（简单检查：手数不应超过余额的10倍）
        max_volume_by_balance = balance * 10
        if volume > max_volume_by_balance:
            logger.warning(f"手数过大: {volume} > {max_volume_by_balance}")
            return RiskCheckResult(
                passed=False,
                reason=f"手数过大: {volume:.2f} > {max_volume_by_balance:.2f}",
                details=details
            )

        # 检查品种手数限制
        if symbol_info:
            volume_min = symbol_info.get("volume_min", 0.01)
            volume_max = symbol_info.get("volume_max", 100.0)
            volume_step = symbol_info.get("volume_step", 0.01)

            if volume < volume_min:
                logger.warning(f"手数小于最小值: {volume} < {volume_min}")
                return RiskCheckResult(
                    passed=False,
                    reason=f"手数小于最小值: {volume} < {volume_min}",
                    details=details | {"volume_min": volume_min}
                )

            if volume > volume_max:
                logger.warning(f"手数超过最大值: {volume} > {volume_max}")
                return RiskCheckResult(
                    passed=False,
                    reason=f"手数超过最大值: {volume} > {volume_max}",
                    details=details | {"volume_max": volume_max}
                )

            # 检查手数是否符合步长
            steps = volume / volume_step
            if abs(steps - round(steps)) > 1e-6:
                logger.warning(f"手数不符合步长要求: {volume}, 步长: {volume_step}")
                return RiskCheckResult(
                    passed=False,
                    reason=f"手数不符合步长要求: {volume}, 步长: {volume_step}",
                    details=details | {"volume_step": volume_step}
                )

        logger.debug(f"仓位检查通过: 手数={volume}")
        return RiskCheckResult(passed=True, reason="仓位检查通过", details=details)

    def check_daily_loss(
        self,
        current_equity: float,
        day_start_equity: Optional[float] = None
    ) -> RiskCheckResult:
        """
        检查当日亏损是否超过限制

        Args:
            current_equity: 当前账户净值
            day_start_equity: 当日开盘净值，如果不传则使用实例变量

        Returns:
            RiskCheckResult: 检查结果
        """
        equity = day_start_equity if day_start_equity is not None else self.day_start_equity

        if equity is None:
            logger.warning("当日开盘净值未设置，无法检查日亏损限制")
            return RiskCheckResult(
                passed=False,
                reason="当日开盘净值未设置，请先调用 update_daily_record()",
                details={"current_equity": current_equity}
            )

        loss_amount = equity - current_equity
        loss_percent = loss_amount / equity if equity > 0 else 0

        details = {
            "day_start_equity": equity,
            "current_equity": current_equity,
            "loss_amount": loss_amount,
            "loss_percent": loss_percent
        }

        if loss_percent > self.max_daily_loss:
            logger.warning(
                f"当日亏损超过限制: {loss_percent:.2%} > {self.max_daily_loss:.2%}"
            )
            return RiskCheckResult(
                passed=False,
                reason=f"当日亏损超过限制: {loss_percent:.2%} > {self.max_daily_loss:.2%}",
                details=details
            )

        logger.debug(f"日亏损检查通过: {loss_percent:.2%}")
        return RiskCheckResult(
            passed=True,
            reason="日亏损检查通过",
            details=details
        )

    def check_max_positions(
        self,
        current_count: int,
        max_positions: Optional[int] = None
    ) -> RiskCheckResult:
        """
        检查持仓数量是否达到上限

        Args:
            current_count: 当前持仓数量
            max_positions: 最大持仓数量，如果不传则使用实例变量

        Returns:
            RiskCheckResult: 检查结果
        """
        limit = max_positions if max_positions is not None else self.max_positions

        details = {
            "current_count": current_count,
            "max_positions": limit
        }

        if current_count >= limit:
            logger.warning(f"持仓数量已达上限: {current_count} >= {limit}")
            return RiskCheckResult(
                passed=False,
                reason=f"持仓数量已达上限: {current_count}/{limit}",
                details=details
            )

        logger.debug(f"持仓数量检查通过: {current_count}/{limit}")
        return RiskCheckResult(
            passed=True,
            reason=f"持仓数量检查通过: {current_count}/{limit}",
            details=details
        )

    def check_all(
        self,
        volume: float,
        balance: float,
        current_equity: float,
        position_count: int,
        symbol_info: Optional[dict] = None,
        day_start_equity: Optional[float] = None
    ) -> RiskCheckResult:
        """
        综合风控检查

        依次执行所有风控检查，任何一项不通过即返回失败。

        Args:
            volume: 交易手数
            balance: 当前账户余额
            current_equity: 当前账户净值
            position_count: 当前持仓数量
            symbol_info: 品种信息
            day_start_equity: 当日开盘净值

        Returns:
            RiskCheckResult: 综合检查结果
        """
        logger.info("开始综合风控检查...")

        # 1. 仓位检查
        position_check = self.check_position_size(volume, balance, symbol_info)
        if not position_check.passed:
            return position_check

        # 2. 日亏损检查
        daily_loss_check = self.check_daily_loss(current_equity, day_start_equity)
        if not daily_loss_check.passed:
            return daily_loss_check

        # 3. 持仓数量检查
        max_positions_check = self.check_max_positions(position_count)
        if not max_positions_check.passed:
            return max_positions_check

        logger.info("综合风控检查全部通过")
        return RiskCheckResult(
            passed=True,
            reason="综合风控检查全部通过",
            details={
                "volume": volume,
                "balance": balance,
                "current_equity": current_equity,
                "position_count": position_count
            }
        )

    def calculate_stop_loss(
        self,
        entry_price: float,
        direction: str,
        atr_value: float,
        multiplier: float = 2.0
    ) -> float:
        """
        基于ATR计算动态止损价格

        Args:
            entry_price: 入场价格
            direction: 交易方向 "BUY" 或 "SELL"
            atr_value: ATR（平均真实波动范围）值
            multiplier: ATR倍数，默认2倍

        Returns:
            float: 止损价格

        Raises:
            ValueError: 当direction不是BUY或SELL时
        """
        if direction.upper() == "BUY":
            stop_loss = entry_price - atr_value * multiplier
            logger.debug(
                f"买单止损计算: 入场={entry_price:.5f}, "
                f"ATR={atr_value:.5f}, 倍数={multiplier}, 止损={stop_loss:.5f}"
            )
            return stop_loss
        elif direction.upper() == "SELL":
            stop_loss = entry_price + atr_value * multiplier
            logger.debug(
                f"卖单止损计算: 入场={entry_price:.5f}, "
                f"ATR={atr_value:.5f}, 倍数={multiplier}, 止损={stop_loss:.5f}"
            )
            return stop_loss
        else:
            raise ValueError(f"无效的交易方向: {direction}, 必须是 'BUY' 或 'SELL'")

    def calculate_take_profit(
        self,
        entry_price: float,
        direction: str,
        risk_reward_ratio: float = 2.0,
        sl_distance: Optional[float] = None,
        stop_loss: Optional[float] = None
    ) -> float:
        """
        计算止盈价格

        基于风险收益比，止盈距离 = 止损距离 × 风险收益比

        Args:
            entry_price: 入场价格
            direction: 交易方向 "BUY" 或 "SELL"
            risk_reward_ratio: 风险收益比，默认2.0（盈亏比1:2）
            sl_distance: 止损距离（点数），与stop_loss二选一
            stop_loss: 止损价格，与sl_distance二选一

        Returns:
            float: 止盈价格

        Raises:
            ValueError: 当direction无效或未提供止损信息时
        """
        # 计算止损距离
        if sl_distance is not None:
            distance = sl_distance
        elif stop_loss is not None:
            distance = abs(stop_loss - entry_price)
        else:
            raise ValueError("必须提供 sl_distance 或 stop_loss 之一")

        tp_distance = distance * risk_reward_ratio

        if direction.upper() == "BUY":
            take_profit = entry_price + tp_distance
            logger.debug(
                f"买单止盈计算: 入场={entry_price:.5f}, "
                f"止损距离={distance:.5f}, 盈亏比={risk_reward_ratio}, "
                f"止盈={take_profit:.5f}"
            )
            return take_profit
        elif direction.upper() == "SELL":
            take_profit = entry_price - tp_distance
            logger.debug(
                f"卖单止盈计算: 入场={entry_price:.5f}, "
                f"止损距离={distance:.5f}, 盈亏比={risk_reward_ratio}, "
                f"止盈={take_profit:.5f}"
            )
            return take_profit
        else:
            raise ValueError(f"无效的交易方向: {direction}, 必须是 'BUY' 或 'SELL'")

    def calculate_position_size(
        self,
        balance: float,
        risk_percent: float,
        sl_distance_points: float,
        point_value: float
    ) -> float:
        """
        根据风险百分比和止损距离计算最优手数

        计算公式:
        风险金额 = 账户余额 × 风险百分比
        手数 = 风险金额 / (止损距离 × 点值)

        Args:
            balance: 账户余额
            risk_percent: 风险百分比（如0.02表示2%）
            sl_distance_points: 止损距离（点数）
            point_value: 每点价值（如黄金0.01点=1美元）

        Returns:
            float: 计算得到的手数

        Example:
            >>> # 黄金交易示例
            >>> # 余额10000，风险2%，止损50点，每点价值1美元
            >>> rm = RiskManager()
            >>> size = rm.calculate_position_size(10000, 0.02, 50, 1)
            >>> # 计算: 10000 * 0.02 / (50 * 1) = 200 / 50 = 4 手
        """
        risk_amount = balance * risk_percent
        risk_per_lot = sl_distance_points * point_value

        if risk_per_lot <= 0:
            logger.error(f"无效的风险每手数: {risk_per_lot}")
            return 0.0

        position_size = risk_amount / risk_per_lot

        logger.debug(
            f"手数计算: 余额={balance:.2f}, 风险={risk_percent:.1%}, "
            f"止损距离={sl_distance_points:.1f}点, 点值={point_value:.2f}, "
            f"计算手数={position_size:.2f}"
        )

        return position_size

    def update_daily_record(self, equity: float) -> None:
        """
        更新每日开盘净值记录

        应在每个交易日开盘时调用，用于日亏损限制检查。

        Args:
            equity: 当日开盘净值
        """
        self.day_start_equity = equity
        logger.info(f"更新每日开盘净值: {equity:.2f}")

    def reset_daily_record(self) -> None:
        """
        重置每日记录

        用于测试或特殊情况下的记录重置。
        """
        self.day_start_equity = None
        logger.info("重置每日开盘净值记录")


# 导出
__all__ = ["RiskManager", "RiskCheckResult"]
