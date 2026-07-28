import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil

from app.core import settings


def allocate_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = int(listener.getsockname()[1])
        if port == 18000:
            return allocate_loopback_port()
        return port


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def wait_for_loopback_port(port: int, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_port_open(port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Locust 端口 {port} 在 {timeout:g} 秒内未就绪。")


def launch_locust_web_process(run_dir: Path, *, port: int, base_path: str) -> int:
    environment = dict(os.environ)
    environment["AI_TESTING_DB_PATH"] = str(settings.DB_PATH)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "locust",
            "-f",
            "locustfile.py",
            "--web-host",
            "127.0.0.1",
            "--web-port",
            str(port),
            "--web-base-path",
            base_path,
        ],
        cwd=run_dir,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=(run_dir / "stdout.log").open("w", encoding="utf-8"),
        stderr=(run_dir / "stderr.log").open("w", encoding="utf-8"),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return process.pid


def terminate_process(process_id: int) -> None:
    try:
        process = psutil.Process(process_id)
    except psutil.NoSuchProcess:
        return

    processes = [*reversed(process.children(recursive=True)), process]
    for item in processes:
        try:
            item.terminate()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(processes, timeout=5)
