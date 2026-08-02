import threading

from app.services.api_automation.orchestration_job_runner import OrchestrationJobRunner


def test_submit_allows_work_keyword_named_plan_id() -> None:
    runner = OrchestrationJobRunner(max_workers=1)
    completed = threading.Event()

    def work(*, plan_id: str) -> None:
        assert plan_id == "plan-1"
        completed.set()

    try:
        assert runner.submit("plan-1", work, plan_id="plan-1") is True
        assert completed.wait(timeout=1)
    finally:
        runner.shutdown()
