from typing import Literal

from pydantic import BaseModel


class ReportCenterItemOut(BaseModel):
    id: str
    report_type: Literal["performance"]
    project_id: str
    project_name: str
    test_id: str
    test_name: str
    run_id: str
    analysis_id: str
    analysis_version: int
    name: str
    status: Literal["collecting", "analyzing", "completed", "failed"]
    generation_mode: str = ""
    generation_status: Literal["generating", "generated", "degraded", "failed"] = "generating"
    verdict: Literal["pass", "conditional_pass", "fail", "indeterminate"]
    quality_status: Literal["complete", "partial", "invalid"]
    error_message: str
    created_at: str
    updated_at: str
    href: str
