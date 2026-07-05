# main.py
"""
量化交易系统 - 程序入口

功能:
    - 初始化MT5连接
    - 启动监控服务
    - 启动FastAPI Web服务
    - 注册atexit清理函数
"""

import atexit
import logging
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    # 延迟导入，避免循环依赖
    from config import settings
    from core.mt5_connector import MT5Connector
    from monitor.monitor import Monitor

    logger.info("=" * 60)
    logger.info("量化交易系统启动中...")
    logger.info("=" * 60)

    # 1. 初始化MT5连接
    logger.info(f"正在初始化MT5连接...")
    logger.info(f"MT5路径: {settings.mt5_path}")

    mt5_connector = MT5Connector(path=settings.mt5_path)
    if not mt5_connector.initialize():
        logger.error("MT5初始化失败，程序退出")
        logger.warning("请检查:")
        logger.warning("  1. MT5终端路径是否正确")
        logger.warning("  2. MT5终端是否已安装")
        logger.warning("  3. .env文件中MT5_PATH配置是否正确")
        return

    logger.info("MT5连接成功")

    # 如果配置了登录信息，尝试登录
    if settings.mt5_login and settings.mt5_password:
        logger.info(f"正在登录MT5账户: {settings.mt5_login}")
        # MT5登录需要在initialize时完成，这里仅记录
        logger.info(f"服务器: {settings.mt5_server}")

    # 2. 启动监控服务
    logger.info("正在启动监控服务...")
    monitor = Monitor(interval_seconds=5)
    monitor.start()
    logger.info("监控服务已启动")

    # 3. 将监控实例传递给Web应用
    from web.app import set_monitor
    set_monitor(monitor)

    # 4. 注册清理函数
    def cleanup():
        """程序退出时的清理工作"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("正在清理资源...")

        # 停止监控
        if monitor.is_running:
            logger.info("停止监控服务...")
            monitor.stop()

        # 关闭MT5连接
        logger.info("关闭MT5连接...")
        mt5_connector.shutdown()

        logger.info("资源清理完成")
        logger.info("=" * 60)

    atexit.register(cleanup)

    # 5. 启动FastAPI服务
    logger.info(f"正在启动Web服务...")
    logger.info(f"监听地址: http://{settings.web_host}:{settings.web_port}")

    import uvicorn

    try:
        uvicorn.run(
            "web.app:app",
            host=settings.web_host,
            port=settings.web_port,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
    except Exception as e:
        logger.error(f"Web服务异常: {e}", exc_info=True)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
