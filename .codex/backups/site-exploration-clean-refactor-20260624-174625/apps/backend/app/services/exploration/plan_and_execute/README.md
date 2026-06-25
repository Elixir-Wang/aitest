# Plan-and-Execute 探索模式

## 概述

Plan-and-Execute 是一种先规划、后执行的探索模式，相比传统的 ReAct（每步思考-行动）模式，具有以下优势：

### 架构对比

```
ReAct 模式（当前 Agentic Loop）:
观察 → 思考 → 行动 → 观察 → 思考 → 行动 → ...
❌ 问题：每步都调用LLM，成本高，缺乏全局视角

Plan-and-Execute 模式:
统一规划 → 执行步骤1 → 执行步骤2 → ... → 遇到问题 → 重新规划 → 继续执行
✅ 优势：全局视角、成本低、可控性强
```

### 核心优势

1. **全局规划**：一次性分析完整目标，制定系统化计划
2. **成本优化**：规划阶段调用1-2次LLM，执行阶段直接操作，大幅降低成本
3. **可控性强**：步骤明确，进度可追踪，易于调试
4. **自适应能力**：失败时可重新规划，兼具灵活性

---

## 使用方法

### 自动模式切换

系统会根据探索目标自动选择最合适的模式：

#### 触发 Plan-and-Execute 模式的目标格式

**方式1：模块化步骤**
```
模块一：进入智能体与切换对话模型
1. 进入工作台。
2. 点击"测试_自主规划智能体"卡片的空白处。
3. 点击对话模型的下拉栏。
4. 在下拉选项中选择一个模型。

模块二：首次会话的发送、发布与历史记录操作
1. 点击右上角历史记录。
2. 点击"新建回话"。
3. 再次点击历史记录按钮，关闭历史记录列表。
...
```

**方式2：数字列表步骤**
```
按照以下步骤进行探索：

1. 导航到工作台页面
2. 找到并点击目标智能体卡片
3. 测试对话功能
4. 验证历史记录功能
5. 测试模型切换
...
```

**方式3：明确指定**
```
请使用 plan-and-execute 模式进行探索，目标是...
```

#### 使用 Agentic Loop 模式的目标格式

自然语言描述（无明确步骤）：
```
全面探索工作台功能，记录所有可交互元素
```

---

## 工作流程

### 1. Planning Phase（规划阶段）

系统调用 Planner，分析：
- 探索目标
- 探索范围
- 禁止路径

生成完整的探索计划，包括：
- 模块划分
- 详细步骤
- 每个步骤的预期结果
- 成功标准

**示例输出**：
```json
{
  "plan_id": "plan-explore-abc123",
  "goal_summary": "测试智能体工作台的对话模型切换和会话管理功能",
  "strategy": "按照用户提供的模块顺序执行，每个步骤都进行验证",
  "modules": ["进入智能体与切换对话模型", "首次会话管理"],
  "steps": [
    {
      "step_id": "step-001",
      "action_type": "navigate",
      "description": "导航到工作台页面",
      "target_description": "/workspace路径",
      "expected_result": "成功进入工作台，看到智能体卡片列表"
    },
    {
      "step_id": "step-002",
      "action_type": "click",
      "description": "点击'测试_自主规划智能体'卡片",
      "target_description": "包含文本'测试_自主规划智能体'的可点击卡片",
      "expected_result": "进入智能体详情页或对话页"
    }
  ]
}
```

### 2. Execution Phase（执行阶段）

PlanExecutor 按照计划逐步执行：

1. **智能元素定位**：根据步骤描述找到目标元素
2. **执行动作**：click、fill、navigate等
3. **记录结果**：页面状态、截图、元素信息

支持的动作类型：
- `navigate`: 导航到URL
- `click`: 点击元素
- `fill`: 填充表单
- `wait`: 等待加载
- `observe`: 观察并记录页面
- `check`: 验证条件

### 3. Monitoring Phase（监控阶段）

ExecutionMonitor 实时监控执行：

**失败处理策略**：
1. **重试**：非持久性错误自动重试（最多2次）
2. **跳过**：非关键步骤失败可跳过
3. **重新规划**：连续3次失败或关键步骤失败触发重新规划
4. **终止**：重新规划失败或无法处理时终止

**重新规划触发条件**：
- 连续3个步骤失败
- 关键步骤失败且无法继续
- 页面结构与预期严重不符

---

## 元素定位策略

### 智能匹配

系统支持多种匹配策略，无需精确的 selector：

**1. 精确匹配**
```
步骤描述: "点击'测试_自主规划智能体'卡片"
→ 匹配元素: name="测试_自主规划智能体"
```

**2. 包含匹配**
```
步骤描述: "点击对话模型下拉栏"
→ 匹配元素: name包含"对话模型"的任何元素
```

**3. 角色匹配**
```
步骤描述: "点击提交按钮"
→ 匹配元素: role="button"且name包含"提交"
```

**4. 反向匹配**
```
步骤描述: "点击包含用户头像的按钮"
→ 匹配元素: 任何包含"头像"关键词的元素
```

---

## 配置和定制

### 步骤属性

每个步骤支持以下配置：

```python
{
  "step_id": "step-001",
  "action_type": "click",  # 动作类型
  "description": "点击登录按钮",  # 步骤描述
  "target_description": "包含'登录'文字的按钮",  # 目标元素描述
  "expected_result": "进入登录页面",  # 预期结果
  "module_name": "用户认证",  # 所属模块
  "is_critical": true,  # 是否关键步骤
  "retry_on_failure": true,  # 失败时是否重试
  "max_retries": 2  # 最大重试次数
}
```

### 监控参数

```python
monitor = ExecutionMonitor(plan, planner_input)
monitor.max_re_plans = 3  # 最多重新规划3次
monitor.consecutive_failures = 0  # 连续失败计数
```

---

## 前端展示

探索过程中，前端会实时显示：

1. **Planning Phase**：
   ```
   正在分析目标并生成探索计划...
   ✓ 计划生成完成：共12个步骤，分为3个模块
   ```

2. **Execution Phase**：
   ```
   执行步骤 3/12: 点击'测试_自主规划智能体'卡片
   ✓ 步骤成功: 成功点击元素，进入智能体详情页
   ```

3. **Re-planning Phase**（如果触发）：
   ```
   ⚠️ 连续步骤失败，正在重新规划...
   🔄 重新规划完成：生成8个新步骤
   ```

---

## 对比 Agentic Loop

| 特性 | Plan-and-Execute | Agentic Loop |
|-----|------------------|--------------|
| **规划方式** | 一次性全局规划 | 每步独立决策 |
| **LLM调用** | 规划阶段1-2次 + 重规划 | 每步1次 |
| **成本** | 低（约为Agentic的20-30%） | 高 |
| **可控性** | 高，步骤明确 | 中，依赖Agent决策 |
| **灵活性** | 中，可重新规划 | 高，完全自主 |
| **适用场景** | 明确目标、结构化任务 | 开放式探索 |
| **进度追踪** | 清晰（X/总数） | 模糊 |
| **调试难度** | 低 | 高 |

---

## 最佳实践

### ✅ 推荐

**明确的步骤描述**
```
✓ "点击包含'测试_自主规划智能体'文字的卡片"
✗ "点击那个卡片"
```

**合理的模块划分**
```
✓ 模块一：用户登录
   模块二：数据浏览
   模块三：数据操作
✗ 模块一：所有操作
```

**设置关键步骤**
```
✓ 登录步骤设为关键（失败必须停止）
✗ 所有步骤都设为关键
```

### ❌ 避免

**过于模糊的描述**
```
✗ "探索页面"
✓ "点击导航栏的'设置'按钮"
```

**过长的单一流程**
```
✗ 一个模块包含50个步骤
✓ 拆分为5个模块，每个10步左右
```

**硬编码selector**
```
✗ target_selector: "#app > div.main > button:nth-child(3)"
✓ target_description: "主界面右上角的'设置'按钮"
```

---

## 故障排查

### 问题：规划生成失败

**原因**：目标描述不清晰或格式错误

**解决**：
1. 确保目标包含明确的步骤或模块
2. 使用清晰的自然语言
3. 检查日志中的 `planning_failed` 事件

### 问题：步骤找不到元素

**原因**：元素描述与实际页面不匹配

**解决**：
1. 检查页面实际内容
2. 放宽描述条件（如去掉"的"、"按钮"等修饰词）
3. 系统会自动重试和重新规划

### 问题：连续失败后停止

**原因**：达到重新规划上限或关键步骤失败

**解决**：
1. 检查失败原因（日志中的 error 字段）
2. 调整目标或范围
3. 标记非关键步骤为 `is_critical: false`

---

## API 使用

### 直接调用

```python
from app.services.exploration.unified_orchestrator import run_unified_exploration_sync

result = run_unified_exploration_sync(
    run_id="explore-abc123",
    artifact_root=Path("/path/to/artifacts"),
    start_url="https://example.com",
    storage_state_path="/path/to/auth.json"  # 可选
)

print(result["status"])  # "completed", "partial", "blocked", "cancelled"
print(result["execution_summary"])
```

### 通过 API 端点

创建探索任务时，在 `goal` 中使用结构化格式即可自动触发 Plan-and-Execute 模式：

```bash
curl -X POST http://localhost:8000/api/v1/projects/proj-123/exploration-runs \
  -H "Content-Type: application/json" \
  -d '{
    "title": "智能体工作台功能测试",
    "environment_id": "env-456",
    "goal": "模块一：进入智能体与切换对话模型\n1. 进入工作台。\n2. 点击卡片。\n...",
    "scope": "/workspace",
    "forbidden_paths": "删除, 支付"
  }'
```

---

## 扩展开发

### 自定义动作类型

```python
# 在 executor.py 中添加新的动作类型
def _execute_custom_action(self, step: ExplorationStep) -> StepExecutionResult:
    # 实现自定义逻辑
    pass

# 在 _execute_step 中注册
if step.action_type == "custom_action":
    return self._execute_custom_action(step)
```

### 自定义匹配策略

```python
# 在 executor.py 的 _find_element 中添加
# 策略5: 自定义语义匹配
if self.use_llm_matching:
    return self._llm_semantic_match(elements, description)
```

---

## 参考资料

- [LangChain Plan-and-Execute Agent](https://python.langchain.com/docs/modules/agents/agent_types/plan_and_execute)
- [ReWOO: Decoupling Reasoning from Observations](https://arxiv.org/abs/2305.18323)
- [Plan-and-Solve Prompting](https://arxiv.org/abs/2305.04091)
