"""
统一日志配置
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """配置全局日志格式"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # 抑制 httpx 的请求日志刷屏
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger"""
    return logging.getLogger(f"openvort.{name}")
