from __future__ import annotations

from pydantic import BaseModel


class DashboardMetricOut(BaseModel):
    label: str
    value: str
    helper: str


class DashboardTrendPointOut(BaseModel):
    date: str
    caseAssets: int
    adoptedCases: int
    automationCases: int


class DashboardOut(BaseModel):
    scope: str
    project_id: str | None = None
    project_name: str | None = None
    metrics: list[DashboardMetricOut]
    trend: list[DashboardTrendPointOut]

