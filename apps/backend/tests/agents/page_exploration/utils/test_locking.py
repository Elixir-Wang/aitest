# apps/backend/tests/agents/page_exploration/utils/test_locking.py
import threading
import time
from pathlib import Path

import pytest

from app.services.page_exploration.locking import FileLock, LockTimeout


def test_acquire_and_release(tmp_path: Path):
    path = tmp_path / "page.yaml"
    path.write_text("schema_version: 2.0\n")
    lock = FileLock(path, timeout_seconds=1.0)
    with lock:
        assert path.exists()  # lock file 不会冲突路径
    # 再次获取应成功
    with lock:
        pass


def test_concurrent_acquire_waits_then_times_out(tmp_path: Path):
    path = tmp_path / "page.yaml"
    path.write_text("schema_version: 2.0\n")
    a = FileLock(path, timeout_seconds=0.5)
    b = FileLock(path, timeout_seconds=0.2)
    with a:
        with pytest.raises(LockTimeout):
            with b:
                pass


def test_acquired_lock_blocks_other_writers(tmp_path: Path):
    path = tmp_path / "page.yaml"
    path.write_text("x")
    a = FileLock(path, timeout_seconds=1.0)
    b = FileLock(path, timeout_seconds=2.0)
    with a:
        t0 = time.monotonic()
        try:
            with b:
                pass
        except LockTimeout:
            elapsed = time.monotonic() - t0
        else:
            pytest.fail("b should not have acquired during a's hold")


def test_release_unlocks(tmp_path: Path):
    path = tmp_path / "page.yaml"
    path.write_text("x")
    a = FileLock(path, timeout_seconds=0.5)
    a.acquire()
    try:
        # 释放后再获取应成功
        a.release()
        a.acquire()
    finally:
        a.release()


def test_raise_class_exists():
    from app.services.page_exploration.locking import LockTimeout

    assert issubclass(LockTimeout, Exception)
