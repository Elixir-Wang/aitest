# 需求分析 v3

当前需求分析运行链路只保留 v3 LangGraph 工作流。

## 入口

- `app.services.document.service` 构造 `app.agents.requirement_analysis.schemas.RequirementAnalysisWorkflowInput`
- `app.agents.requirement_analysis.v3.workflow.run_requirement_analysis_v3` 编排完整流程

## 结构

```text
app/agents/requirement_analysis/
├── schemas.py
├── utils/
└── v3/
    ├── workflow.py
    ├── state.py
    ├── agents/
    │   ├── analysis.py
    │   └── search.py
    ├── nodes/
    │   ├── understand_node.py
    │   ├── quality_node.py
    │   ├── clarify_node.py
    │   └── enhance_node.py
    ├── services/
    │   └── auxiliary_search_service.py
    └── tools/
        └── search_auxiliary.py
```

## 流程

1. `understand_node`：提取结构化需求理解。
2. `quality_node`：评估完整性、清晰度、可测试性和一致性。
3. `clarify_node`：对需要澄清的问题执行辅助文档搜索。
4. `enhance_node`：生成分析报告和增强版需求。

高质量且已批准的需求会跳过澄清节点，直接进入增强节点。
