#!/bin/bash
cd /d/project/Quant-trading
claude -p '你在 D:\project\Quant-trading 量化交易项目中工作。先读 DESIGN.md 了解整体设计。

你的任务：创建 web 和主入口文件。

## 文件1: web/app.py
FastAPI Web应用，路由：
- GET / -> index.html
- GET /api/account -> 账户信息
- GET /api/positions -> 当前持仓
- GET /api/rates?symbol=XAUUSD&timeframe=H1&count=200 -> K线JSON
- GET /api/symbols?pattern=XAU -> 品种列表
- GET /api/strategies -> 策略列表
- POST /api/backtest -> 执行回测(symbol, timeframe, strategy_name, params, count)，返回metrics+交易记录+资金曲线
- POST /api/trade -> 手动下单(symbol, direction, volume, sl, tp)
- GET /api/monitor -> 监控状态
- 所有import延迟导入(函数内部)，CORS配置，pydantic BaseModel定义请求体

## 文件2: web/templates/index.html
前端单页面，ECharts CDN(https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js)：
- 深色主题，响应式布局，内联CSS
- 左侧控制面板：品种选择(XAUUSD默认)、周期(M5/M15/H1/H4/D1)、策略选择(双均线/RSI/布林带)、策略参数输入、获取数据按钮、回测按钮、手动下单(买/卖/平仓)
- 右侧图表区：ECharts K线图(candlestick)+成交量副图、买卖信号markPoint、回测资金曲线折线图、指标卡片(总收益率/最大回撤/夏普/胜率)
- 持仓表格(每5秒刷新)
- 原生JS fetch调用API

## 文件3: main.py
程序入口：
- 导入config.settings，初始化MT5连接(core.mt5_connector)，启动monitor.Monitor，启动FastAPI(uvicorn.run)
- 注册atexit清理：关闭MT5，停止监控

用中文写注释和docstring。HTML要完整可运行。' --allowedTools 'Read,Write' --dangerously-skip-permissions --max-turns 20
echo "=== 任务E完成 ==="
read -n 1
