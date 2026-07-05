# Quant-Trading 量化交易系统设计文档

## 1. 项目概述

基于 MetaTrader 5 的量化交易系统。当前主要交易黄金 (XAUUSD)，架构预留扩展接口，
后期可接入加密货币 (Binance/OKX 等) 或其他交易品种。

## 2. 技术栈

| 层面     | 选型                         |
|----------|------------------------------|
| 语言     | Python 3.11+                 |
| MT5对接  | MetaTrader5 官方Python库      |
| 数据处理 | pandas + numpy               |
| Web后端  | FastAPI + uvicorn            |
| 前端图表 | ECharts 5.x (CDN引入)        |
| 数据存储 | SQLite (内置, 零配置)         |
| 配置管理 | python-dotenv + pydantic     |

## 3. 目录结构

```
Quant-trading/
├── config/
│   └── settings.py          # 全局配置 (MT5路径、交易参数、风控参数)
├── core/
│   ├── mt5_connector.py     # MT5连接管理 (单例, 自动重连)
│   └── base_classes.py      # 抽象基类 (BaseDataSource, BaseStrategy)
├── data/
│   ├── data_fetcher.py      # 行情数据获取 (K线/Tick/盘口)
│   └── data_store.py        # 数据存储与缓存 (SQLite)
├── strategy/
│   ├── base_strategy.py     # 策略基类 + 信号枚举
│   ├── ma_cross.py          # 双均线交叉策略
│   ├── rsi_strategy.py      # RSI超买超卖策略
│   └── bollinger.py         # 布林带策略
├── backtest/
│   ├── backtest_engine.py   # 回测引擎 (事件驱动)
│   └── metrics.py           # 回测指标计算 (收益率/回撤/夏普/胜率)
├── execution/
│   └── trade_executor.py    # 交易执行 (下单/平仓/修改/查询)
├── risk/
│   └── risk_manager.py      # 风控管理 (仓位/止损/日亏损限制)
├── monitor/
│   └── monitor.py           # 实时监控 (账户/持仓/盈亏/策略状态)
├── web/
│   ├── app.py               # FastAPI 主应用 + 路由
│   └── templates/
│       └── index.html       # 前端页面 (ECharts图表)
├── main.py                  # 程序入口
├── .env.example             # 环境变量模板
├── DESIGN.md                # 本文件
└── requirements.txt
```

## 4. 核心设计

### 4.1 MT5 连接管理 (core/mt5_connector.py)

- 单例模式，全局唯一连接
- 自动初始化 (指定 terminal64.exe 路径)
- 连接状态检查 + 自动重连
- 提供 shutdown 方法

MT5 Python API 关键接口:
```python
import MetaTrader5 as mt5

# 初始化
mt5.initialize(path=r"D:\交易盘\DLSM MT5\terminal64.exe")

# 账户信息
mt5.account_info()  # -> namedtuple(login, balance, equity, currency, server, leverage, ...)

# 品种信息
mt5.symbols_get()           # 所有品种
mt5.symbol_info("XAUUSD")   # 单个品种详情
mt5.symbol_info_tick("XAUUSD")  # 最新tick (bid, ask, last, volume)

# K线数据
mt5.copy_rates_from_pos(symbol, timeframe, start, count)
# timeframe: mt5.TIMEFRAME_M1/M5/M15/M30/H1/H4/D1/W1/MN1
# 返回: numpy structured array (time, open, high, low, close, tick_volume, spread)

# 下单
mt5.order_send(request_dict)
# request 关键字段:
#   action: mt5.TRADE_ACTION_DEAL (市价) / TRADE_ACTION_PENDING (挂单)
#   symbol: "XAUUSD"
#   volume: 0.1
#   type: mt5.ORDER_TYPE_BUY / ORDER_TYPE_SELL
#   price: mt5.symbol_info_tick(symbol).ask (买) / .bid (卖)
#   sl: 止损价, tp: 止盈价
#   deviation: 滑点容忍 (点)
#   magic: EA魔术号 (标识策略)
#   comment: "策略备注"
#   type_filling: mt5.ORDER_FILLING_IOC / ORDER_FILLING_FOK / ORDER_FILLING_RETURN
#   type_time: mt5.ORDER_TIME_GTC

# 持仓查询
mt5.positions_get(symbol="XAUUSD")  # 当前持仓
mt5.positions_total()               # 持仓数量

# 历史订单
mt5.history_orders_get(from_date, to_date)
mt5.deals_get(from_date, to_date)

# 关闭
mt5.shutdown()
```

### 4.2 抽象基类 (core/base_classes.py)

```python
from abc import ABC, abstractmethod

class BaseDataSource(ABC):
    """数据源抽象基类 - 预留扩展加密货币等"""
    @abstractmethod
    def get_rates(self, symbol, timeframe, count): ...
    @abstractmethod
    def get_tick(self, symbol): ...

class BaseStrategy(ABC):
    """策略抽象基类"""
    @abstractmethod
    def generate_signals(self, df) -> pd.DataFrame:
        """接收K线DataFrame, 返回带signal列的DataFrame"""
        ...
    @abstractmethod
    def get_params(self) -> dict: ...
```

### 4.3 数据模块 (data/)

- DataFetcher: 封装MT5数据获取, 返回pandas DataFrame
- DataStore: SQLite缓存历史数据, 避免重复拉取
- 列结构: time(datetime), open, high, low, close, tick_volume, spread

### 4.4 策略模块 (strategy/)

所有策略继承 BaseStrategy, 统一接口:
- generate_signals(df) -> df (新增 signal 列: 1=买入, -1=卖出, 0=持有)
- get_params() -> dict (策略参数)

内置三个策略:
1. 双均线交叉 (MA_Cross): fast_period上穿slow_period买入
2. RSI策略 (RSI_Strategy): RSI<oversold买入, RSI>overbought卖出
3. 布林带 (Bollinger): 价格触及下轨买入, 触及上轨卖出

### 4.5 回测模块 (backtest/)

- BacktestEngine: 事件驱动, 逐bar遍历
  - 输入: DataFrame(含signal), 初始资金, 手数, 点差, 手续费
  - 过程: 遇到signal=1开多, signal=-1平仓
  - 输出: BacktestResult(交易记录, 资金曲线, 指标)
- Metrics: 计算总收益率/年化/最大回撤/夏普比率/胜率/盈亏比

### 4.6 执行模块 (execution/)

- TradeExecutor: 封装MT5下单操作
  - open_position(symbol, direction, volume, sl, tp)
  - close_position(ticket)
  - close_all()
  - modify_position(ticket, sl, tp)
  - get_positions()
  - 错误处理: 订单失败重试 + 日志

### 4.7 风控模块 (risk/)

- RiskManager: 交易前风控检查
  - check_position_size(volume, balance) -> bool  仓位检查
  - check_daily_loss() -> bool                     日亏损限制
  - check_max_positions() -> bool                  持仓数量上限
  - calculate_stop_loss(entry, direction, atr)     ATR动态止损
  - calculate_position_size(balance, risk_pct, sl_distance) -> volume  凯利公式简化

### 4.8 监控模块 (monitor/)

- Monitor: 实时监控线程
  - 账户状态 (余额/净值/可用保证金)
  - 持仓明细 (品种/方向/手数/浮盈亏)
  - 策略运行状态
  - 提供 get_status() -> dict 供Web查询

### 4.9 Web界面 (web/)

FastAPI 后端路由:
- GET  /              -> 主页面
- GET  /api/account   -> 账户信息
- GET  /api/positions -> 当前持仓
- GET  /api/rates     -> K线数据 (symbol, timeframe, count)
- POST /api/backtest  -> 执行回测
- GET  /api/strategies -> 可用策略列表
- POST /api/trade     -> 手动下单
- GET  /api/monitor   -> 监控状态

前端 (index.html):
- 单页应用, ECharts画K线图 + 资金曲线
- 策略选择 + 参数配置表单
- 回测结果展示 (指标卡片 + 图表)
- 实时持仓表格

## 5. 扩展性设计

- DataSource 抽象: 后期加 BinanceDataSource 只需实现 get_rates/get_tick
- Strategy 插件式: 新策略继承 BaseStrategy 即可被系统自动发现
- 配置驱动: 品种/参数/风控规则全部在 config/settings.py 配置
- MT5路径、账户信息等敏感数据放 .env 文件

## 6. .env 配置项

```
MT5_PATH=D:\交易盘\DLSM MT5\terminal64.exe
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=
DEFAULT_SYMBOL=XAUUSD
INITIAL_CAPITAL=10000
```
