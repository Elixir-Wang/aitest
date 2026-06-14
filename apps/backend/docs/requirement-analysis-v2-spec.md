# 需求分析系统 v2.0 - 技术规格说明书

**版本**: 2.0  
**日期**: 2026-06-12  
**状态**: Draft  
**作者**: AI 测试系统团队

---

## 1. 概述

### 1.1 目的

本文档定义需求分析系统 v2.0 的技术规格，包括系统架构、API 接口、数据模型、处理流程和部署要求。

### 1.2 范围

需求分析系统 v2.0 采用**三块核心架构**：
1. 需求理解 (Requirement Understanding)
2. 质量评估 (Quality Assessment)
3. 待澄清内容 (Clarification with Auto-Enhancement)

### 1.3 目标

- 自动化需求文档质量评估
- 识别需求缺口、冲突、模糊表述
- 评估非功能需求（NFR）完整性
- 自动从辅助文档查找答案
- 生成优先级排序的待澄清问题列表

### 1.4 术语表

| 术语 | 定义 |
|------|------|
| NFR | Non-Functional Requirements，非功能需求（性能、安全、可用性等） |
| Blocker | 阻塞级别问题，必须立即解决 |
| Major | 主要问题，应在批准前解决 |
| Minor | 次要问题，建议修复 |
| Agent | 基于 LLM 的智能体，负责特定分析任务 |
| Schema | Pydantic 数据模型定义 |

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer                             │
│  POST /api/requirement-analysis/v2/analyze               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                 Service Orchestrator                     │
│         run_requirement_analysis_v2()                    │
└─────────────────────────────────────────────────────────┘
                          ↓
    ┌─────────────────────┬─────────────────────┬─────────────────────┐
    ↓                     ↓                     ↓
┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐
│ Understanding│    │  Quality    │    │  Clarification      │
│   Agent      │ → │  Assessment │ → │  Agent              │
│              │    │   Agent     │    │  (Auto-Enhancement) │
└─────────────┘    └─────────────┘    └─────────────────────┘
    ↓                     ↓                     ↓
┌─────────────────────────────────────────────────────────┐
│              RequirementAnalysisResultV2                 │
└─────────────────────────────────────────────────────────┘
```

### 2.2 模块划分

```
apps/backend/app/agents/requirement_analysis/
├── __init__.py
├── schemas_v2.py                    # Pydantic 数据模型
├── agent_v2.py                      # 三个 Agent 实现
├── service.py                       # 业务逻辑封装
├── router.py                        # FastAPI 路由
├── skills/
│   └── requirement-analysis-v2/
│       └── SKILL.md                 # Skill 定义
└── utils/
    ├── report_generator.py          # 报告生成工具
    ├── priority_sorter.py           # 优先级排序
    └── evidence_matcher.py          # 辅助文档匹配
```

### 2.3 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| 框架 | FastAPI, LangChain |
| 数据验证 | Pydantic v2 |
| LLM | Claude Opus 4.7 / Sonnet 4.6 |
| 异步 | asyncio |
| 存储 | 文件系统 (Markdown) |

---

## 3. 数据模型

### 3.1 输入模型

#### 3.1.1 RequirementAnalysisInputV2

```python
class RequirementAnalysisInputV2(BaseModel):
    project_id: str
    document_id: str
    document_name: str
    run_id: str = ""
    
    # 主需求文档
    primary_mapping_id: str
    primary_filename: str
    primary_markdown_content: str
    
    # 辅助文档
    auxiliary_documents: list[AuxiliaryDocument] = []
    
    # 配置
    config: dict = {}
```

#### 3.1.2 AuxiliaryDocument

```python
class AuxiliaryDocument(BaseModel):
    mapping_id: str
    filename: str
    document_type: Literal[
        "specification", "policy", "standard", 
        "reference", "template", "example", "other"
    ]
    markdown_content: str
```

### 3.2 输出模型

#### 3.2.1 RequirementAnalysisResultV2

```python
class RequirementAnalysisResultV2(BaseModel):
    status: Literal["completed", "needs_clarification", "blocked"]
    
    # 三块核心输出
    understanding: RequirementUnderstandingOutput
    quality_assessment: QualityAssessmentOutput
    clarification: ClarificationOutput
    
    # 报告
    analysis_report_markdown: str
    preliminary_requirement_markdown: str = ""
    
    # 元数据
    metadata: dict
```

### 3.3 核心数据结构

#### 3.3.1 需求理解输出

```python
class RequirementUnderstandingOutput(BaseModel):
    modules: list[RequirementModule]
    dependencies: list[Dependency]
    risks: list[Risk]
    assumptions: list[Assumption]
    understanding_summary: str

class RequirementModule(BaseModel):
    module_key: str
    module_name: str
    summary: str
    capabilities: list[str]
    business_objects: list[BusinessObject]
    business_rules: list[BusinessRule]
    state_flows: list[StateFlow]
```

#### 3.3.2 质量评估输出

```python
class QualityAssessmentOutput(BaseModel):
    scores: QualityScores
    decision: QualityDecision
    completeness: CompletenessAssessment
    clarity: ClarityAssessment
    testability: TestabilityAssessment
    consistency: ConsistencyAssessment
    assessment_summary: str

class QualityScores(BaseModel):
    completeness: int  # 0-100
    clarity: int
    testability: int
    consistency: int
    overall: int  # 加权平均

class QualityDecision(BaseModel):
    result: Literal["approved", "conditional", "rejected"]
    rationale: str
    blocking_issues: list[str]
    recommended_actions: list[str]
```

#### 3.3.3 待澄清内容输出

```python
class ClarificationOutput(BaseModel):
    items: list[ClarificationItem]  # 按优先级排序
    summary: ClarificationSummary
    clarification_summary_text: str

class ClarificationItem(BaseModel):
    item_id: str
    source: Literal["understanding", "completeness", "clarity", 
                    "testability", "consistency"]
    module_key: str
    question: str
    impact: str
    severity: Literal["blocker", "major", "minor"]
    current_text: str
    suggested_fix: str
    recommended_options: list[ClarificationOption]
    evidence: list[EvidenceReference]
    resolution_status: Literal["auto_resolved", 
                               "has_suggestions", 
                               "needs_manual"]
```

---

## 4. API 接口规格

### 4.1 需求分析接口

#### 4.1.1 POST /api/requirement-analysis/v2/analyze

**描述**: 执行完整的需求分析流程

**请求**:
```http
POST /api/requirement-analysis/v2/analyze
Content-Type: application/json

{
  "project_id": "project-001",
  "document_id": "doc-001",
  "document_name": "订单管理需求.md",
  "run_id": "run-20260612-001",
  "primary_mapping_id": "mapping-001",
  "primary_filename": "订单管理需求.md",
  "primary_markdown_content": "# 订单管理\n\n...",
  "auxiliary_documents": [
    {
      "mapping_id": "aux-001",
      "filename": "技术标准.md",
      "document_type": "standard",
      "markdown_content": "..."
    }
  ],
  "config": {
    "quality_thresholds": {
      "approved": 90,
      "conditional": 75
    },
    "dimension_weights": {
      "completeness": 0.30,
      "clarity": 0.25,
      "testability": 0.25,
      "consistency": 0.20
    }
  }
}
```

**响应** (200 OK):
```json
{
  "status": "needs_clarification",
  "understanding": {
    "modules": [...],
    "risks": [...],
    "assumptions": [...]
  },
  "quality_assessment": {
    "scores": {
      "completeness": 70,
      "clarity": 75,
      "testability": 60,
      "consistency": 95,
      "overall": 73
    },
    "decision": {
      "result": "conditional",
      "rationale": "...",
      "blocking_issues": ["缺少性能要求"],
      "recommended_actions": ["补充NFR"]
    }
  },
  "clarification": {
    "items": [...],
    "summary": {
      "total": 10,
      "auto_resolved": 2,
      "has_suggestions": 5,
      "needs_manual": 3
    }
  },
  "analysis_report_markdown": "# 需求分析报告\n\n...",
  "metadata": {
    "version": "2.0",
    "execution_time_ms": 45000
  }
}
```

**错误响应**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "primary_markdown_content 不能为空",
    "details": {}
  }
}
```

**状态码**:
- 200: 成功
- 400: 请求参数错误
- 500: 服务器内部错误

---

## 5. 处理流程

### 5.1 阶段 1：需求理解

**输入**: `primary_markdown_content`

**处理步骤**:
1. 调用 `understanding_agent()`
2. LLM 分析文档，提取结构化信息
3. 识别模块、对象、规则、状态、依赖、风险
4. 返回 `RequirementUnderstandingOutput`

**System Prompt 关键点**:
```
你是需求理解智能体。
职责：从原始需求文档中提取结构化信息。
输入：primary_markdown_content
处理：
1. 识别功能模块（module_key, module_name, capabilities）
2. 提取业务对象（name, fields, relationships）
3. 提取业务规则（验证、计算、工作流、权限）
4. 分析状态流转（states, transitions）
5. 识别依赖关系、风险、假设
输出：RequirementUnderstandingOutput JSON
```

**执行时间**: 10-15 秒  
**Token 消耗**: 输入 ~6K, 输出 ~2K

### 5.2 阶段 2：质量评估

**输入**: `primary_markdown_content` + `understanding_result`

**处理步骤**:
1. 调用 `quality_assessment_agent()`
2. 并行评估四个维度：
   - 完整性检查（功能 + NFR）
   - 清晰度检查（模糊词 + 歧义）
   - 可测试性检查（验收标准 + 测试覆盖）
   - 一致性检查（冲突 + 术语）
3. 计算加权总分
4. 生成决策（approved/conditional/rejected）
5. 返回 `QualityAssessmentOutput`

**评分公式**:
```python
overall_score = (
    completeness_score * 0.30 +
    clarity_score * 0.25 +
    testability_score * 0.25 +
    consistency_score * 0.20
)
```

**决策规则**:
```python
if overall_score >= 90 and blocker_count == 0:
    result = "approved"
elif overall_score >= 75 or blocker_count <= 2:
    result = "conditional"
else:
    result = "rejected"
```

**执行时间**: 15-20 秒  
**Token 消耗**: 输入 ~8K, 输出 ~3K

### 5.3 阶段 3：待澄清内容

**输入**: `understanding_result` + `quality_assessment_result` + `auxiliary_documents`

**处理步骤**:
1. 汇总问题（从质量评估提取）
2. 问题转换（转为 ClarificationItem）
3. 自动从辅助文档查找答案
4. 评估证据质量（high/medium/low）
5. 生成建议选项
6. 确定解答状态（auto_resolved/has_suggestions/needs_manual）
7. 7 级优先级排序
8. 返回 `ClarificationOutput`

**优先级排序算法**:
```python
def sort_key(item):
    severity_priority = {"blocker": 0, "major": 1, "minor": 2}
    status_priority = {
        "needs_manual": 0, 
        "has_suggestions": 1, 
        "auto_resolved": 2
    }
    return (
        severity_priority[item.severity],
        status_priority[item.resolution_status]
    )

items.sort(key=sort_key)
```

**执行时间**: 10-15 秒  
**Token 消耗**: 输入 ~10K, 输出 ~2K

### 5.4 流程编排

```python
async def run_requirement_analysis_v2(
    model, primary_markdown_content, 
    auxiliary_documents=None, config=None
):
    # 阶段 1
    understanding = await run_understanding_agent(
        model, primary_markdown_content
    )
    
    # 阶段 2
    quality = await run_quality_assessment_agent(
        model, primary_markdown_content, understanding
    )
    
    # 阶段 3
    clarification = await run_clarification_agent(
        model, understanding, quality, auxiliary_documents
    )
    
    # 确定状态
    status = determine_status(quality.decision, clarification.summary)
    
    # 生成报告
    report = generate_analysis_report(
        understanding, quality, clarification
    )
    
    return RequirementAnalysisResultV2(
        status=status,
        understanding=understanding,
        quality_assessment=quality,
        clarification=clarification,
        analysis_report_markdown=report
    )
```

---

## 6. 配置规格

### 6.1 默认配置

```python
DEFAULT_CONFIG = {
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
        "performance",      # 性能
        "security",         # 安全
        "availability",     # 可用性
        "scalability",      # 可扩展性
        "compatibility",    # 兼容性
        "compliance",       # 合规
    ],
    "auto_enhancement": {
        "enabled": True,
        "min_confidence": "medium",
    },
    "max_clarification_items": 100,
    "max_recommended_options": 2,
}
```

### 6.2 环境变量

```bash
# LLM 配置
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-7
ANTHROPIC_MAX_TOKENS=4096
ANTHROPIC_TEMPERATURE=0.0

# 应用配置
REQUIREMENT_ANALYSIS_VERSION=2.0
REQUIREMENT_ANALYSIS_TIMEOUT=120  # 秒
REQUIREMENT_ANALYSIS_RETRY=3

# 存储配置
REQUIREMENT_ANALYSIS_OUTPUT_DIR=D:\project\test_project\apps\backend\data\projects
```

---

## 7. 部署要求

### 7.1 系统要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 10/11, Linux, macOS |
| Python | 3.11+ |
| 内存 | 4GB+ |
| 磁盘 | 10GB+ 可用空间 |
| 网络 | 访问 Anthropic API |

### 7.2 依赖安装 (Windows)

```powershell
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 验证安装
python -c "import langchain; import pydantic; print('OK')"
```

### 7.3 启动服务 (Windows)

```powershell
# 设置环境变量
$env:ANTHROPIC_API_KEY="sk-ant-..."

# 启动 FastAPI 服务
cd apps\backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 访问 API 文档
start http://localhost:8000/docs
```

---

## 8. 性能指标

### 8.1 响应时间

| 阶段 | 目标 | 最大 |
|------|------|------|
| 需求理解 | 10-15s | 30s |
| 质量评估 | 15-20s | 45s |
| 待澄清内容 | 10-15s | 30s |
| **总计** | **35-50s** | **2min** |

### 8.2 Token 消耗

| 操作 | 输入 | 输出 | 总计 |
|------|------|------|------|
| 单次分析 | ~24K | ~7K | ~31K |
| 每月预估 (1000次) | ~24M | ~7M | ~31M |

### 8.3 并发能力

- 单实例支持：10 并发请求
- 响应时间 P95：60 秒
- 响应时间 P99：90 秒

---

## 9. 监控和日志

### 9.1 日志级别

```python
LOGGING_CONFIG = {
    "version": 1,
    "loggers": {
        "requirement_analysis": {
            "level": "INFO",
            "handlers": ["console", "file"]
        }
    }
}
```

### 9.2 关键指标

```python
# 记录执行时间
logger.info(f"Understanding completed in {duration}s")

# 记录质量评分
logger.info(f"Quality score: {overall_score}/100")

# 记录待澄清数量
logger.info(f"Clarification items: {total} ({needs_manual} manual)")

# 记录错误
logger.error(f"Analysis failed: {error}", exc_info=True)
```

### 9.3 监控指标

- `requirement_analysis_duration_seconds`：分析耗时
- `requirement_analysis_quality_score`：质量评分
- `requirement_analysis_clarification_count`：待澄清数量
- `requirement_analysis_errors_total`：错误总数

---

## 10. 测试规格

### 10.1 单元测试

```powershell
# 运行单元测试 (Windows)
cd apps\backend
pytest tests\agents\requirement_analysis\test_agent_v2.py -v
```

**测试覆盖**:
- `test_understanding_agent()`: 需求理解
- `test_quality_assessment_agent()`: 质量评估
- `test_clarification_agent()`: 待澄清内容
- `test_nfr_evaluation()`: NFR 评估
- `test_priority_sorting()`: 优先级排序

### 10.2 集成测试

```python
async def test_full_workflow():
    """测试完整流程"""
    result = await run_requirement_analysis_v2(
        model=test_model,
        primary_markdown_content=TEST_CONTENT,
        auxiliary_documents=TEST_AUX_DOCS,
    )
    
    assert result.status in ["completed", "needs_clarification", "blocked"]
    assert result.quality_assessment.scores.overall >= 0
    assert result.quality_assessment.scores.overall <= 100
    assert len(result.clarification.items) > 0
```

### 10.3 性能测试

```powershell
# 使用 pytest-benchmark (Windows)
pytest tests\agents\requirement_analysis\test_performance.py --benchmark-only
```

---

## 11. 安全规格

### 11.1 输入验证

```python
# Pydantic 自动验证
class RequirementAnalysisInputV2(BaseModel):
    primary_markdown_content: str = Field(min_length=10, max_length=100000)
    document_name: str = Field(pattern=r'^[a-zA-Z0-9_\-\u4e00-\u9fa5]+\.md$')
```

### 11.2 敏感信息处理

- API Key 通过环境变量配置，不记录日志
- 需求文档内容不上传到第三方（除 Anthropic API）
- 分析结果存储在本地文件系统

### 11.3 错误处理

```python
try:
    result = await run_requirement_analysis_v2(...)
except ValidationError as e:
    return {"error": {"code": "VALIDATION_ERROR", "message": str(e)}}
except TimeoutError as e:
    return {"error": {"code": "TIMEOUT", "message": "分析超时"}}
except Exception as e:
    logger.error("Analysis failed", exc_info=True)
    return {"error": {"code": "INTERNAL_ERROR", "message": "内部错误"}}
```

---

## 12. 版本管理

### 12.1 版本号

- 当前版本：`2.0.0`
- 版本格式：`MAJOR.MINOR.PATCH`

### 12.2 兼容性

- v2.0 与 v1.0 API 不兼容
- 提供迁移工具：`migrate_v1_to_v2.py`

### 12.3 变更日志

```markdown
## [2.0.0] - 2026-06-12

### Added
- 三块核心架构（理解、评估、澄清）
- NFR 评估（6 大类）
- 行内修正建议（suggested_fix）
- 辅助文档查询集成到待澄清阶段
- 7 级优先级排序

### Changed
- 重构数据模型（schemas_v2.py）
- 优化质量评分算法
- 改进决策输出格式

### Removed
- 旧版 requirement-review skill（单一文档）
```

---

## 13. 附录

### 13.1 文件清单

```
apps/backend/
├── app/agents/requirement_analysis/
│   ├── schemas_v2.py                  # 数据模型
│   ├── agent_v2.py                    # Agent 实现
│   ├── service.py                     # 业务逻辑
│   ├── router.py                      # API 路由
│   └── skills/requirement-analysis-v2/
│       └── SKILL.md
├── docs/
│   ├── requirement-analysis-architecture.md
│   ├── requirement-analysis-v2-guide.md
│   ├── requirement-analysis-v2-workflow.md
│   └── requirement-analysis-v2-spec.md  # 本文档
└── tests/agents/requirement_analysis/
    ├── test_agent_v2.py
    ├── test_schemas_v2.py
    └── test_performance.py
```

### 13.2 参考资源

- BABOK (Business Analysis Body of Knowledge)
- IREB (International Requirements Engineering Board)
- IEEE 830 - Software Requirements Specification
- ISO/IEC 25010 - Systems and software Quality Models
- INVEST Principles for User Stories

### 13.3 联系方式

- 项目仓库：`D:\project\test_project`
- 文档路径：`apps\backend\docs\`
- 问题反馈：GitHub Issues

---

**文档结束**
