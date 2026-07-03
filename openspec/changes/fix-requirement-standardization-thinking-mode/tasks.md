# Tasks

## 1. 修复 `requirement_standardization/service.py` 的模型构造调用

- [ ] 在 `app/agents/requirement_standardization/service.py` 中新增 `_thinking_extra_body(selection)` 与 `_supports_thinking_toggle(selection)` 局部辅助函数，逻辑与 `app/agents/knowledge/service.py` 等价。
- [ ] 将 `convert_requirement_file` 中 `build_agent_model(selection)` 改为 `build_agent_model(selection, extra_body=_thinking_extra_body(selection))`。
- [ ] 运行 `pytest apps/backend/tests/test_raw_requirement_converter_agent.py -q`，确认结构调整后的测试可被跟进修改。

## 2. 同步调整对应测试的 `monkeypatch`

- [ ] 在 `tests/test_raw_requirement_converter_agent.py` 中，将两处 `lambda selection: "model"` 改为接受 `extra_body` 的签名（`lambda selection, *, extra_body=None: "model"`），避免 monkeypatch 站点报 TypeError。
- [ ] 重跑 `pytest apps/backend/tests/test_raw_requirement_converter_agent.py -q`，确保全部用例通过。

## 3. 根因复核

- [ ] 在代码中搜索 `ToolStrategy` 用法，确认所有使用 `ToolStrategy` 的 agent 都已在建模型阶段处理 `extra_body`，避免再次出现同类 409。
- [ ] 输出根因消除的复核结论到 `.comet.yaml` 之外的简短说明（commit message 里）。
