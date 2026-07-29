from dataclasses import dataclass

from app.agents.capabilities import list_ai_capabilities


@dataclass(frozen=True)
class AgentEmployeeMetadata:
    display_name: str
    role: str
    department_id: str
    department_name: str
    accent_color: str
    avatar_asset: str
    workstation_variant: str
    seat_code: str
    task_source_types: tuple[str, ...] = ()


EMPLOYEE_METADATA: dict[str, AgentEmployeeMetadata] = {
    "document_editor": AgentEmployeeMetadata(
        display_name="林悦",
        role="文档编辑师",
        department_id="requirement",
        department_name="需求工程组",
        accent_color="#4f7cff",
        avatar_asset="female-yujie-plum",
        workstation_variant="female-cream",
        seat_code="REQ-01",
    ),
    "requirement_standardization": AgentEmployeeMetadata(
        display_name="王芳",
        role="需求标准化专员",
        department_id="requirement",
        department_name="需求工程组",
        accent_color="#8b6fd8",
        avatar_asset="female-yujie-red",
        workstation_variant="female-cream",
        seat_code="REQ-02",
        task_source_types=("requirement_file",),
    ),
    "requirement_analysis": AgentEmployeeMetadata(
        display_name="张静",
        role="需求分析师",
        department_id="requirement",
        department_name="需求工程组",
        accent_color="#e85d4a",
        avatar_asset="female-yujie-emerald",
        workstation_variant="female-cream",
        seat_code="REQ-03",
        task_source_types=("requirement_analysis_run", "requirement_finalization_run"),
    ),
    "knowledge_query": AgentEmployeeMetadata(
        display_name="杨帆",
        role="知识研究员",
        department_id="test-design",
        department_name="测试设计组",
        accent_color="#18a589",
        avatar_asset="male-handsome-green",
        workstation_variant="male-white",
        seat_code="TST-01",
    ),
    "test_case_generation": AgentEmployeeMetadata(
        display_name="张伟",
        role="测试用例设计师",
        department_id="test-design",
        department_name="测试设计组",
        accent_color="#d5952f",
        avatar_asset="male-handsome-charcoal",
        workstation_variant="male-gray",
        seat_code="TST-02",
        task_source_types=("test_case_generation_run",),
    ),
    "test_point_generation": AgentEmployeeMetadata(
        display_name="周燕",
        role="测试点设计师",
        department_id="test-design",
        department_name="测试设计组",
        accent_color="#9b6dd7",
        avatar_asset="female-yujie-plum",
        workstation_variant="female-cream",
        seat_code="TST-03",
        task_source_types=("test_point_generation_run",),
    ),
    "api_test_generation": AgentEmployeeMetadata(
        display_name="孙娜",
        role="API 测试设计师",
        department_id="automation",
        department_name="自动化工程组",
        accent_color="#f97316",
        avatar_asset="female-yujie-red",
        workstation_variant="female-cream",
        seat_code="AUT-01",
        task_source_types=("api_automation_generation_run",),
    ),
    "api_scenario_orchestration": AgentEmployeeMetadata(
        display_name="郑凯",
        role="API 场景编排师",
        department_id="automation",
        department_name="自动化工程组",
        accent_color="#df574c",
        avatar_asset="male-handsome-camel",
        workstation_variant="male-gray",
        seat_code="AUT-02",
        task_source_types=("api_script_generation_run", "api_automation_run"),
    ),
    "ui_test_generation": AgentEmployeeMetadata(
        display_name="陈燕",
        role="UI 自动化工程师",
        department_id="automation",
        department_name="自动化工程组",
        accent_color="#e2ad2e",
        avatar_asset="female-yujie-plum",
        workstation_variant="female-cream",
        seat_code="AUT-03",
        task_source_types=("ui_automation_generation_run", "ui_automation_run"),
    ),
    "page_exploration": AgentEmployeeMetadata(
        display_name="刘洋",
        role="站点探索员",
        department_id="operations",
        department_name="运行与分析组",
        accent_color="#4a90d9",
        avatar_asset="male-handsome-camel",
        workstation_variant="male-white",
        seat_code="OPS-01",
        task_source_types=("exploration_run",),
    ),
    "performance_script_generation": AgentEmployeeMetadata(
        display_name="唐宇",
        role="性能脚本工程师",
        department_id="operations",
        department_name="运行与分析组",
        accent_color="#3f8f75",
        avatar_asset="male-handsome-charcoal",
        workstation_variant="male-white",
        seat_code="OPS-02",
        task_source_types=("performance_script_generation_run", "performance_test_run"),
    ),
    "performance_report_analysis": AgentEmployeeMetadata(
        display_name="彭宇",
        role="性能分析师",
        department_id="operations",
        department_name="运行与分析组",
        accent_color="#4ecdc4",
        avatar_asset="male-handsome-camel",
        workstation_variant="male-gray",
        seat_code="OPS-03",
        task_source_types=("performance_analysis_run",),
    ),
}


def list_agent_employees() -> list[dict]:
    employees: list[dict] = []
    department_seat_indexes: dict[str, int] = {}
    for capability in list_ai_capabilities():
        metadata = EMPLOYEE_METADATA[capability.id]
        seat_index = department_seat_indexes.get(metadata.department_id, 0)
        department_seat_indexes[metadata.department_id] = seat_index + 1
        employees.append(
            {
                "id": capability.id,
                "name": metadata.role,
                "display_name": metadata.display_name,
                "role": metadata.role,
                "capability_name": capability.name,
                "description": capability.description,
                "department": metadata.department_name,
                "department_id": metadata.department_id,
                "department_name": metadata.department_name,
                "accent_color": metadata.accent_color,
                "avatar_asset": metadata.avatar_asset,
                "workstation_variant": metadata.workstation_variant,
                "seat_code": metadata.seat_code,
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
