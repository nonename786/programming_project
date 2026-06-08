"""
utils/logger.py
日志工具模块 - 统一管理项目日志输出
"""

import sys
from loguru import logger
from pathlib import Path


def setup_logger(log_level: str = "INFO", log_file: str = None) -> None:
    """
    配置日志系统

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径，可选
    """
    # 移除默认的处理器
    logger.remove()

    # 定义日志格式
    format_template = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # 添加控制台输出
    logger.add(
        sys.stdout,
        format=format_template,
        level=log_level,
        colorize=True,
    )

    # 如果指定了日志文件，也写入文件
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            format=format_template,
            level=log_level,
            rotation="10 MB",       # 文件超过10MB时自动轮转
            retention="7 days",      # 保留7天的日志
            compression="zip",      # 压缩旧日志
        )

    logger.info(f"📝 日志系统初始化完成，日志级别: {log_level}")


def get_logger(name: str = None):
    """
    获取日志记录器实例

    Args:
        name: 模块名称，会显示在日志中

    Returns:
        logger实例
    """
    if name:
        return logger.bind(name=name)
    return logger