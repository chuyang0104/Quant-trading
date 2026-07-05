#!/bin/bash
cd /d/project/Quant-trading
claude -p '你在 D:\project\Quant-trading 量化交易项目中工作。先读 DESIGN.md 了解整体设计。

你的任务：创建 config 和 core 两个目录下的文件。

## 文件1: config/settings.py
全局配置类，使用 pydantic BaseModel：
- MT5配置: mt5_path(默认r"D:\交易盘\DLSM MT5\terminal64.exe"), mt5_login(int), mt5_password(str), mt5_server(str)
- 交易配置: default_symbol(默认XAUUSD), default_timeframe(默认H1), initial_capital(默认10000)
- 风控参数: max_risk_per_trade(0.02), max_daily_loss(0.05), max_positions(5)
- Web配置: web_host(127.0.0.1), web_port(8000)
- 从.env文件加载(用python-dotenv的load_dotenv)
- 提供一个全局单例 settings = Settings()

## 文件2: core/mt5_connector.py
MT5连接管理，单例模式：
- import MetaTrader5 as mt5
- MT5Connector类: __init__接收path参数
- initialize(): 调用mt5.initialize(path=...)，失败则打印last_error
- ensure_connected(): 检查连接状态，断开则自动重连
- shutdown(): 调用mt5.shutdown()
- is_connected属性
- 全局单例函数 get_connector() -> MT5Connector
- 所有方法要有中文日志输出(logging)

## 文件3: core/base_classes.py
抽象基类：
- BaseDataSource(ABC): get_rates(symbol, timeframe, count), get_tick(symbol) 抽象方法
- BaseStrategy(ABC):
  - generate_signals(self, df) -> df 抽象方法 (df新增signal列: 1=买, -1=卖, 0=持有)
  - get_params(self) -> dict 抽象方法
  - name属性

用中文写注释和docstring。代码质量要高，有完整的类型标注。' --allowedTools 'Read,Write' --dangerously-skip-permissions --max-turns 15
echo "=== 任务A完成 ==="
read -n 1
