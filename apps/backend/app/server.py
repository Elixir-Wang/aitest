import uvicorn


GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 0


def run() -> None:
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
    )


if __name__ == "__main__":
    run()
