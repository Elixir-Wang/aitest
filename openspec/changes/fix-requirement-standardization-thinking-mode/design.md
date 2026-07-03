# 修复方案

## 方案

在 `app/agents/requirement_standardization/service.py` 的 `convert_requirement_file` 中，将

```python
model = build_agent_model(selection)
```

改为与 `app/agents/knowledge/service.py::run_knowledge_agent` 同款的写法：构造一个 `_thinking_extra_body(selection, show_thinking=False)`，对 `_supports_thinking_toggle(selection)` 返回 True 的 provider 产出 `{"thinking": {"type": "disabled"}}`，再透传给 `build_agent_model(selection, extra_body=...)`。

考虑到 `requirement_standardization` 历史上是一个独立模块、与 `knowledge` 之间无服务依赖，新增的 5–8 行辅助函数**就近内联在 `requirement_standardization/service.py`** 中，避免跨模块依赖意外扩散（保持现有分层）。

伪代码：

```python
def _thinking_extra_body(selection) -> dict | None:
    if not _supports_thinking_toggle(selection):
        return None
    return {"thinking": {"type": "disabled"}}

def _supports_thinking_toggle(selection) -> bool:
    provider = str(selection.provider).strip().lower()
    model = str(selection.model).strip().lower()
    return "minimax" in provider or "minimax" in model or "deepseek" in provider or "deepseek" in model

async def convert_requirement_file(input_data):
    ...
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=_thinking_extra_body(selection))
    ...
```

> 注：与 `knowledge/service.py` 中的同等实现保持完全一致的命中规则（`minimax` / `deepseek`）。若后续官方通用化（提取到 `model_selection.py`）则属于后续 tweak，本次仅做最小修复。

## 风险与回滚

- 修改仅影响 `requirement_standardization` Agent 的模型构造参数。其他用途（上传转换、定向故障注入、本地手工标准化）的链路不变。
- 不引入新依赖、新接口，不修改数据库 schema。
- 失败可回滚到原 `build_agent_model(selection)`，等于本次 hotfix 的反向提交。

## 测试

- 重跑 `tests/test_raw_requirement_converter_agent.py`：
  - 其内 `monkeypatch.setattr(... "app.agents.requirement_standardization.service.build_agent_model", lambda selection: "model")` 会因为新调用传入了 `extra_body` 而 TypeError，需要在测试里改成 `lambda selection, *, extra_body=None: "model"`。
- 业务级行为验证（不开模型）：手工上传任意 `.md` 触发后台转换，确认最终落库 `conversion_status="success"`，`GET /requirement-files/{mapping_id}/markdown` 返回 200 而非 409。
- 全量仓库测试命令：`pytest apps/backend/tests/test_raw_requirement_converter_agent.py -q`。
