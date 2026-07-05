# main.py
"""
量化交易系统 - 程序入口

功能:
    - 根据配置初始化MT4或MT5连接
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
    from core.connector_factory import create_connector
    from monitor.monitor import Monitor

    logger.info("=" * 60)
    logger.info("量化交易系统启动中...")
    logger.info(f"交易平台: {settings.platform.upper()}")
    logger.info("=" * 60)

    # 1. 初始化平台连接器 (根据配置选择MT4或MT5)
    logger.info(f"正在初始化{settings.platform.upper()}连接...")

    if settings.platform == "mt5":
        connector = create_connector("mt5", path=settings.mt5_path)
        logger.info(f"MT5路径: {settings.mt5_path}")
    elif settings.platform == "mt4":
        connector = create_connector(
            "mt4",
            zmq_host=settings.mt4_zmq_host,
            push_host=settings.mt4_zmq_push_host,
        )
        logger.info(f"MT4 ZMQ地址: {settings.mt4_zmq_host}")
    else:
        logger.error(f"不支持的平台: {settings.platform}")
        return

    if not connector.initialize():
        logger.error(f"{settings.platform.upper()}初始化失败，程序退出")
        logger.warning("请检查:")
        if settings.platform == "mt5":
            logger.warning("  1. MT5终端路径是否正确")
            logger.warning("  2. MT5终端是否已打开并登录")
            logger.warning("  3. .env文件中MT5_PATH配置是否正确")
        else:
            logger.warning("  1. MT4终端是否已打开并登录")
            logger.warning("  2. MT4是否已附加ZMQ桥接EA")
            logger.warning("  3. ZMQ端口地址是否正确")
        return

    logger.info(f"{settings.platform.upper()}连接成功")

    # 2. 启动监控服务
    logger.info("正在启动监控服务...")
    monitor = Monitor(connector=connector, interval_seconds=5)
    monitor.start()
    logger.info("监控服务已启动")

    # 3. 将监控实例传递给Web应用
    from web.app import set_monitor, set_connector
    set_monitor(monitor)
    set_connector(connector)

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

        # 关闭连接器
        logger.info(f"关闭{settings.platform.upper()}连接...")
        connector.shutdown()

        logger.info("资源清理完成")
        logger.info("=" * 60)

    atexit.register(cleanup)

    # 5. 启动FastAPI服务
    logger.info("正在启动Web服务...")
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
