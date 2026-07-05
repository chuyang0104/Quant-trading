"""
回测性能指标计算模块

提供常用回测指标计算函数: 总收益率、年化收益率、最大回撤、夏普比率、胜率、盈亏比等。
"""

from typing import List, Dict
import pandas as pd
import numpy as np

from backtest.backtest_engine import Trade


def calculate_metrics(equity_curve: pd.Series, trades: List[Trade]) -> Dict[str, float]:
    """
    计算回测性能指标

    Args:
        equity_curve: 资金曲线 Series, index为时间, value为权益值
        trades: 交易记录列表

    Returns:
        Dict[str, float]: 包含各项指标的字典
            - total_return: 总收益率
            - annual_return: 年化收益率
            - max_drawdown: 最大回撤百分比
            - sharpe_ratio: 夏普比率
            - win_rate: 胜率
            - profit_factor: 盈亏比
            - total_trades: 总交易笔数
            - avg_trade_pnl: 平均每笔盈亏
            - avg_holding_bars: 平均持仓bar数
    """
    if equity_curve.empty:
        return {
            'total_return': 0.0,
            'annual_return': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'total_trades': 0,
            'avg_trade_pnl': 0.0,
            'avg_holding_bars': 0.0
        }

    initial_capital = equity_curve.iloc[0]
    final_capital = equity_curve.iloc[-1]

    # 1. 总收益率
    total_return = ((final_capital - initial_capital) / initial_capital) * 100

    # 2. 年化收益率 (按252个交易日计算)
    if len(equity_curve) > 1:
        # 计算实际交易日数
        trading_days = len(equity_curve) - 1
        years = trading_days / 252.0
        if years > 0:
            annual_return = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
        else:
            annual_return = total_return
    else:
        annual_return = 0.0

    # 3. 最大回撤
    max_drawdown = _calculate_max_drawdown(equity_curve)

    # 4. 夏普比率 (无风险利率2%)
    sharpe_ratio = _calculate_sharpe_ratio(equity_curve, risk_free_rate=0.02)

    # 5. 胜率
    win_rate = _calculate_win_rate(trades)

    # 6. 盈亏比
    profit_factor = _calculate_profit_factor(trades)

    # 7. 总交易笔数
    total_trades = len(trades)

    # 8. 平均每笔盈亏
    if trades:
        avg_trade_pnl = np.mean([t.pnl for t in trades])
    else:
        avg_trade_pnl = 0.0

    # 9. 平均持仓bar数
    avg_holding_bars = _calculate_avg_holding_bars(trades)

    return {
        'total_return': round(total_return, 2),
        'annual_return': round(annual_return, 2),
        'max_drawdown': round(max_drawdown, 2),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'total_trades': total_trades,
        'avg_trade_pnl': round(avg_trade_pnl, 2),
        'avg_holding_bars': round(avg_holding_bars, 1)
    }


def _calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """
    计算最大回撤百分比

    Args:
        equity_curve: 资金曲线

    Returns:
        float: 最大回撤百分比
    """
    if len(equity_curve) < 2:
        return 0.0

    # 计算累计最大值
    cummax = equity_curve.cummax()

    # 计算回撤
    drawdown = (equity_curve - cummax) / cummax * 100

    # 返回最大回撤 (负值转正)
    return abs(drawdown.min())


def _calculate_sharpe_ratio(equity_curve: pd.Series, risk_free_rate: float = 0.02) -> float:
    """
    计算夏普比率

    Args:
        equity_curve: 资金曲线
        risk_free_rate: 年化无风险利率, 默认2%

    Returns:
        float: 夏普比率
    """
    if len(equity_curve) < 2:
        return 0.0

    # 计算日收益率
    returns = equity_curve.pct_change().dropna()

    if returns.empty or returns.std() == 0:
        return 0.0

    # 日化无风险利率
    daily_rf = risk_free_rate / 252

    # 计算超额收益的均值和标准差
    excess_returns = returns - daily_rf

    # 年化夏普比率
    sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252)

    return sharpe


def _calculate_win_rate(trades: List[Trade]) -> float:
    """
    计算胜率

    Args:
        trades: 交易记录列表

    Returns:
        float: 胜率百分比
    """
    if not trades:
        return 0.0

    winning_trades = sum(1 for t in trades if t.pnl > 0)
    return (winning_trades / len(trades)) * 100


def _calculate_profit_factor(trades: List[Trade]) -> float:
    """
    计算盈亏比 (总盈利 / 总亏损)

    Args:
        trades: 交易记录列表

    Returns:
        float: 盈亏比, 0表示没有盈利交易
    """
    if not trades:
        return 0.0

    total_profit = sum(t.pnl for t in trades if t.pnl > 0)
    total_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))

    if total_loss == 0:
        return float('inf') if total_profit > 0 else 0.0

    return total_profit / total_loss


def _calculate_avg_holding_bars(trades: List[Trade]) -> float:
    """
    计算平均持仓bar数

    Args:
        trades: 交易记录列表

    Returns:
        float: 平均持仓bar数
    """
    if not trades:
        return 0.0

    holding_periods = []
    for trade in trades:
        if trade.exit_time and trade.entry_time:
            # 转换为时间差
            if isinstance(trade.exit_time, pd.Timestamp):
                exit_time = trade.exit_time
            else:
                exit_time = pd.Timestamp(trade.exit_time)

            if isinstance(trade.entry_time, pd.Timestamp):
                entry_time = trade.entry_time
            else:
                entry_time = pd.Timestamp(trade.entry_time)

            bars = (exit_time - entry_time).total_seconds() / 60  # 假设1分钟K线
            holding_periods.append(bars)

    if not holding_periods:
        return 0.0

    return np.mean(holding_periods)


def print_metrics(metrics: Dict[str, float]) -> None:
    """
    格式化打印回测指标

    Args:
        metrics: 指标字典
    """
    print("\n" + "=" * 50)
    print("回测结果".center(50))
    print("=" * 50)

    print(f"总收益率:        {metrics['total_return']:.2f}%")
    print(f"年化收益率:      {metrics['annual_return']:.2f}%")
    print(f"最大回撤:        {metrics['max_drawdown']:.2f}%")
    print(f"夏普比率:        {metrics['sharpe_ratio']:.2f}")
    print(f"胜率:            {metrics['win_rate']:.2f}%")
    print(f"盈亏比:          {metrics['profit_factor']:.2f}")
    print(f"总交易笔数:      {metrics['total_trades']}")
    print(f"平均每笔盈亏:    ${metrics['avg_trade_pnl']:.2f}")
    print(f"平均持仓bar数:   {metrics['avg_holding_bars']:.1f}")

    print("=" * 50 + "\n")


def format_metrics_table(metrics: Dict[str, float]) -> str:
    """
    将指标格式化为表格字符串

    Args:
        metrics: 指标字典

    Returns:
        str: 表格格式的指标字符串
    """
    lines = [
        "+" + "-" * 40 + "+",
        "|" + "回测指标".center(40) + "|",
        "+" + "-" * 40 + "+",
    ]

    labels = [
        ("总收益率", f"{metrics['total_return']:.2f}%"),
        ("年化收益率", f"{metrics['annual_return']:.2f}%"),
        ("最大回撤", f"{metrics['max_drawdown']:.2f}%"),
        ("夏普比率", f"{metrics['sharpe_ratio']:.2f}"),
        ("胜率", f"{metrics['win_rate']:.2f}%"),
        ("盈亏比", f"{metrics['profit_factor']:.2f}"),
        ("总交易笔数", str(metrics['total_trades'])),
        ("平均每笔盈亏", f"${metrics['avg_trade_pnl']:.2f}"),
        ("平均持仓bar数", f"{metrics['avg_holding_bars']:.1f}"),
    ]

    for label, value in labels:
        lines.append(f"| {label.ljust(20)} | {value.rjust(16)} |")

    lines.append("+" + "-" * 40 + "+")

    return "\n".join(lines)
