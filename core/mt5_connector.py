# core/mt5_connector.py
"""
MT5 连接管理模块

提供 MT5 终端连接的单例管理，支持:
- 自动初始化和连接
- 连接状态检查和自动重连
- 优雅关闭
"""

import logging
import threading
from typing import Optional

try:
    import MetaTrader5 as mt5
except ImportError:
    raise ImportError(
        "未安装 MetaTrader5 库，请运行: pip install MetaTrader5"
    )

logger = logging.getLogger(__name__)


class MT5Connector:
    """
    MT5 连接管理器 - 单例模式

    负责与 MT5 终端的连接管理，提供:
    - 连接初始化
    - 连接状态检查
    - 自动重连
    - 优雅关闭
    """

    _instance: Optional['MT5Connector'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """确保单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, path: Optional[str] = None):
        """
        初始化 MT5 连接管理器

        Args:
            path: MT5 terminal64.exe 的完整路径
        """
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._path = path
        self._connected = False
        self._initialized = True
        logger.info(f"MT5连接管理器已创建, 路径: {path or '默认'}")

    def initialize(self) -> bool:
        """
        初始化 MT5 连接

        Returns:
            bool: 连接是否成功
        """
        if self._connected:
            logger.debug("MT5 已经连接，跳过初始化")
            return True

        try:
            # 调用 MT5 初始化
            if self._path:
                result = mt5.initialize(path=self._path)
            else:
                result = mt5.initialize()

            if not result:
                error_code = mt5.last_error()
                logger.error(f"MT5 初始化失败: {error_code}")
                self._connected = False
                return False

            self._connected = True
            logger.info("MT5 连接初始化成功")

            # 打印 MT5 版本信息
            version_info = mt5.version()
            logger.info(
                f"MT5 版本: {version_info.build} "
                f"(发布于 {version_info.date})"
            )

            return True

        except Exception as e:
            logger.error(f"MT5 初始化异常: {e}", exc_info=True)
            self._connected = False
            return False

    def ensure_connected(self) -> bool:
        """
        确保连接状态，断线时自动重连

        Returns:
            bool: 当前是否已连接
        """
        if not self._connected:
            logger.warning("检测到 MT5 未连接，尝试重新连接...")
            return self.initialize()

        # 验证连接是否仍然有效
        try:
            # 尝试获取账户信息来验证连接
            account = mt5.account_info()
            if account is None:
                self._connected = False
                logger.warning("MT5 连接已断开，尝试重新连接...")
                return self.initialize()
        except Exception as e:
            self._connected = False
            logger.error(f"验证连接状态时出错: {e}")
            return self.initialize()

        return True

    def shutdown(self) -> bool:
        """
        关闭 MT5 连接

        Returns:
            bool: 关闭是否成功
        """
        try:
            if self._connected:
                mt5.shutdown()
                self._connected = False
                logger.info("MT5 连接已关闭")
                return True
            else:
                logger.debug("MT5 未连接，无需关闭")
                return True
        except Exception as e:
            logger.error(f"关闭 MT5 连接时出错: {e}", exc_info=True)
            return False

    @property
    def is_connected(self) -> bool:
        """
        当前连接状态

        Returns:
            bool: 是否已连接
        """
        return self._connected

    def __enter__(self):
        """支持上下文管理器协议"""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议"""
        self.shutdown()

    def __repr__(self) -> str:
        return f"<MT5Connector connected={self._connected} path={self._path}>"


# 全局连接器单例
_connector: Optional[MT5Connector] = None
_connector_lock = threading.Lock()


def get_connector(path: Optional[str] = None) -> MT5Connector:
    """
    获取 MT5 连接器单例

    Args:
        path: MT5 terminal64.exe 的完整路径 (首次调用时有效)

    Returns:
        MT5Connector: 全局唯一的连接器实例
    """
    global _connector

    if _connector is None:
        with _connector_lock:
            if _connector is None:
                _connector = MT5Connector(path=path)
                logger.info("创建全局 MT5 连接器单例")

    return _connector


def reset_connector() -> None:
    """
    重置全局连接器 (主要用于测试)

    注意: 会先关闭现有连接
    """
    global _connector

    with _connector_lock:
        if _connector is not None:
            _connector.shutdown()
            _connector = None
            logger.info("全局 MT5 连接器已重置")


if __name__ == "__main__":
    # 配置日志用于测试
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 50)
    print("MT5 连接器测试")
    print("=" * 50)

    # 使用上下文管理器
    with MT5Connector(path=r"D:\交易盘\DLSM MT5\terminal64.exe") as conn:
        print(f"连接状态: {conn.is_connected}")
        if conn.is_connected:
            # 获取账户信息
            account = mt5.account_info()
            if account:
                print(f"账户: {account.login}")
                print(f"服务器: {account.server}")
                print(f"余额: {account.balance}")
                print(f"净值: {account.equity}")
