from dataclasses import dataclass

from app.agents.capabilities import list_ai_capabilities


@dataclass(frozen=True)
class AgentEmployeeMetadata:
    title: str
    department: str
    accent_color: str
    task_source_types: tuple[str, ...] = ()


EMPLOYEE_METADATA: dict[str, AgentEmployeeMetadata] = {
    "document_editor": AgentEmployeeMetadata(
        title="文档编辑师",
        department="需求工程",
        accent_color="#4f7cff",
    ),
    "requirement_standardization": AgentEmployeeMetadata(
        title="需求标准化专员",
        department="需求工程",
        accent_color="#8b6fd8",
        task_source_types=("requirement_file",),
    ),
    "requirement_analysis": AgentEmployeeMetadata(
        title="需求分析师",
        department="需求工程",
        accent_color="#e85d4a",
        task_source_types=("requirement_analysis_run", "requirement_finalization_run"),
    ),
    "knowledge_query": AgentEmployeeMetadata(
        title="知识研究员",
        department="测试设计",
        accent_color="#18a589",
    ),
    "test_case_generation": AgentEmployeeMetadata(
        title="测试用例设计师",
        department="测试设计",
        accent_color="#d5952f",
        task_source_types=("test_case_generation_run",),
    ),
    "test_point_generation": AgentEmployeeMetadata(
        title="测试点设计师",
        department="测试设计",
        accent_color="#9b6dd7",
        task_source_types=("test_point_generation_run",),
    ),
    "api_test_generation": AgentEmployeeMetadata(
        title="API 测试设计师",
        department="自动化工程",
        accent_color="#f97316",
        task_source_types=("api_automation_generation_run",),
    ),
    "api_scenario_orchestration": AgentEmployeeMetadata(
        title="API 场景编排师",
        department="自动化工程",
        accent_color="#df574c",
        task_source_types=("api_script_generation_run", "api_automation_run"),
    ),
    "ui_test_generation": AgentEmployeeMetadata(
        title="UI 自动化工程师",
        department="自动化工程",
        accent_color="#e2ad2e",
        task_source_types=("ui_automation_generation_run", "ui_automation_run"),
    ),
    "page_exploration": AgentEmployeeMetadata(
        title="站点探索员",
        department="运行与分析",
        accent_color="#4a90d9",
        task_source_types=("exploration_run",),
    ),
    "performance_script_generation": AgentEmployeeMetadata(
        title="性能脚本工程师",
        department="运行与分析",
        accent_color="#3f8f75",
        task_source_types=("performance_script_generation_run", "performance_test_run"),
    ),
    "performance_report_analysis": AgentEmployeeMetadata(
        title="性能分析师",
        department="运行与分析",
        accent_color="#4ecdc4",
        task_source_types=("performance_analysis_run",),
    ),
}


def list_agent_employees() -> list[dict]:
    employees: list[dict] = []
    for seat_index, capability in enumerate(list_ai_capabilities()):
        metadata = EMPLOYEE_METADATA[capability.id]
        employees.append(
            {
                "id": capability.id,
                "name": metadata.title,
                "capability_name": capability.name,
                "description": capability.description,
                "department": metadata.department,
                "accent_color": metadata.accent_color,
                "task_source_types": list(metadata.task_source_types),
                "seat_index": seat_index,
                "registered": True,
            }
        )
    return employees


def validate_employee_registry() -> None:
    capability_ids = {capability.id for capability in list_ai_capabilities()}
    metadata_ids = set(EMPLOYEE_METADATA)
    if capability_ids != metadata_ids:
        missing = sorted(capability_ids - metadata_ids)
        extra = sorted(metadata_ids - capability_ids)
        raise ValueError(f"智能体员工注册表不完整：missing={missing}, extra={extra}")


validate_employee_registry()
