from typing import Literal

from pydantic import BaseModel, Field


DecisionType = Literal["act", "record", "back", "skip", "finish", "block"]
AgenticActionType = Literal[
    "navigate",
    "click",
    "fill",
    "select_option",
    "press",
    "close_modal",
    "go_back",
    "wait",
    "record_state",
]
RiskLevel = Literal["safe", "guarded", "destructive"]


class AgenticExplorationInput(BaseModel):
    run: dict = Field(default_factory=dict)
    budget: dict = Field(default_factory=dict)
    history_summary: str = ""
    current_observation: dict = Field(default_factory=dict)


class AgenticAction(BaseModel):
    type: AgenticActionType
    target_element_id: str = ""
    value: str = ""
    url: str = ""
    key: str = ""
    intent: str = ""


class AgenticRisk(BaseModel):
    level: RiskLevel = "safe"
    reason: str = ""


class AgenticCoverageIntent(BaseModel):
    module: str = ""
    page_or_state: str = ""
    goal_fragment: str = ""


class AgenticDecisionOutput(BaseModel):
    decision_type: DecisionType
    action: AgenticAction | None = None
    reason: str = Field(min_length=1)
    expected_result: str = ""
    risk: AgenticRisk = Field(default_factory=AgenticRisk)
    coverage_intent: AgenticCoverageIntent = Field(default_factory=AgenticCoverageIntent)
