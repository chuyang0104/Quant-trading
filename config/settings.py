# config/settings.py
"""
全局配置模块

使用 pydantic BaseModel 管理系统配置，支持从 .env 文件加载环境变量。
配置项包括: MT5连接、交易参数、风控参数、Web服务等。
"""

import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class Settings(BaseModel):
    """全局配置类 - 系统所有配置参数的单一来源"""

    # ==================== MT5 配置 ====================
    mt5_path: str = Field(
        default=r"D:\交易盘\DLSM MT5\terminal64.exe",
        description="MT5终端完整路径"
    )
    mt5_login: Optional[int] = Field(
        default=None,
        description="MT5账户登录号 (可选)"
    )
    mt5_password: Optional[str] = Field(
        default=None,
        description="MT5账户密码 (可选)"
    )
    mt5_server: Optional[str] = Field(
        default=None,
        description="MT5服务器名称 (可选)"
    )

    # ==================== 交易配置 ====================
    default_symbol: str = Field(
        default="XAUUSD",
        description="默认交易品种"
    )
    default_timeframe: str = Field(
        default="H1",
        description="默认时间周期 (M1/M5/M15/M30/H1/H4/D1/W1/MN1)"
    )
    initial_capital: float = Field(
        default=10000.0,
        ge=0,
        description="初始资金"
    )
    lot_size: float = Field(
        default=0.01,
        gt=0,
        description="默认交易手数"
    )

    # ==================== 风控参数 ====================
    max_risk_per_trade: float = Field(
        default=0.02,
        ge=0,
        le=1,
        description="单笔交易最大风险比例 (占账户净值的比例)"
    )
    max_daily_loss: float = Field(
        default=0.05,
        ge=0,
        le=1,
        description="每日最大亏损比例 (占初始资金的比例)"
    )
    max_positions: int = Field(
        default=5,
        ge=0,
        description="同时持有的最大仓位数量"
    )
    max_drawdown: float = Field(
        default=0.20,
        ge=0,
        le=1,
        description="最大回撤限制 (触发后停止交易)"
    )

    # ==================== Web 配置 ====================
    web_host: str = Field(
        default="127.0.0.1",
        description="Web服务器监听地址"
    )
    web_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Web服务器监听端口"
    )

    # ==================== 日志配置 ====================
    log_level: str = Field(
        default="INFO",
        description="日志级别 (DEBUG/INFO/WARNING/ERROR)"
    )
    log_file: Optional[str] = Field(
        default=None,
        description="日志文件路径 (None 表示只输出到控制台)"
    )

    @field_validator('default_timeframe')
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """验证时间周期参数是否有效"""
        valid_timeframes = {'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1', 'MN1'}
        v_upper = v.upper()
        if v_upper not in valid_timeframes:
            raise ValueError(
                f"无效的timeframe: {v}. "
                f"支持的值: {', '.join(sorted(valid_timeframes))}"
            )
        return v_upper

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别是否有效"""
        v_upper = v.upper()
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if v_upper not in valid_levels:
            raise ValueError(
                f"无效的log_level: {v}. "
                f"支持的值: {', '.join(sorted(valid_levels))}"
            )
        return v_upper

    class Config:
        """Pydantic 配置"""
        env_file = '.env'
        env_file_encoding = 'utf-8'
        extra = 'ignore'  # 忽略 .env 中未定义的字段
        # 使用环境变量时，字段名需要大写
        populate_by_name = True


def load_settings() -> Settings:
    """
    加载并返回配置单例

    优先级:
    1. 环境变量
    2. .env 文件
    3. 代码默认值
    """
    # 尝试加载 .env 文件
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        logger.debug(f"已加载环境配置文件: {env_path.absolute()}")
    else:
        logger.debug("未找到 .env 文件，使用默认配置")

    # 创建并返回配置实例
    settings = Settings()
    logger.info("配置加载完成")
    return settings


# 全局配置单例
settings = load_settings()


if __name__ == "__main__":
    # 配置测试
    print("=" * 50)
    print("配置测试")
    print("=" * 50)
    for key, value in settings.model_dump().items():
        print(f"{key}: {value}")
