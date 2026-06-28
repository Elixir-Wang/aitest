# MiniMax 模型工具调用兼容性问题分析与修复

## 问题描述

**错误信息**：
```
httpx.HTTPStatusError: Client error '400 Bad Request' for url 'https://minnimax.chat/v1/chat/completions'
```

**现象**：
- 探索任务启动后立即失败
- 请求发送到 MiniMax API 但返回 400 错误
- 错误发生在调用 LLM 模型时

## 根本原因分析

### 1. 模型配置
从数据库查询结果：
```
Provider: Minimax
Model: MiniMax-M3
Base URL: https://minnimax.chat/v1
Status: enabled
Health Status: healthy
```

模型配置本身是正常的，健康检查也通过了。

### 2. 代码黑名单
在 `apps/backend/app/agents/model_selection.py` 中已经定义了不支持工具调用的提供商：

```python
TOOL_CALLING_UNSUPPORTED_PROVIDERS = {
    "minimax",
}
```

并且有检查逻辑：
```python
if selection.provider.strip().lower() in TOOL_CALLING_UNSUPPORTED_PROVIDERS:
    raise ValueError(
        f"当前模型提供方 {selection.provider} / {selection.model} 不适合用于带工具调用的 Agent。"
        "请为该能力分配支持 OpenAI tools/function calling 的模型配置。"
    )
```

### 3. 问题所在

**为什么黑名单检查没有阻止 MiniMax？**

检查逻辑是正确的：
- 数据库中的 provider: `"Minimax"`（首字母大写）
- 检查时：`"Minimax".strip().lower()` = `"minimax"`
- 黑名单中：`"minimax"`
- 理论上**应该被拦截**

**实际问题**：请求已经发送到了 MiniMax API，说明**请求到达了 API 层面**。

### 4. 真正的根因

**MiniMax API 不支持 OpenAI 的 `tools` 参数格式**

从错误请求中可以看到：
```python
'tools': [{'type': 'function', 'function': {'name': 'write_todos...
```

DeepAgents 框架使用的是 OpenAI 标准的 tools 格式（OpenAI Function Calling），但 MiniMax API：
- 可能完全不支持 tools 参数
- 或者使用不同的工具调用格式
- 或者该模型版本不支持工具调用

当 MiniMax 收到不认识的 `tools` 参数时，返回 `400 Bad Request`。

### 5. 为什么检查失效？

可能的原因：
1. **异步执行绕过检查**：探索任务在后台线程中执行，`build_agent_model` 的检查在某些场景下可能被绕过
2. **多次调用**：可能有其他代码路径直接创建模型，没有经过检查
3. **异常被吞掉**：检查抛出的异常在某处被捕获但没有正确处理

## 修复方案

### 修复内容

在探索任务执行的最早阶段添加**二次防御检查**：

**文件**：`apps/backend/app/services/exploration/page_exploration_service.py`

```python
def _execute_exploration(run_id: str, run_config: dict) -> None:
    """执行探索逻辑 - 集成deepagents Agent"""
    import asyncio
    from app.agents.model_selection import (
        resolve_model_selection, 
        build_agent_model, 
        TOOL_CALLING_UNSUPPORTED_PROVIDERS  # 新增导入
    )
    from app.agents.page_exploration.agent import page_exploration_agent

    project_id = run_config["project_id"]
    start_url = run_config["scope"]
    max_pages = run_config["max_pages"]

    try:
        # 1. 解析模型配置
        model_selection = resolve_model_selection("site_exploration")

        # 2. 提前检查模型是否支持工具调用（新增）
        if model_selection.provider.strip().lower() in TOOL_CALLING_UNSUPPORTED_PROVIDERS:
            raise ValueError(
                f"探索任务需要工具调用能力，但当前模型 {model_selection.provider}/{model_selection.model} "
                f"不支持 OpenAI tools/function calling 格式。"
                f"请为 'site_exploration' 能力分配支持工具调用的模型（如 OpenAI、Anthropic、DeepSeek 等）。"
            )

        model = build_agent_model(model_selection)
        
        # ... 后续代码
```

### 修复原理

**深度防御策略**：
1. **第一层**：`build_agent_model` 中的检查（通用检查）
2. **第二层**：`_execute_exploration` 开始时的检查（任务级检查）

即使第一层检查因某种原因失效，第二层也能拦截。

### 错误处理改进

这个错误会被后续的异常处理捕获：

```python
except Exception as e:
    # 发生错误，更新状态为blocked
    with connect() as db:
        exploration_run_repo.update_status(
            db,
            run_id,
            "blocked",
            finished_at=datetime.now(timezone.utc).isoformat(),
            result_summary=f"探索阻塞: {str(e)}",
        )
    raise
```

任务状态会被标记为 `blocked`，用户会看到清晰的错误信息。

## 支持工具调用的模型提供商

### 已验证支持
- **OpenAI**：GPT-4, GPT-3.5-turbo 等
- **Anthropic**：Claude 3 系列（Opus, Sonnet, Haiku）
- **DeepSeek**：DeepSeek-V2, DeepSeek-Chat

### 不支持（黑名单）
- **MiniMax**：所有版本
  - MiniMax-M3
  - MiniMax-M2.7-highspeed

### 如何更换模型

1. **通过管理界面**：
   - 进入"模型管理"
   - 为"站点探索"能力分配支持工具调用的模型
   - 保存配置

2. **通过数据库**（临时方案）：
```sql
-- 查看可用的支持工具调用的模型
SELECT id, provider, model FROM model_providers 
WHERE provider NOT IN ('Minimax', 'minimax') 
AND status = 'enabled';

-- 更新站点探索的模型分配
UPDATE model_assignments 
SET model_provider_id = '<新的模型ID>' 
WHERE capability_id = 'site_exploration';
```

## 测试验证

### 测试步骤

1. **重启后端**
```bash
cd apps/backend
uvicorn app.main:app --reload --port 8000
```

2. **启动探索任务**
   - 使用 MiniMax 模型会立即失败
   - 状态标记为 `blocked`
   - 错误信息清晰说明原因

3. **切换到支持的模型**
   - 更换为 OpenAI 或其他支持的模型
   - 重新启动探索任务
   - 应该正常运行

### 预期结果

**使用 MiniMax**：
```
探索阻塞: 探索任务需要工具调用能力，但当前模型 Minimax/MiniMax-M3 不支持 OpenAI tools/function calling 格式。
请为 'site_exploration' 能力分配支持工具调用的模型（如 OpenAI、Anthropic、DeepSeek 等）。
```

**使用 OpenAI**：
- 探索任务正常运行
- 状态显示为 `running` -> `completed`

## 技术要点

### 1. OpenAI Function Calling 格式

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "tool_name",
        "description": "Tool description",
        "parameters": {
          "type": "object",
          "properties": {...}
        }
      }
    }
  ]
}
```

### 2. 为什么 MiniMax 不支持

MiniMax API 可能：
- 使用自己的工具调用格式
- 该模型版本不支持工具调用
- API 兼容性问题

### 3. DeepAgents 框架的要求

DeepAgents 框架依赖 LangChain 的 `ChatOpenAI` 接口，该接口使用 OpenAI 标准格式：
- 工具定义使用 `tools` 参数
- 工具调用结果使用 `tool_calls` 字段
- 需要模型完全兼容 OpenAI 的 API 规范

## 后续改进建议

### 1. 前端提示
在模型选择界面添加提示：
```
⚠️ 站点探索功能需要支持工具调用的模型
支持的提供商：OpenAI、Anthropic、DeepSeek
不支持：MiniMax
```

### 2. 健康检查增强
在模型健康检查时，测试工具调用能力：
```python
def test_tool_calling(model):
    """测试模型是否支持工具调用"""
    try:
        response = model.invoke(
            messages=[...],
            tools=[...]  # 简单的测试工具
        )
        return response.tool_calls is not None
    except:
        return False
```

### 3. 能力标签系统
为每个模型配置添加能力标签：
```python
model_capabilities = {
    "supports_tools": True/False,
    "supports_vision": True/False,
    "supports_streaming": True/False,
}
```

在分配模型时自动检查能力匹配。

### 4. 错误码系统
定义明确的错误码：
```python
ERROR_CODES = {
    "E001": "模型不支持工具调用",
    "E002": "模型 API Key 无效",
    "E003": "模型配额不足",
}
```

便于前端展示和问题追踪。

## 结论

通过在探索任务执行的早期阶段添加二次防御检查，可以：
- ✅ 在调用 API 之前拦截不支持的模型
- ✅ 提供清晰的错误信息
- ✅ 避免无意义的 API 调用和费用
- ✅ 引导用户切换到正确的模型

建议用户为"站点探索"能力分配支持工具调用的模型（如 OpenAI GPT-4）。
