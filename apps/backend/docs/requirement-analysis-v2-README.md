# 需求分析系统 v2.0 - 使用说明

## 🎉 编码完成

需求分析系统 v2.0 已完全实现，包含所有核心功能、测试和文档。

---

## 📦 已实现的文件

### 核心模块
- ✅ `schemas_v2.py` - 完整的 Pydantic 数据模型（532行）
- ✅ `agent_v2.py` - 三个 Agent 实现（690行）
- ✅ `service_v2.py` - 业务逻辑服务层（180行）
- ✅ `router_v2.py` - FastAPI 路由定义（180行）

### 工具模块
- ✅ `utils/priority_sorter.py` - 优先级排序工具（120行）
- ✅ `utils/report_generator.py` - Markdown 报告生成（320行）

### 测试
- ✅ `tests/test_schemas_v2.py` - 单元测试（280行）
- ✅ `tests/test_integration_v2.py` - 集成测试（180行）

### 文档
- ✅ `requirement-analysis-architecture.md` - 架构设计文档
- ✅ `requirement-analysis-v2-guide.md` - 快速上手指南
- ✅ `requirement-analysis-v2-workflow.md` - 详细流程说明
- ✅ `requirement-analysis-v2-spec.md` - 技术规格文档

**总代码量**: ~2,600 行代码 + ~2,000 行文档

---

## 🚀 快速开始

### 1. 安装依赖

```powershell
cd apps\backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```powershell
# 设置 Anthropic API Key
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. 运行测试

```powershell
# 运行单元测试
pytest tests\agents\requirement_analysis\test_schemas_v2.py -v

# 运行所有测试
pytest tests\agents\requirement_analysis\ -v
```

### 4. 使用代码示例

```python
from app.agents.requirement_analysis.service_v2 import analyze_requirement_v2

# 准备需求文档
requirement_content = """
# 订单管理模块

用户可以创建订单。订单创建后状态为"待支付"。
用户支付成功后，订单状态变为"已支付"。
订单金额大于1000元时，需要经理审批。
系统应当快速响应用户操作。
"""

# 执行分析
result = await analyze_requirement_v2(
    model=your_llm_model,  # 需要提供 LLM 模型
    primary_markdown_content=requirement_content,
)

# 查看结果
print(f"状态: {result.status}")
print(f"质量评分: {result.quality_assessment.scores.overall}/100")
print(f"待澄清问题: {result.clarification.summary.needs_manual} 个")
```

---

## 📋 API 使用

### 启动 FastAPI 服务

```powershell
cd apps\backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 调用 API

```powershell
# 健康检查
curl http://localhost:8000/api/requirement-analysis/v2/health

# 获取默认配置
curl http://localhost:8000/api/requirement-analysis/v2/config

# 执行分析
curl -X POST http://localhost:8000/api/requirement-analysis/v2/analyze `
  -H "Content-Type: application/json" `
  -d @request.json
```

**request.json 示例**:
```json
{
  "project_id": "project-001",
  "document_id": "doc-001",
  "document_name": "订单管理需求.md",
  "primary_mapping_id": "primary",
  "primary_filename": "订单管理需求.md",
  "primary_markdown_content": "# 订单管理\n\n用户可以创建订单...",
  "auxiliary_documents": [
    {
      "mapping_id": "aux-001",
      "filename": "技术标准.md",
      "document_type": "standard",
      "markdown_content": "..."
    }
  ]
}
```

---

## 🎯 核心功能

### 三块核心架构

```
1️⃣ 需求理解
  → 识别模块、业务对象、规则、状态流转
  → 识别依赖、风险、假设

2️⃣ 质量评估
  → 完整性检查（功能 + NFR）
  → 清晰度检查（模糊词识别 + suggested_fix）
  → 可测试性检查（验收标准 + 测试覆盖）
  → 一致性检查（冲突识别）
  → 质量决策（approved/conditional/rejected）

3️⃣ 待澄清内容
  → 汇总所有问题
  → 自动从辅助文档查找答案
  → 提供建议选项和行内修正
  → 7级优先级排序
```

### NFR 评估（6大类）

- ✅ **Performance** - 性能（响应时间、吞吐量、并发）
- ✅ **Security** - 安全（认证、授权、加密、审计）
- ✅ **Availability** - 可用性（SLA、容错、恢复）
- ✅ **Scalability** - 可扩展性（用户增长、数据量）
- ✅ **Compatibility** - 兼容性（浏览器、设备、API版本）
- ✅ **Compliance** - 合规（GDPR、HIPAA、行业标准）

---

## 📊 输出结构

```typescript
{
  status: "completed" | "needs_clarification" | "blocked",
  
  understanding: {
    modules: [...],           // 识别的模块
    risks: [...],             // 风险列表
    assumptions: [...]        // 假设列表
  },
  
  quality_assessment: {
    scores: {
      completeness: 70,
      clarity: 75,
      testability: 60,
      consistency: 95,
      overall: 73              // 加权总分
    },
    decision: {
      result: "conditional",
      rationale: "...",
      blocking_issues: [...],
      recommended_actions: [...]
    },
    completeness: { nfr_gaps: [...] },  // NFR 缺口
    clarity: { fuzzy_terms: [...] },    // 模糊词 + suggested_fix
    // ...
  },
  
  clarification: {
    items: [                   // 按优先级排序
      {
        question: "...",
        impact: "...",
        severity: "blocker" | "major" | "minor",
        current_text: "...",
        suggested_fix: "...",  // 行内修正建议
        recommended_options: [...],
        evidence: [...],       // 辅助文档证据
        resolution_status: "auto_resolved" | "has_suggestions" | "needs_manual"
      }
    ],
    summary: {
      total: 10,
      auto_resolved: 2,
      has_suggestions: 5,
      needs_manual: 3
    }
  },
  
  analysis_report_markdown: "...",  // 完整 Markdown 报告
  metadata: {...}
}
```

---

## ⚙️ 配置选项

```python
config = {
    "quality_thresholds": {
        "approved": 90,      # 通过阈值
        "conditional": 75,   # 有条件通过阈值
    },
    "dimension_weights": {
        "completeness": 0.30,
        "clarity": 0.25,
        "testability": 0.25,
        "consistency": 0.20,
    },
    "nfr_categories": [
        "performance",
        "security",
        "availability",
        "scalability",
        "compatibility",
        "compliance",
    ],
}
```

---

## 📖 文档

- **架构设计**: [`requirement-analysis-architecture.md`](docs/requirement-analysis-architecture.md)
- **快速上手**: [`requirement-analysis-v2-guide.md`](docs/requirement-analysis-v2-guide.md)
- **详细流程**: [`requirement-analysis-v2-workflow.md`](docs/requirement-analysis-v2-workflow.md)
- **技术规格**: [`requirement-analysis-v2-spec.md`](docs/requirement-analysis-v2-spec.md)

---

## 🔧 待配置项

### 1. LLM 模型注入

在 `router_v2.py` 中替换 `get_analysis_service()`:

```python
def get_analysis_service():
    from app.core.llm import get_llm_model  # 你的 LLM 模型获取函数
    model = get_llm_model()
    return RequirementAnalysisServiceV2(model=model, config=DEFAULT_CONFIG)
```

### 2. 路由注册

在 FastAPI 主应用中注册路由:

```python
from app.agents.requirement_analysis import router_v2

app.include_router(router_v2)
```

---

## 🎉 完成！

需求分析系统 v2.0 已完全实现，包括：
- ✅ 完整的数据模型
- ✅ 三个 Agent 实现
- ✅ 业务逻辑层
- ✅ RESTful API
- ✅ 单元测试和集成测试
- ✅ 完整的技术文档

**下一步**: 配置 LLM 模型，运行测试，开始使用！
