from typing import Literal

from pydantic import BaseModel


class ReportCenterItemOut(BaseModel):
    id: str
    report_type: Literal["performance", "api"]
    project_id: str
    project_name: str
    test_id: str = ""
    test_name: str = ""
    run_id: str = ""
    analysis_id: str = ""
    analysis_version: int = 0
    name: str
    status: Literal["collecting", "analyzing", "completed", "failed"]
    generation_mode: str = ""
    generation_status: Literal["generating", "generated", "degraded", "failed"] = "generating"
    verdict: Literal["pass", "conditional_pass", "fail", "indeterminate"]
    quality_status: Literal["complete", "partial", "invalid"]
    environment_name: str = ""
    scenario_count: int = 0
    passed_count: int = 0
    pass_rate: float = 0
    error_message: str
    created_at: str
    updated_at: str
    href: str
