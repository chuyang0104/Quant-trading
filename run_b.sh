#!/bin/bash
cd /d/project/Quant-trading
claude -p '你在 D:\project\Quant-trading 量化交易项目中工作。先读 DESIGN.md 了解整体设计。

你的任务：创建 data 和 strategy 两个目录下的文件。

## 文件1: data/data_fetcher.py
行情数据获取，继承core.base_classes.BaseDataSource：
- import MetaTrader5 as mt5, pandas as pd, numpy as np
- DataFetcher类继承BaseDataSource
- get_rates(symbol, timeframe, count=500) -> pd.DataFrame: 调用mt5.copy_rates_from_pos拉K线，返回DataFrame列: time(datetime), open, high, low, close, tick_volume, spread
- get_rates_range(symbol, timeframe, start_dt, end_dt) -> pd.DataFrame: 用mt5.copy_rates_range
- get_tick(symbol) -> dict: 返回最新bid/ask/last/volume
- get_symbol_info(symbol) -> dict: 品种信息(point, digits, volume_min, volume_max, volume_step, trade_contract_size等)
- get_available_symbols(pattern="") -> list: 可用品种列表，支持模糊匹配
- TIMEFRAME_MAP字典: {"M1":mt5.TIMEFRAME_M1, "M5":mt5.TIMEFRAME_M5, "M15":mt5.TIMEFRAME_M15, "H1":mt5.TIMEFRAME_H1, "H4":mt5.TIMEFRAME_H4, "D1":mt5.TIMEFRAME_D1}
- 所有方法先检查MT5连接(从core.mt5_connector导入get_connector)

## 文件2: data/data_store.py
SQLite数据存储：
- DataStore类: __init__(db_path="quant.db")
- save_rates(symbol, timeframe, df): 存K线数据(用INSERT OR REPLACE)
- load_rates(symbol, timeframe, start, end) -> pd.DataFrame: 读历史数据
- create_table(): 建表(rates表: symbol, timeframe, time, open, high, low, close, tick_volume, spread, 主键symbol+timeframe+time)

## 文件3: strategy/base_strategy.py
策略基类(继承core.base_classes.BaseStrategy)：
- 添加name属性(策略名称)
- 添加description属性
- calculate_indicators(self, df) -> df 抽象方法

## 文件4: strategy/ma_cross.py
双均线交叉策略(MA_Cross)：参数fast_period(10), slow_period(30)，EMA计算，金叉买入死叉卖出，name="双均线交叉"

## 文件5: strategy/rsi_strategy.py
RSI策略(RSI_Strategy)：参数period(14), oversold(30), overbought(70)，name="RSI超买超卖"

## 文件6: strategy/bollinger.py
布林带策略(Bollinger)：参数period(20), num_std(2.0)，name="布林带"

用中文写注释和docstring。代码质量要高，有完整的类型标注。' --allowedTools 'Read,Write' --dangerously-skip-permissions --max-turns 15
echo "=== 任务B完成 ==="
read -n 1
