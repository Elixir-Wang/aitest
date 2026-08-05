from __future__ import annotations

import re

from app.schemas.performance_analysis import PerformanceDiagnosis


_SERVER_ATTRIBUTION_PATTERN = re.compile(
    r"服务端资源|服务端组件|服务端瓶颈|服务端调用链|服务器资源|服务器瓶颈|下游依赖|"
    r"数据库连接|连接池|CPU|内存|线程池|server\.resource|resource_correlation|backend bottleneck",
    re.IGNORECASE,
)


def enforce_client_only_scope(diagnosis: PerformanceDiagnosis) -> PerformanceDiagnosis:
    texts = [diagnosis.direct_cause, diagnosis.root_cause]
    texts.extend(
        str(item.get(field) or "")
        for item in diagnosis.model_dump(mode="json").get("evidence", [])
        for field in ("title", "detail", "reference")
    )
    texts.extend(
        str(item.get(field) or "")
        for item in diagnosis.model_dump(mode="json").get("findings", [])
        for field in ("title", "statement", "alternative_hypotheses")
    )
    texts.extend(
        str(item.get(field) or "")
        for item in diagnosis.model_dump(mode="json").get("recommendations", [])
        for field in ("action", "expected_effect", "verification")
    )
    if not any(_SERVER_ATTRIBUTION_PATTERN.search(text) for text in texts):
        return diagnosis
    return PerformanceDiagnosis.model_validate(
        {
            "category": "insufficient_evidence",
            "confidence": min(float(diagnosis.confidence), 0.35),
            "direct_cause": "当前仅能确认压测窗口内的指标表现，不能进行未采集目标的根因归因。",
            "root_cause": "当前证据仅覆盖压测客户端与接口观测，应优先检查脚本请求构造、等待逻辑和计时口径。",
            "evidence": [],
            "proposed_changes": [],
            "missing_evidence": [
                "server_resource_monitoring",
                "script_execution_timing",
            ],
            "requires_second_approval": False,
            "can_auto_rerun": False,
            "findings": [],
            "recommendations": [],
        }
    )


__all__ = ["enforce_client_only_scope"]
