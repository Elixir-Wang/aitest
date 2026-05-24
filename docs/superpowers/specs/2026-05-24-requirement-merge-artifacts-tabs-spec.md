# 需求归并四产物与顶部 Tab 展示规范

## 目标

需求标准文档合并后，先生成一组可审计的归并产物，而不是直接把智能体输出写成正式版本。

本期只落地四个产物：

```text
previews/mergerun-xxx.md       合并候选稿
mappings/mergerun-xxx.md       段落映射
conflicts/mergerun-xxx.md      明显冲突
reports/mergerun-xxx.md        归并质量报告
```

前端在归并结果区域顶部提供 Tab 切换，用户可以在同一页面查看这四个文件。

本规范不包含后续“需求分析报告”“澄清问答”“正式版本确认”的完整流程；这些应作为下一阶段能力接在归并质量报告之后。

## 核心原则

- 合并候选稿是给业务、产品、研发、测试阅读的候选需求文档。
- 映射、冲突、质量报告是给审计和确认使用的辅助文档。
- 候选稿正文不得显示源文件名、`docmap-*`、来源文档分组。
- 来源追溯只能出现在段落映射、冲突文档和质量报告中。
- 四个文件必须绑定同一个 `merge_run_id`，文件名统一使用 `mergerun-xxx.md`。
- 质量报告未通过时，不允许写入 `versions/vN.md`。

## 目录结构

每个需求文档目录下增加四个目录：

```text
requirements/
  doc-xxx/
    raw/
    standard/
    versions/
    previews/
      mergerun-xxxx.md
    mappings/
      mergerun-xxxx.md
    conflicts/
      mergerun-xxxx.md
    reports/
      mergerun-xxxx.md
```

目录职责：

| 目录 | 职责 |
| --- | --- |
| `previews/` | 保存合并候选稿 |
| `mappings/` | 保存来源段落到候选稿章节的映射 |
| `conflicts/` | 保存明显冲突清单 |
| `reports/` | 保存归并质量检查结果 |

## 产物一：合并候选稿

文件路径：

```text
previews/{merge_run_id}.md
```

用途：

- 展示本次归并后的候选需求文档。
- 作为后续需求分析和澄清的输入。
- 不是正式版本，不能替代 `versions/vN.md`。

推荐结构：

```markdown
# {需求名称}

## 需求概述

说明本次候选稿的确认范围和业务目标。

## {业务模块}

### {能力或规则组}

- 需求描述。
- 约束条件。
- 验收要点。

## 待澄清问题

- 仅放低风险、不会被误读为已确认事实的问题。
```

内容规则：

- 必须按业务模块组织，不得按源文件组织。
- 不得出现源文件名、源文档标题、`docmap-*`、`mapping_id`。
- 不得出现“来源文档一”“源文件二”“原始文件”“标准文件”等分组标题。
- 背景介绍、阅读建议、目录页、附件提示、转换说明不得进入正文。
- 冲突未解决时，冲突内容不得作为已确认需求写入正文。
- 模糊但不冲突的内容可以进入“待澄清问题”，不能写成确定需求。

## 产物二：段落映射

文件路径：

```text
mappings/{merge_run_id}.md
```

用途：

- 证明每个来源片段在候选稿中有明确去向。
- 发现遗漏、误删、错误合并。
- 给后续审计、回归分析和人工确认使用。

推荐结构：

```markdown
# 段落映射

## 覆盖统计

| 指标 | 数量 |
| --- | ---: |
| 来源文件数 | 2 |
| 来源片段数 | 120 |
| 已合入 | 80 |
| 重复去重 | 20 |
| 明显冲突 | 3 |
| 待澄清 | 8 |
| 不可测试 | 6 |
| 已丢弃 | 3 |
| 未覆盖 | 0 |

## 映射明细

| fragment_id | 来源文件 | 来源标题 | 来源摘要 | 状态 | 目标章节 | 原因 |
| --- | --- | --- | --- | --- | --- | --- |
| frag-001 | docmap-001 | 登录认证 | 支持手机号登录 | merged | 登录认证 / 登录方式 | 合入登录方式要求 |
```

状态枚举：

| 状态 | 含义 |
| --- | --- |
| `merged` | 已合入候选稿 |
| `duplicate` | 与其他片段重复，已去重 |
| `conflict` | 存在明显冲突，进入冲突文档 |
| `pending_clarification` | 不明确，需要澄清 |
| `not_testable` | 背景、说明、阅读建议等不可测试内容 |
| `discarded` | 明确丢弃 |
| `missing` | 未被处理，属于阻塞问题 |

强规则：

- 每个来源片段必须有一条映射。
- `merged` 必须有目标章节。
- `duplicate` 必须说明被哪条需求覆盖。
- `conflict` 必须关联冲突编号。
- `discarded` 必须有明确原因。
- `missing` 数量大于 0 时，质量报告必须为 `failed`。

## 产物三：明显冲突

文件路径：

```text
conflicts/{merge_run_id}.md
```

用途：

- 展示来源之间不能同时成立的内容。
- 给业务或产品做决策。
- 阻止冲突内容被误写进候选稿或正式版本。

推荐结构：

```markdown
# 明显冲突

## 冲突统计

| 严重级别 | 数量 |
| --- | ---: |
| high | 1 |
| medium | 2 |
| low | 0 |

## C001 首期是否包含 SLO

### 冲突类型

scope_overlap

### 严重级别

high

### 来源 A

- 来源文件：docmap-xxx
- 来源标题：非建设范围
- 摘要：首期不强制全局登出。

### 来源 B

- 来源文件：docmap-yyy
- 来源标题：验收标准
- 摘要：SLO 生效。

### 影响

如果首期包含 SLO，会增加认证中心与产品侧登出联动实现范围。
如果首期不包含 SLO，验收标准需要调整。

### 智能体建议

建议确认 V1 是否强制包含 SLO。

### 决策状态

open
```

冲突类型：

| 类型 | 含义 |
| --- | --- |
| `contradiction` | 直接互斥 |
| `mutual_exclusion` | 两种规则不能同时执行 |
| `scope_overlap` | 版本范围或建设范围冲突 |
| `obsolete_rule` | 新旧规则冲突 |

强规则：

- 只要存在互斥内容，必须进入冲突文档。
- 冲突未解决时，候选稿不得把任一冲突侧写成已确认事实。
- 冲突文档可以为空，但必须生成文件，写明“本次未发现明显冲突”。

## 产物四：归并质量报告

文件路径：

```text
reports/{merge_run_id}.md
```

用途：

- 判断本次归并是否可信。
- 给前端展示可执行的质量结论。
- 决定是否允许进入后续需求分析、澄清或正式版本写入。

推荐结构：

```markdown
# 归并质量报告

## 结论

failed

## 输入信息

| 指标 | 值 |
| --- | --- |
| 合并运行 | mergerun-xxxx |
| 合并模式 | initial |
| 来源文件数 | 2 |
| 来源片段数 | 120 |
| 基线版本 | 无 |

## 质量检查

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 来源片段覆盖完整 | failed | 存在 3 个 missing 片段 |
| 候选稿无源文档结构 | passed | 未发现源文件名或 docmap |
| 冲突已隔离 | failed | SLO 冲突仍出现在候选稿正文 |
| 待澄清已隔离 | warning | 存在 5 个待澄清问题 |
| 正文可读性 | passed | 按业务模块组织 |

## 阻塞问题

- 存在 missing 映射，不能写入正式版本。
- SLO 范围冲突未解决。

## 非阻塞问题

- 部分需求缺少明确验收标准，建议进入后续需求分析。
```

质量结论：

| 结论 | 含义 |
| --- | --- |
| `passed` | 可以进入后续需求分析或人工确认 |
| `warning` | 可以展示候选稿，但需要用户注意 |
| `failed` | 不允许写正式版本，必须修复或人工处理 |

必须检查：

- 是否所有来源片段都有映射。
- 是否存在 `missing`。
- 是否存在源文件名、`docmap-*`、来源文档分组进入候选稿。
- 是否存在冲突内容进入候选稿正文。
- 是否存在 `coverage_items` 过少或为空。
- 是否所有输入文件都出现在映射中。
- 是否生成了四个产物文件。

## 后端行为

### 合并运行成功但需要人工确认

当智能体正常返回候选稿，且质量报告为 `passed` 或 `warning`：

- 写入 `previews/{merge_run_id}.md`
- 写入 `mappings/{merge_run_id}.md`
- 写入 `conflicts/{merge_run_id}.md`
- 写入 `reports/{merge_run_id}.md`
- 更新 `requirement_merge_runs.status = preview`
- 不写入 `versions/vN.md`

接口返回：

```json
{
  "status": "preview",
  "preview_id": "mergerun-xxxx",
  "artifact_tabs": [
    {
      "key": "preview",
      "label": "合并候选稿",
      "path": "previews/mergerun-xxxx.md",
      "content": "# 官网登录sso..."
    },
    {
      "key": "mapping",
      "label": "段落映射",
      "path": "mappings/mergerun-xxxx.md",
      "content": "# 段落映射..."
    },
    {
      "key": "conflicts",
      "label": "明显冲突",
      "path": "conflicts/mergerun-xxxx.md",
      "content": "# 明显冲突..."
    },
    {
      "key": "report",
      "label": "质量报告",
      "path": "reports/mergerun-xxxx.md",
      "content": "# 归并质量报告..."
    }
  ],
  "quality_result": "warning"
}
```

### 合并运行存在明显冲突

当存在明显冲突：

- 仍生成四个产物。
- `previews/{merge_run_id}.md` 可以是候选稿，也可以是“因冲突未生成完整候选稿”的说明。
- `conflicts/{merge_run_id}.md` 必须列出冲突明细。
- `reports/{merge_run_id}.md` 结论必须为 `failed`。
- 不写入 `versions/vN.md`。

接口返回：

```json
{
  "status": "preview",
  "preview_id": "mergerun-xxxx",
  "quality_result": "failed",
  "conflict_count": 2,
  "artifact_tabs": []
}
```

说明：本期前端只依赖 `artifact_tabs` 展示四个文件；为了兼容旧逻辑，可以继续保留 `conflict_count` 和 `conflicts` 字段。

## 前端展示

位置：

```text
需求详情页 > 标准文件/归并区域
```

顶部增加 Tab：

```text
合并候选稿 | 段落映射 | 明显冲突 | 质量报告
```

展示规则：

- 默认选中“合并候选稿”。
- 每个 Tab 展示对应 Markdown 文件内容。
- Tab 不使用卡片嵌套卡片；保持当前页面的文档预览样式。
- 如果某个文件为空，展示该文件中的空状态文案，而不是前端硬编码空状态。
- `quality_result = failed` 时，在 Tab 上方显示阻塞提示。
- `conflicts` 数量大于 0 时，“明显冲突”Tab 显示数量徽标。
- `report` 结论为 `failed` 时，“质量报告”Tab 显示失败状态。

按钮规则：

- “确认写入版本”按钮只有在 `quality_result = passed` 且没有 open conflict 时可用。
- `warning` 状态可以允许人工确认，但按钮文案应体现风险，例如“确认并写入版本”。
- `failed` 状态禁用写入版本。
- 后续需求分析入口应放在质量报告之后，不在本期强行接入。

## 验收标准

- 点击合并后，后端生成四个 Markdown 文件。
- 四个文件路径均在 `requirements/{doc_id}/` 下对应目录。
- 接口返回四个 Tab 的 key、label、path、content。
- 前端顶部 Tab 可切换查看四个文件。
- 合并候选稿不出现源文件名、`docmap-*`、来源文档分组。
- 段落映射包含覆盖统计和映射明细。
- 明显冲突文档即使无冲突也会生成。
- 质量报告包含 `passed`、`warning` 或 `failed` 结论。
- `failed` 时不能写入正式版本。
- 现有 `raw/standard/versions/previews` 目录语义不被破坏。

## 非目标

- 本期不实现需求分析报告。
- 本期不实现澄清问答闭环。
- 本期不实现知识库生成。
- 本期不实现测试用例生成。
- 本期不新增独立“分析智能体”。
- 本期不改变原始文件和标准文件预览逻辑。
