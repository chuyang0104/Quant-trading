#!/bin/bash
cd /d/project/Quant-trading
claude -p '你在 D:\project\Quant-trading 量化交易项目中工作。先读 DESIGN.md 了解整体设计。

你的任务：创建 backtest 和 execution 两个目录下的文件。

## 文件1: backtest/backtest_engine.py
事件驱动回测引擎：
- BacktestResult dataclass: trades(list), equity_curve(pd.Series), metrics(dict), signals_df(pd.DataFrame)
- Trade dataclass: entry_time, exit_time, direction(1/-1), entry_price, exit_price, volume, pnl, pnl_pct
- BacktestEngine类:
  - __init__(initial_capital=10000, volume=0.1, spread=0.0, commission=0.0, sl_points=0, tp_points=0)
  - run(df, strategy) -> BacktestResult: 逐bar遍历, signal=1空仓则开多, signal=-1持仓则平仓, 支持止损止盈
  - 记录每笔交易和每日权益，最后调用backtest.metrics.calculate_metrics

## 文件2: backtest/metrics.py
回测指标计算：
- calculate_metrics(equity_curve, trades) -> dict: total_return, annual_return, max_drawdown, sharpe_ratio, win_rate, profit_factor, total_trades, avg_trade_pnl, avg_holding_bars
- print_metrics(metrics): 格式化打印
- format_metrics_table(metrics) -> str: 表格字符串

## 文件3: execution/trade_executor.py
交易执行模块，对接MT5：
- TradeExecutor类:
  - __init__(magic_number=234000, deviation=20)
  - open_position(symbol, direction("BUY"/"SELL"), volume, sl=0.0, tp=0.0, comment="") -> dict
  - close_position(ticket) -> bool: 反向平仓
  - close_all(symbol=None) -> list: 全部平仓
  - modify_position(ticket, sl, tp) -> bool
  - get_positions(symbol=None) -> list[dict]
  - get_position_count() -> int
  - type_filling用mt5.ORDER_FILLING_IOC, BUY取ask价SELL取bid价
  - 完善的错误处理和中文日志

用中文写注释和docstring。代码质量要高，有完整的类型标注。' --allowedTools 'Read,Write' --dangerously-skip-permissions --max-turns 15
echo "=== 任务C完成 ==="
read -n 1
