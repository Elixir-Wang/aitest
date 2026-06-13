def terminate(run_id: str) -> bool:
    """Terminate external work for a v3 requirement analysis run.

    The v3 workflow runs in-process and observes cancellation through run status,
    so there is no child process to terminate.
    """

    return False
