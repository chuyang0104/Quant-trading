# web/app.py
"""
FastAPI Web应用

量化交易系统的Web接口，提供账户信息、持仓查询、K线数据、回测等功能。

所有模块使用延迟导入，避免MT5未连接时启动失败。
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用实例
app = FastAPI(
    title="Quant-Trading Web API",
    description="量化交易系统Web接口",
    version="1.0.0"
)

# CORS中间件配置（允许本地调试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模板目录配置
templates = Jinja2Templates(directory="web/templates")


# ==================== Pydantic 数据模型 ====================

class BacktestRequest(BaseModel):
    """回测请求模型"""
    symbol: str = Field(..., description="交易品种，如 XAUUSD")
    timeframe: str = Field(..., description="周期，如 H1")
    strategy_name: str = Field(..., description="策略名称")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略参数")
    count: int = Field(default=500, description="K线数量")


class TradeRequest(BaseModel):
    """手动下单请求模型"""
    symbol: str = Field(..., description="交易品种")
    direction: str = Field(..., description="方向: buy/sell")
    volume: float = Field(..., description="交易手数", gt=0)
    sl: Optional[float] = Field(None, description="止损价")
    tp: Optional[float] = Field(None, description="止盈价")


# ==================== 全局变量（用于缓存） ====================

# 全局监控实例（由main.py启动）
_monitor_instance = None


def set_monitor(monitor):
    """设置全局监控实例（由main.py调用）"""
    global _monitor_instance
    _monitor_instance = monitor


# ==================== 辅助函数（延迟导入） ====================

def _get_mt5():
    """延迟导入MT5模块"""
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


def _get_data_fetcher():
    """延迟导入数据获取器"""
    try:
        from data.data_fetcher import DataFetcher
        return DataFetcher
    except ImportError as e:
        logger.warning(f"DataFetcher导入失败: {e}")
        return None


def _get_backtest_engine():
    """延迟导入回测引擎"""
    try:
        from backtest.backtest_engine import BacktestEngine
        return BacktestEngine
    except ImportError as e:
        logger.warning(f"BacktestEngine导入失败: {e}")
        return None


def _get_strategies():
    """延迟导入策略模块，返回策略字典"""
    try:
        from strategy.ma_cross import MA_Cross
        strategies = {
            "双均线交叉": MA_Cross,
        }
        # 尝试导入其他策略（如果存在）
        try:
            from strategy.rsi_strategy import RSI_Strategy
            strategies["RSI"] = RSI_Strategy
        except ImportError:
            pass
        try:
            from strategy.bollinger import Bollinger
            strategies["布林带"] = Bollinger
        except ImportError:
            pass
        return strategies
    except ImportError as e:
        logger.warning(f"策略模块导入失败: {e}")
        return {}


def _get_trade_executor():
    """延迟导入交易执行器"""
    try:
        from execution.trade_executor import TradeExecutor
        return TradeExecutor
    except ImportError as e:
        logger.warning(f"TradeExecutor导入失败: {e}")
        return None


# ==================== 路由 ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页面"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/account")
async def get_account():
    """
    获取账户信息
    返回: 余额、净值、可用保证金、持仓盈亏等
    """
    mt5 = _get_mt5()
    if not mt5 or not mt5.initialize():
        raise HTTPException(status_code=503, detail="MT5未连接")

    try:
        account = mt5.account_info()
        if account is None:
            raise HTTPException(status_code=503, detail="无法获取账户信息")

        return {
            "success": True,
            "data": {
                "login": account.login,
                "server": account.server,
                "balance": account.balance,
                "equity": account.equity,
                "margin": account.margin,
                "margin_free": account.margin_free,
                "margin_level": account.margin_level if account.margin > 0 else 0,
                "profit": account.profit,
                "currency": account.currency
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取账户信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/positions")
async def get_positions():
    """
    获取当前持仓列表
    """
    mt5 = _get_mt5()
    if not mt5 or not mt5.initialize():
        raise HTTPException(status_code=503, detail="MT5未连接")

    try:
        positions = mt5.positions_get()
        if positions is None:
            positions = []

        result = []
        for pos in positions:
            result.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": pos.type,
                "type_str": "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume": pos.volume,
                "price_open": pos.price_open,
                "price_current": pos.price_current,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
                "comment": pos.comment,
                "magic": pos.magic,
            })

        return {
            "success": True,
            "data": result,
            "count": len(result),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rates")
async def get_rates(
    symbol: str = "XAUUSD",
    timeframe: str = "H1",
    count: int = 200
):
    """
    获取K线数据
    参数:
        symbol: 交易品种
        timeframe: 周期 (M5/M15/H1/H4/D1)
        count: K线数量
    """
    DataFetcher = _get_data_fetcher()
    if not DataFetcher:
        raise HTTPException(status_code=503, detail="数据模块未加载")

    try:
        fetcher = DataFetcher()
        df = fetcher.get_rates(symbol, timeframe, count)

        # 转换为前端可用的格式
        data = []
        for _, row in df.iterrows():
            data.append({
                "time": row["time"].isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row.get("tick_volume", 0))
            })

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "data": data,
            "count": len(data)
        }
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/symbols")
async def get_symbols(pattern: str = ""):
    """
    获取品种列表
    参数:
        pattern: 过滤模式，如 "XAU" 返回包含XAU的品种
    """
    DataFetcher = _get_data_fetcher()
    if not DataFetcher:
        raise HTTPException(status_code=503, detail="数据模块未加载")

    try:
        fetcher = DataFetcher()
        symbols = fetcher.get_available_symbols(pattern)

        return {
            "success": True,
            "data": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        logger.error(f"获取品种列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategies")
async def get_strategies():
    """
    获取可用策略列表
    返回: 策略名称、参数、描述
    """
    strategies = _get_strategies()

    strategy_list = []
    for name, cls in strategies.items():
        try:
            # 创建临时实例获取参数
            temp_instance = cls()
            params = temp_instance.get_params()
            description = getattr(temp_instance, 'description', '')

            # 将参数转换为可展示格式
            param_list = []
            for key, value in params.items():
                param_list.append({
                    "name": key,
                    "value": value,
                    "type": type(value).__name__
                })

            strategy_list.append({
                "name": name,
                "params": param_list,
                "description": description
            })
        except Exception as e:
            logger.warning(f"获取策略 {name} 信息失败: {e}")
            strategy_list.append({
                "name": name,
                "params": [],
                "description": "参数获取失败"
            })

    return {
        "success": True,
        "data": strategy_list
    }


@app.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    """
    执行回测
    接收参数: symbol, timeframe, strategy_name, params, count
    返回: 回测结果（指标 + 交易记录 + 资金曲线）
    """
    DataFetcher = _get_data_fetcher()
    BacktestEngine = _get_backtest_engine()
    strategies = _get_strategies()

    if not DataFetcher or not BacktestEngine:
        raise HTTPException(status_code=503, detail="回测模块未加载")

    if request.strategy_name not in strategies:
        raise HTTPException(status_code=400, detail=f"未知策略: {request.strategy_name}")

    try:
        # 1. 获取数据
        fetcher = DataFetcher()
        df = fetcher.get_rates(request.symbol, request.timeframe, request.count)

        # 2. 实例化策略
        strategy_class = strategies[request.strategy_name]
        strategy = strategy_class(**request.params)

        # 3. 运行回测
        engine = BacktestEngine()
        result = engine.run(df, strategy)

        # 4. 格式化交易记录
        trades_data = []
        for trade in result.trades:
            trades_data.append({
                "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
                "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                "direction": "BUY" if trade.direction == 1 else "SELL",
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "volume": trade.volume,
                "pnl": trade.pnl,
                "pnl_pct": trade.pnl_pct
            })

        # 5. 格式化资金曲线
        equity_data = []
        for idx, value in result.equity_curve.items():
            equity_data.append({
                "time": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                "value": float(value)
            })

        return {
            "success": True,
            "data": {
                "metrics": result.metrics,
                "trades": trades_data,
                "equity_curve": equity_data
            },
            "summary": {
                "total_return": result.metrics.get("total_return", 0),
                "max_drawdown": result.metrics.get("max_drawdown", 0),
                "sharpe_ratio": result.metrics.get("sharpe_ratio", 0),
                "win_rate": result.metrics.get("win_rate", 0),
                "total_trades": result.metrics.get("total_trades", 0)
            }
        }
    except Exception as e:
        logger.error(f"回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trade")
async def manual_trade(request: TradeRequest):
    """
    手动下单
    接收参数: symbol, direction, volume, sl, tp
    """
    TradeExecutor = _get_trade_executor()
    if not TradeExecutor:
        raise HTTPException(status_code=503, detail="交易执行模块未加载")

    try:
        executor = TradeExecutor()

        if request.direction.upper() == "BUY":
            result = executor.open_position(
                symbol=request.symbol,
                direction="BUY",
                volume=request.volume,
                sl=request.sl or 0.0,
                tp=request.tp or 0.0
            )
        elif request.direction.upper() == "SELL":
            result = executor.open_position(
                symbol=request.symbol,
                direction="SELL",
                volume=request.volume,
                sl=request.sl or 0.0,
                tp=request.tp or 0.0
            )
        else:
            raise HTTPException(status_code=400, detail="无效的方向，应为 BUY 或 SELL")

        return {
            "success": result.get("success", False),
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"下单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor")
async def get_monitor_status():
    """
    获取监控状态
    返回: 账户状态、持仓统计、策略运行状态
    """
    if _monitor_instance is None:
        return {
            "success": True,
            "data": {
                "is_running": False,
                "message": "监控未启动"
            },
            "timestamp": datetime.now().isoformat()
        }

    try:
        status = _monitor_instance.get_status()
        return {
            "success": True,
            "data": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    mt5 = _get_mt5()
    mt5_connected = False
    if mt5:
        try:
            mt5_connected = mt5.initialize()
        except:
            pass

    return {
        "status": "healthy" if mt5_connected else "degraded",
        "mt5_connected": mt5_connected,
        "monitor_running": _monitor_instance is not None and _monitor_instance.is_running,
        "timestamp": datetime.now().isoformat()
    }


# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("FastAPI应用启动")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    logger.info("FastAPI应用关闭")
