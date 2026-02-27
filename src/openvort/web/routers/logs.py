"""运行日志路由"""

import logging
from collections import deque
from datetime import datetime

from fastapi import APIRouter

router = APIRouter()

# 内存日志缓冲区
_log_buffer: deque = deque(maxlen=500)


class WebLogHandler(logging.Handler):
    """将日志写入内存缓冲区，供 Web 面板查询"""

    def emit(self, record: logging.LogRecord):
        _log_buffer.append({
            "id": str(id(record)),
            "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "source": record.name,
            "message": record.getMessage(),
        })


def install_log_handler():
    """安装 Web 日志处理器到根 logger"""
    handler = WebLogHandler()
    handler.setLevel(logging.INFO)
    logging.getLogger("openvort").addHandler(handler)


@router.get("")
async def get_logs(page: int = 1, size: int = 20, level: str = "", keyword: str = ""):
    logs = list(_log_buffer)
    logs.reverse()  # 最新的在前

    if level:
        levels = [l.strip().upper() for l in level.split(",")]
        logs = [l for l in logs if l["level"] in levels]
    if keyword:
        logs = [l for l in logs if keyword.lower() in l["message"].lower()]

    start = (page - 1) * size
    end = start + size
    return {
        "logs": logs[start:end],
        "total": len(logs),
    }
