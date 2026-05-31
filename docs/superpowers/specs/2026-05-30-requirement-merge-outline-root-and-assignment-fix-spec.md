# 需求文档合并：目标大纲根节点与旧大纲归属修复 Spec

## 背景

当前需求合并流程已改为大纲驱动：

1. 从多个旧需求文档抽取旧大纲节点。
2. AI 根据多个旧大纲生成新的统一目标大纲。
3. AI 将旧大纲节点归属到新目标大纲章节。
4. AI 按新大纲章节组合、去重、标记冲突。
5. 后端确定性渲染合并稿、映射稿、冲突稿。

本次实际运行出现：

```text
合并候选稿未生成
目标大纲生成失败：目标大纲章节 sect-001 层级不合法。
旧大纲归属生成失败：Expecting ',' delimiter: line 980 column 6 (char 25495)
```

排查结论：

- 旧大纲抽取成功，不是旧大纲生成失败。
- 本次源大纲包含 4 个文档、178 个旧大纲节点。
- AI 目标大纲阶段有返回内容，但当前校验只允许目标大纲 level 为 2/3/4。
- 正确业务规则是：目标大纲一级标题为需求名称，二级、三级标题由多个旧需求实际大纲综合生成。
- 当前系统把 AI 返回的一级标题误判为非法，导致 `target_outline` 被丢弃为空数组。
- 编排层没有 fail-fast，目标大纲失败后仍继续调用旧大纲归属阶段。
- 归属阶段在空目标大纲和 178 个旧大纲节点输入下继续要求 AI 输出长 JSON，最终返回非法 JSON。

## 目标

修复目标：

1. 目标大纲允许唯一 `level=1` 根节点。
2. `level=1` 根节点标题必须等于当前需求名称。
3. `level=2/3` 为 AI 根据多个旧需求文档一二三级标题综合生成的新业务大纲。
4. 旧大纲节点只允许归属到目标大纲 `level=2/3` 章节，不允许归属到 `level=1` 根节点。
5. 任一 AI 前置阶段失败后立即停止，不继续执行后续阶段。
6. 失败不兜底，不生成伪成功合并稿，不写正式版本。
7. 保存 AI 原始输出和阶段输入摘要，便于判断是 AI 质量问题还是校验问题。

## 非目标

本次不做：

- 不恢复旧 fragment 合并主流程。
- 不引入失败兜底大纲。
- 不在 AI 失败后用关键词规则伪造归属结果。
- 不自动修复 AI 返回的业务大纲语义。
- 不改前端大范围交互，只保证后端返回明确失败状态和可审计产物。

## 当前问题分析

### 问题 1：目标大纲层级契约错误

当前校验：

```python
if section.level not in {2, 3, 4}:
    issues.append(f"目标大纲章节 {section.section_id} 层级不合法。")
```

这与现行业务规则冲突。

正确规则：

```text
# 需求名称                level=1，唯一根节点
## 业务章节              level=2，AI 综合生成
### 子章节               level=3，AI 综合生成，可选
```

### 问题 2：旧大纲归属阶段依赖无效目标大纲

目标大纲失败后，当前编排仍继续：

```python
target_outline = generate_target_outline(...)
assignments = assign_source_outline_to_target(source_documents, target_outline)
section_results = merge_sections_by_target_outline(...)
```

当 `target_outline=[]` 时，归属阶段没有可用目标章节，不应继续执行。

### 问题 3：归属阶段一次输出过大

本次归属阶段输入包含 178 个旧大纲节点，输出需要 178 条 assignment。日志显示：

```text
prompt_len=57421
output_len=25500
```

在非强结构化输出模型下，一次性生成大 JSON 容易缺逗号、截断或混入解释文本。

本问题可以通过 fail-fast 先避免错误级联；后续可再做分批归属以提高稳定性。

### 问题 4：缺少原始 AI 输出审计

失败后当前只保存解析后的空数组：

```text
target-outline.json = []
outline-assignments.json = []
```

无法判断 AI 原始输出是否可修复、是否符合业务语义、是否只是校验规则误判。

## 目标大纲数据契约

### TargetOutlineSection

继续使用现有模型：

```python
class TargetOutlineSection(BaseModel):
    section_id: str
    parent_id: str = ""
    level: int
    title: str
    reason: str = ""
    children: list["TargetOutlineSection"] = Field(default_factory=list)
```

### 新契约

目标大纲必须满足：

1. 顶层 `outline` 只能有一个根节点。
2. 根节点 `level=1`。
3. 根节点 `title == document_name`。
4. 根节点 `parent_id == ""`。
5. 根节点 `children` 至少包含一个 `level=2` 章节。
6. `level=2` 章节的 `parent_id` 指向根节点 `section_id`。
7. `level=3` 章节的 `parent_id` 指向直接父级 `level=2` 章节。
8. 不允许 `level > 3`。
9. 不允许跳级，例如根节点下直接出现 `level=3`。
10. 所有 `section_id` 全局唯一。
11. 标题不得包含正文、换行、Markdown 代码块、表格符号。
12. 二三级标题应来自四个旧文档大纲的综合归纳，不要求照搬原顺序。

### 示例

```json
{
  "outline": [
    {
      "section_id": "root",
      "parent_id": "",
      "level": 1,
      "title": "百系产品接入官网统一认证中心",
      "reason": "统一需求文档根节点。",
      "children": [
        {
          "section_id": "sect-001",
          "parent_id": "root",
          "level": 2,
          "title": "背景与目标",
          "reason": "综合多个来源文档中的背景、目标、范围说明。",
          "children": []
        },
        {
          "section_id": "sect-002",
          "parent_id": "root",
          "level": 2,
          "title": "接入范围与职责边界",
          "reason": "归并接入范围、不接入范围、产品侧职责、认证中心职责。",
          "children": [
            {
              "section_id": "sect-002-001",
              "parent_id": "sect-002",
              "level": 3,
              "title": "接入范围",
              "reason": "承接旧文档中的接入产品、接入模式、范围边界。",
              "children": []
            }
          ]
        }
      ]
    }
  ]
}
```

## 旧大纲归属契约

### 输入

归属阶段输入：

- `target_sections`：目标大纲中可归属章节，只包含 `level=2/3`。
- `source_nodes`：旧大纲节点。

不把 `level=1` 根节点传给 AI 作为可归属目标。

### 输出

```json
{
  "assignments": [
    {
      "source_node_id": "A-01-02",
      "target_section_ids": ["sect-001"],
      "assignment_type": "primary",
      "reason": "旧节点为背景说明，归入背景与目标。"
    }
  ]
}
```

### 校验规则

1. 每个旧大纲节点必须出现一次。
2. 非 `discarded_non_requirement` 节点必须至少有一个 `target_section_ids`。
3. `target_section_ids` 只能指向目标大纲 `level=2/3` 章节。
4. 不允许指向 `level=1` 根节点。
5. 不允许未知 `source_node_id`。
6. 不允许未知 `target_section_id`。
7. `preserve_original=true` 的旧节点不得被标为 `discarded_non_requirement`。
8. 归属原因不能为空。

## 编排规则

新流程：

```text
build_source_outline
  -> generate_target_outline
      -> validate_target_outline
      -> failed 则停止
  -> assign_source_outline_to_target
      -> validate_assignments
      -> failed 则停止
  -> merge_sections_by_target_outline
      -> failed 则停止
  -> render
  -> quality
  -> passed 才写正式版本
```

### Fail-fast 规则

任何阶段失败：

1. 立即停止后续 AI 阶段。
2. 返回 `status=preview` 或现有失败预览状态。
3. `quality_result=failed`。
4. 不写正式需求版本。
5. 写入 `stage-errors.json`。
6. 写入已完成阶段产物。
7. 写入失败阶段原始输入摘要和原始 AI 输出。

### 禁止行为

失败后禁止：

- 使用默认大纲伪造成功。
- 使用关键词归属伪造成功。
- 继续执行依赖失败阶段的后续阶段。
- 写入正式版本。

## AI Prompt 调整

### 目标大纲 Prompt

必须明确：

```text
你只生成目标大纲，不生成正文。
目标大纲必须有且只有一个 level=1 根节点。
level=1 根节点 title 必须等于输入 document_name。
level=2/3 章节必须根据多个旧需求文档的一二三级标题综合生成。
禁止输出 level=4 或更深层级。
禁止把旧文档文件名直接作为业务章节，除非它本身就是需求名称。
section_id 必须稳定、唯一，建议 root、sect-001、sect-001-001。
只返回 JSON 对象，不要 Markdown 代码块，不要解释文字。
```

### 旧大纲归属 Prompt

必须明确：

```text
target_sections 只包含可归属章节。
不要把任何 source_node_id 归属到 level=1 根节点。
必须为每个 source_node_id 返回一条 assignment。
target_section_ids 只能使用输入 target_sections 中的 section_id。
如果旧节点只是文档封面、目录或阅读建议，且 preserve_original=false，可标记 discarded_non_requirement。
如果 preserve_original=true，不得 discarded_non_requirement。
只返回 JSON 对象，不要 Markdown 代码块，不要解释文字。
```

## 产物调整

保留现有：

```text
source-outline.json
target-outline.json
outline-assignments.json
section-merge-results.json
quality.json
stage-errors.json
```

新增内部调试产物：

```text
target-outline-raw.txt
outline-assignments-raw.txt
section-merge-raw/<section_id>.txt
outline-stage-input-summary.json
assignment-stage-input-summary.json
```

说明：

| 产物 | 用途 |
| --- | --- |
| `target-outline-raw.txt` | 保存目标大纲阶段 AI 原始输出 |
| `outline-assignments-raw.txt` | 保存旧大纲归属阶段 AI 原始输出 |
| `section-merge-raw/<section_id>.txt` | 保存每个章节合并阶段 AI 原始输出 |
| `outline-stage-input-summary.json` | 保存目标大纲阶段输入摘要、文档数、节点数、层级分布 |
| `assignment-stage-input-summary.json` | 保存归属阶段可归属章节数、旧节点数、是否含根节点 |

原始输出只用于排查，不作为成功结果。

## 实现点

### 1. 修改目标大纲校验

文件：

```text
apps/backend/app/services/requirement_merge_outline_service.py
```

修改：

- `validate_target_outline(outline, document_name)` 接收 `document_name`。
- 校验唯一根节点。
- 校验根节点 `level=1` 且标题等于 `document_name`。
- 校验子级只允许 `level=2/3`。
- 校验父子层级连续。
- 校验没有 `level=4`。

### 2. 修改目标大纲解析默认层级

当前 `_parse_outline` 默认：

```python
level=int(raw.get("level") or (3 if parent_id else 2))
```

应调整为：

- 无 `parent_id` 时默认 `level=1`。
- 根节点子级默认 `level=2`。
- 二级子级默认 `level=3`。

但缺少 level 本身仍应记录校验风险，不应静默掩盖 AI 契约问题。

### 3. 增加可归属章节过滤

文件：

```text
apps/backend/app/services/requirement_outline_assignment_service.py
```

新增：

```python
assignable_target_sections(target_outline) -> list[TargetOutlineSection]
```

只返回 `level in {2, 3}` 的章节。

Prompt 和校验都使用可归属章节集合。

### 4. 修改编排为 fail-fast

文件：

```text
apps/backend/app/services/document_merge_orchestrator.py
```

修改：

- 目标大纲失败后立即返回失败预览。
- 不调用 `assign_source_outline_to_target`。
- 归属失败后立即返回失败预览。
- 不调用 `merge_sections_by_target_outline`。
- 章节合并失败后立即返回失败预览。

### 5. 保存原始 AI 输出

文件：

```text
apps/backend/app/services/requirement_merge_artifact_service.py
```

修改：

- 支持写入 raw 文本产物。
- 不要求 raw 文本是 JSON。
- 失败时也保存已经拿到的 raw 输出。

服务返回值可扩展为：

```python
StageResult[T] = {
    "data": T,
    "errors": list[str],
    "raw_output": str | None,
    "input_summary": dict,
}
```

如果不想大改模型，可先在各服务返回三元组：

```python
return outline, errors, debug
```

其中 `debug` 包含 `raw_output` 和 `input_summary`。

## 测试要求

### 目标大纲校验测试

1. 允许唯一 `level=1` 根节点。
2. 根节点标题等于需求名称时通过。
3. 根节点标题不等于需求名称时失败。
4. 多个根节点失败。
5. 根节点下直接出现 `level=3` 失败。
6. 出现 `level=4` 失败。
7. `section_id` 重复失败。
8. 二级标题包含正文或换行失败。

### 旧大纲归属测试

1. 归属目标不包含 `level=1` 根节点。
2. assignment 指向根节点时失败。
3. assignment 指向二级章节时通过。
4. assignment 指向三级章节时通过。
5. 缺少旧节点归属时失败。
6. 未知旧节点失败。
7. 未知目标章节失败。
8. `preserve_original=true` 节点被忽略时失败。

### 编排测试

1. 目标大纲失败后不调用旧大纲归属服务。
2. 旧大纲归属失败后不调用章节合并服务。
3. 章节合并失败后不写正式版本。
4. 任一阶段失败返回 `quality_result=failed`。
5. 任一阶段失败写入 `stage-errors.json`。
6. AI 原始输出被写入 raw 产物。

### 回归测试

1. 正常四文档合并流程可生成：
   - `source-outline.json`
   - `target-outline.json`
   - `outline-assignments.json`
   - `section-merge-results.json`
   - `quality.json`
2. 合并稿一级标题为需求名称。
3. 合并稿正文从二级标题开始承载业务章节。
4. 映射稿覆盖所有旧大纲节点。
5. 冲突存在时不写正式版本。
6. 质量通过时才写正式版本。

## 验收标准

1. AI 生成一级根节点不再被误判为层级非法。
2. `target-outline.json` 保留完整一级、二级、三级目标大纲。
3. 旧大纲归属只归到二级、三级目标章节。
4. 目标大纲失败时，不再出现后续旧大纲归属 JSON 解析错误。
5. 旧大纲归属失败时，不再执行章节合并。
6. 所有失败都能在 `stage-errors.json` 和 raw 产物中定位原因。
7. 没有任何失败兜底会写入正式版本。
8. 单元测试和后端测试通过。

## 推荐实施顺序

1. 修改目标大纲校验，支持唯一一级根节点。
2. 调整目标大纲 prompt，明确一级为需求名称，二三级由旧大纲综合生成。
3. 增加可归属目标章节过滤，排除一级根节点。
4. 修改旧大纲归属 prompt 和校验。
5. 修改 orchestrator 为阶段 fail-fast。
6. 增加 raw 输出和输入摘要产物。
7. 补充单元测试和编排测试。
8. 使用当前四文档样本重新跑合并验证。

