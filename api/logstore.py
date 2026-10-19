"""进程内日志环形缓冲，供 /logs 页面查看。

注意：日志保存在内存里，进程重启后清空；多进程部署时各进程各有一份。
"""
import threading
from collections import deque
from datetime import datetime

MAX_LOGS = 200

_logs = deque(maxlen=MAX_LOGS)
_lock = threading.Lock()
_seq = 0


def add(level, message, **extra):
    """追加一条日志。level: info / warn / error。"""
    global _seq
    with _lock:
        _seq += 1
        _logs.append({
            "id": _seq,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            **extra,
            "message": message,
        })


def all():
    with _lock:
        return list(_logs)
