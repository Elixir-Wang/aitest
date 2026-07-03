# Fix: 需求标准化 Agent 在 thinking 模式下调用工具失败

## 问题描述

- **接口错误**：标准文件加载失败（HTTP 409，GET `/requirement-files/{docmapId}/markdown`）
- **错误码**：`DOCUMENT_CONVERSION_NOT_READY`
- **失败根因**（provider 报错 400）：
  ```
  Thinking mode does not support this tool_choice
  ```

前端拉取某条 `docmap-518bfb3f9a6b02bd`（同样出现过 `docmap-2f5741f03545f8ce`）的标准文件时，请求被后端 `get_converted_markdown` 拒绝。该接口在 `conversion_status` 不是 `success`/`warning` 时直接返回 409。后端日志链路显示：

```
获取待办记录上报 (400) 'Thinking mode does not support this tool_choice' code=invalid_request_error
→ RequirementConversionInput 被传入 requirement_standardization_agent
→ agent.ainvoke(...) 失败
→ convert_source_file_mapping 捕获异常后写入 conversion_status=failed，conversion_summary=原始异常文本
→ 下一次 GET /requirement-files/{mapping_id}/markdown 触发 409 + DOCUMENT_CONVERSION_NOT_READY
```

## 根因分析

`app/agents/requirement_standardization/service.py` 在调用 `build_agent_model(selection)` 时**没有传入 `extra_body` 关闭 thinking 模式**。当前 provider 端，模型默认启用 thinking，而 `requirement_standardization_agent` 使用 `langchain.agents.structured_output.ToolStrategy(RequirementConversionOutput)`，该策略在底层会把 `tool_choice` 设置为 `required`（或与 thinking 互斥的值）。当前 provider 在 thinking 开启时拒绝该 `tool_choice`，于是整次调用返回 400 上抛为异常。

对比同仓库里其他同样使用 `ToolStrategy` 的 agent：

| Agent | 是否传 `extra_body` 关闭 thinking | 状态 |
| --- | --- | --- |
| `app/agents/knowledge/service.py` (`run_knowledge_agent` / `stream_knowledge_agent`) | 是（`_thinking_extra_body(selection, show_thinking=False)`） | 正常 |

`requirement_standardization/service.py` 是当前唯一遗漏的同模式 agent，导致该路径下所有 `docmap-*` 的请求都不会成功落到 `ToolStrategy` 调用上，从而反复落回 `failed` + 409。

## 修复目标

让 `requirement_standardization` Agent 的 ChatOpenAI 调用，与 `knowledge` Agent 行为一致：识别支持 thinking 切换的 provider（`minimax`、`deepseek`），为它们发送 `{"thinking": {"type": "disabled"}}` 的 `extra_body`，使 `ToolStrategy` 发出的 `tool_choice` 不再与 thinking 模式冲突，保证候选 Markdown 能被模型消费并返回结构化结果。

## 修复范围

- 仅修改 `app/agents/requirement_standardization/service.py` 中构建模型的调用（约 1 行 + 复用 `thinking_disabled_extra_body` 或等价的局部实现）。
- 同步更新 `tests/test_raw_requirement_converter_agent.py` 中 monkeypatch `build_agent_model` 的两处调用，使其与新签名匹配（不强制将 `extra_body` 写为断言，只是 `lambda` 参数兼容）。
- 不改变接口、不改变数据库结构、不改变 Agent 业务语义。
- 预计影响文件：≤ 2 个，符合 hotfix 适用条件。
