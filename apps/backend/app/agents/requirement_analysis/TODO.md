# 需求分析 v3.0 - 未完成事项清单

## ✅ 已完成（核心功能）

- ✅ Agentic Search（搜索工具 + Agent + 服务）
- ✅ LangGraph 工作流（状态 + 节点 + 编排）
- ✅ 主流程集成（特性开关 + 适配器）
- ✅ 单元测试（12个用例）
- ✅ 完整文档（4篇）

---

## 📝 未完成事项

### 🔴 高优先级（阻塞上线）

#### 1. **真实环境验证**（必须）
- [ ] 使用真实需求文档测试 v3.0
- [ ] 实测 Token 消耗（验证是否真的节省 90%）
- [ ] 实测答案准确率（验证是否 ≥ 85%）
- [ ] 实测执行耗时（验证是否 < v2）

**为什么重要**：目前的数字都是预估，必须用真实数据验证。

**如何完成**：
```bash
# 1. 启用 v3
export REQUIREMENT_ANALYSIS_VERSION=v3

# 2. 准备测试数据
# - 主需求：包含模糊词的真实文档
# - 辅助文档：包含明确定义

# 3. 运行分析，记录指标
# - Token 消耗（从日志或 metadata）
# - 执行耗时（metadata.execution_time_ms）
# - 答案质量（人工评估）

# 4. 对比 v2
export REQUIREMENT_ANALYSIS_VERSION=v2
# 重复测试，对比结果
```

---

#### 2. **依赖项检查**（必须）
- [ ] 确认 `langchain-core`、`langchain-openai`、`langgraph` 已安装
- [ ] 确认 LLM 模型配置正确
- [ ] 确认 `app.core.llm` 和 `app.repositories.model_selection_repo` 存在

**为什么重要**：缺少依赖会导致运行时错误。

**如何完成**：
```bash
# 检查依赖
pip list | grep langchain
pip list | grep langgraph

# 如果缺少，安装
pip install langchain-core langchain-openai langgraph
```

---

### 🟡 中优先级（增强功能）

#### 3. **Callbacks 可观测性**（推荐）
- [ ] 实现自定义 Callback Handler
- [ ] 结构化日志输出
- [ ] 监控指标上报（Token、耗时、成功率）
- [ ] LangSmith 集成（可选）

**预估时间**：1-2天

**文件**：`apps/backend/app/agents/requirement_analysis/v3/callbacks/analysis_callback.py`

---

#### 4. **性能优化**（推荐）
- [ ] 并行搜索多个问题（目前是串行）
- [ ] 搜索结果缓存（相同问题不重复搜索）
- [ ] 超时控制（单个搜索最多 30s）

**预估时间**：1-2天

**效果**：耗时从 27s → 15s

---

#### 5. **错误处理增强**（推荐）
- [ ] LLM 调用失败的重试机制
- [ ] 搜索超时的降级策略
- [ ] 数据格式转换的容错处理

**预估时间**：1天

---

### 🟢 低优先级（可选增强）

#### 6. **模糊匹配**（可选）
- [ ] 使用 FuzzyWuzzy 替代精确匹配
- [ ] 支持同义词搜索

**预估时间**：0.5天

**效果**：搜索准确率 85% → 90%

---

#### 7. **语义搜索**（可选）
- [ ] 使用 Embedding + FAISS 替代关键词匹配
- [ ] 支持跨语言搜索

**预估时间**：2-3天

**效果**：搜索准确率 90% → 95%

---

#### 8. **LangGraph 可视化**（可选）
- [ ] 生成工作流程图（Mermaid）
- [ ] 前端展示流程图

**预估时间**：1天

**效果**：便于理解和调试

---

#### 9. **前端展示搜索路径**（可选）
- [ ] 在前端 UI 中显示搜索过程
- [ ] 显示"Agent搜索了3次：验证码 → 有效期 → OTP timeout"

**预估时间**：1-2天

**效果**：用户可以看到 AI 的思考过程

---

## 🚨 潜在问题

### 1. **模型依赖检查**
当前代码依赖这些模块：
```python
from app.core.llm import build_agent_model
from app.repositories.model_selection_repo import resolve_model_selection
```

**需要确认**：
- [ ] 这些模块是否存在？
- [ ] `resolve_model_selection("requirement_analysis")` 返回什么？
- [ ] `build_agent_model()` 返回的模型是否兼容 LangChain？

**如何检查**：
```python
# 在 Python shell 中测试
from app.core.llm import build_agent_model
from app.repositories.model_selection_repo import resolve_model_selection

model_selection = resolve_model_selection("requirement_analysis")
print(model_selection)

model = build_agent_model(model_selection)
print(type(model))
```

---

### 2. **数据格式兼容性**
`service_adapter.py` 中进行了 v2 ↔ v3 数据格式转换。

**需要确认**：
- [ ] v2 的 `RequirementAnalysisOutput` 字段是否完整？
- [ ] v3 的 `RequirementAnalysisResultV2` 是否包含所有必要字段？
- [ ] 转换逻辑是否正确？

**如何检查**：
运行集成测试，查看返回数据是否符合预期。

---

### 3. **导入路径问题**
`service_adapter.py` 中有相对导入：
```python
from ..schemas_v2 import ...
```

**需要确认**：
- [ ] 导入路径是否正确？
- [ ] 是否能正常加载？

**如何检查**：
```bash
python -c "from app.agents.requirement_analysis.service_adapter import analyze_requirement; print('OK')"
```

---

## 📋 启用前检查清单

在生产环境启用 v3.0 前，请完成：

### 必须项
- [ ] 安装 LangChain 依赖
- [ ] 真实环境验证（至少 5 个真实文档）
- [ ] Token 消耗实测（确认节省 > 80%）
- [ ] 答案准确率实测（确认 ≥ 80%）
- [ ] 错误处理测试（LLM 失败、超时等）
- [ ] 准备回滚方案

### 推荐项
- [ ] Callbacks 可观测性（日志 + 监控）
- [ ] 性能优化（并行搜索 + 缓存）
- [ ] 压力测试（100 个并发请求）

### 可选项
- [ ] 模糊匹配
- [ ] 语义搜索
- [ ] LangGraph 可视化

---

## 🎯 建议执行顺序

1. **立即**：依赖检查 + 导入测试（5分钟）
2. **今天**：真实环境验证（2-4小时）
3. **本周**：Callbacks + 性能优化（2-3天）
4. **下周**：灰度发布（10% → 50% → 100%）

---

**更新时间**：2026-06-13
