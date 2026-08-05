from app.schemas.performance_analysis import PerformanceDiagnosis
from app.services.performance_testing.diagnosis_scope import enforce_client_only_scope


def test_scope_rejects_server_root_cause_when_server_monitoring_is_disabled() -> None:
    diagnosis = PerformanceDiagnosis.model_validate(
        {
            "category": "external_service",
            "confidence": 0.9,
            "direct_cause": "LLM 服务端组件等待过长",
            "root_cause": "服务端资源不足导致调用链阻塞",
            "evidence": [],
            "proposed_changes": [],
            "missing_evidence": [],
            "findings": [],
            "recommendations": [],
        }
    )

    sanitized = enforce_client_only_scope(diagnosis)

    assert sanitized.category == "insufficient_evidence"
    assert "服务器" not in sanitized.direct_cause
    assert "服务端" not in sanitized.root_cause
    assert sanitized.can_auto_rerun is False
    assert "server_resource_monitoring" in sanitized.missing_evidence


def test_scope_preserves_script_diagnosis() -> None:
    diagnosis = PerformanceDiagnosis.model_validate(
        {
            "category": "locust_script",
            "confidence": 0.9,
            "direct_cause": "请求体未生成",
            "root_cause": "脚本模板变量未解析",
            "evidence": [],
            "proposed_changes": [],
            "missing_evidence": [],
            "findings": [],
            "recommendations": [],
        }
    )

    assert enforce_client_only_scope(diagnosis) == diagnosis
