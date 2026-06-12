# 待澄清报告

用于记录需求稳定前必须由人工确认、补充或裁决的事项。

## 目的

回答：哪些内容必须由人工确认、决策或补充。

## 运行时去向

待澄清事项进入：

- `clarification_questions`
- `conflicts`

不要把这些事项清单重复写入 `analysis_report_markdown`。

## 可解析 Markdown 格式

每个可点击事项必须使用下面的格式：

```markdown
## CQ-001 模块名
- 模块Key：module_key
- 类型：clarification
- 维度：validation_rule
- 严重级别：major
- 问题：直接面向人工确认的问题？
- 影响：不确认造成的下游影响。
- 来源：主需求中的证据或缺失说明。
- 选项A：短标签|可直接写入初步需求的 Markdown
- 选项B：短标签|可直接写入初步需求的 Markdown
```

冲突事项使用 `CF-001`，并设置 `类型：conflict`。

## 待澄清问题字段

每个问题必须包含：

- `id`：稳定 ID，例如 `CQ-001`
- `module_key`
- `module_name`
- `question`：直接面向人工的问题
- `impact`：不回答造成的下游影响
- `dimension`
- `severity`
- `source_excerpt`：有帮助时填写
- `recommended_options`：最多两个

`dimension` 只能使用：

- `boundary_value`
- `exception_path`
- `state_flow`
- `permission`
- `data_dependency`
- `message`
- `validation_rule`
- `concurrency`
- `time_related`
- `data_consistency`
- `scope`
- `other`

`severity` 只能使用：

- `blocker`：阻断有意义的实现或测试设计
- `major`：带来明显的实现、交互、数据或测试风险
- `minor`：提升精确度，但不阻断推进

## 冲突字段

以下情况使用 `conflicts`：

- 需求之间互相矛盾
- 证据明显不属于当前范围
- 来源证据薄弱或语义含混
- 来源归属不清

每个冲突必须包含直接的 `question`，说明需要人工裁决什么。

## 推荐选项

每个选项必须包含：

- `id`
- `label`
- `answer_markdown`
- `rationale`：有帮助时填写
- `confidence`

`answer_markdown` 必须能直接写入初步需求。不要只写 `方案一`、`默认方案` 这类标签，要命名具体业务决策。

## 问题质量

好：

```text
验证码连续输错达到多少次后应锁定登录尝试，锁定多久？
```

差：

```text
当前缺口：未说明验证码错误次数限制。
```

好：

```text
管理员是否可以代用户重置 MFA，还是只能引导用户自助重置？
```

差：

```text
权限规则不清楚。
```
