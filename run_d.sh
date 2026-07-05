#!/bin/bash
cd /d/project/Quant-trading
claude -p '你在 D:\project\Quant-trading 量化交易项目中工作。先读 DESIGN.md 了解整体设计。

你的任务：创建 risk 和 monitor 两个目录下的文件。

## 文件1: risk/risk_manager.py
风控管理模块：
- RiskCheckResult dataclass: passed(bool), reason(str), details(dict)
- RiskManager类:
  - __init__(max_risk_per_trade=0.02, max_daily_loss=0.05, max_positions=5, initial_capital=10000)
  - check_position_size(volume, balance, symbol_info) -> RiskCheckResult
  - check_daily_loss(current_equity, day_start_equity) -> RiskCheckResult
  - check_max_positions(current_count) -> RiskCheckResult
  - check_all(**kwargs) -> RiskCheckResult: 综合检查
  - calculate_stop_loss(entry_price, direction, atr_value, multiplier=2.0) -> float: ATR动态止损
  - calculate_take_profit(entry_price, direction, risk_reward_ratio=2.0, sl_distance) -> float
  - calculate_position_size(balance, risk_percent, sl_distance_points, point_value) -> float
  - update_daily_record(equity): 每日开盘记录净值
  - 所有方法有中文注释和日志

## 文件2: monitor/monitor.py
实时监控模块：
- import threading, time, logging, MetaTrader5 as mt5
- Monitor类:
  - __init__(interval_seconds=5)
  - start(): 启动daemon线程
  - stop(): 停止
  - _run(): 线程主循环
  - get_status() -> dict: {account:{balance,equity,margin,free_margin,margin_level,profit}, positions:[...], position_count, is_running, last_update, connection_ok}
  - get_account_info() -> dict
  - get_positions() -> list[dict]
  - check_connection() -> bool
  - 用threading.Event控制停止

用中文写注释和docstring。代码质量要高，有完整的类型标注。' --allowedTools 'Read,Write' --dangerously-skip-permissions --max-turns 15
echo "=== 任务D完成 ==="
read -n 1
