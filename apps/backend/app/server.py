import os

import uvicorn


GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 0.5


def run() -> None:
    reload_enabled = os.getenv("APP_RELOAD", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=18000,
        reload=reload_enabled,
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
    )


if __name__ == "__main__":
    run()
