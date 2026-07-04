# apps/backend/app/services/page_exploration/locking.py
"""文件级互斥锁: tmp/<file>.lock; acquire 阶段超时抛 LockTimeout。"""
from __future__ import annotations

import os
import time
from pathlib import Path

try:
    import fcntl  # type: ignore[import]

    _USE_FCNTL = True
except ImportError:
    import msvcrt  # type: ignore[import]

    _USE_FCNTL = False


class LockTimeout(Exception):
    """锁等待超时。"""


class FileLock:
    def __init__(self, file_path: Path, timeout_seconds: float = 5.0):
        self._lock_path = Path(str(file_path) + ".lock")
        self._timeout = timeout_seconds
        self._fd = None

    def acquire(self) -> None:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        # Create the lock file with read/write sharing so msvcrt.locking works
        if _USE_FCNTL:
            self._lock_path.touch(exist_ok=True)
            self._fd = open(self._lock_path, "w")
        else:
            lock_str = os.fspath(self._lock_path)
            # os.open with non-exclusive create to avoid Windows access denied
            fd_raw = os.open(lock_str, os.O_CREAT | os.O_RDWR, 0o644)
            self._fd = open(fd_raw, "r+b", closefd=True)
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                if _USE_FCNTL:
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    msvcrt.locking(self._fd.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"timeout acquiring {self._lock_path}")
                time.sleep(0.05)

    def release(self) -> None:
        if self._fd is not None:
            try:
                if _USE_FCNTL:
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                else:
                    msvcrt.locking(self._fd.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self._fd.close()
                self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
