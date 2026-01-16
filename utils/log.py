"""
日志配置
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from colorama import Fore, Style, init

# 初始化 colorama
init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """用于彩色控制台输出的自定义格式化程序"""

    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, Fore.WHITE)
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"


# 全局控制台处理器
_console_handler = None


def get_logger(category: str = "main") -> logging.Logger:
    """
    获取指定类别的日志记录器，每个类别有独立的日志文件
    参数：
        category: 日志类别，如 "main", "agent", "core", "tool", "error"
    返回值：
        logging.Logger：已配置的日志记录器
    """
    global _console_handler

    logger_name = f"pollex.{category}"
    logger = logging.getLogger(logger_name)

    # 避免重复添加处理器
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # 确保 logs 目录存在
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 为该类别创建文件处理器
        log_file = os.path.join(log_dir, f"{category}.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # 全局只添加一次控制台处理器
        if _console_handler is None:
            _console_handler = logging.StreamHandler(sys.stdout)
            _console_handler.setLevel(logging.INFO)
            console_formatter = ColoredFormatter("%(message)s")
            _console_handler.setFormatter(console_formatter)

        logger.addHandler(_console_handler)

        # 禁止向根记录器传播，避免日志重复
        logger.propagate = False

    return logger


def setup_logger(name: str = "pollex") -> logging.Logger:
    """
    向后兼容的函数，返回主日志记录器
    """
    return get_logger("main")
