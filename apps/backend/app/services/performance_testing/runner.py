import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

from app.core import settings


def allocate_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


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
    os.kill(process_id, signal.SIGTERM)
