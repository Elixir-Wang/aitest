---
name: markdown_normalize
display_name: Markdown 规范化
description: 修复原始需求文件转换后的 Markdown 结构问题，包含业务流程链路、误包代码块和异常换行。
enabled: true
---

对候选 Markdown 做确定性结构规范化。

使用规则：
- 业务链路、登录流程、操作流程、系统交互流程不能放入代码块。
- 只有明确表达跨步骤流程链路、登录流程、操作流程、系统交互流程，且转换后不会损失原文层级/条件说明时，才可转换为 Mermaid 流程图代码块，优先使用 `flowchart TD`。
- 标题为“业务逻辑”“处理逻辑”“规则说明”“判断规则”一类的内容，若主体是条件判断、字段取值、状态映射、接口返回 action、数据库存在性判断等说明，应保持为普通 Markdown 列表/段落/表格，不要转换为 Mermaid。
- 不要仅因为文本中出现多个 `↓`、`→`、`如果/存在/不存在` 就转换为 Mermaid；这些符号在规则说明中应按原文语义保留或整理为列表。
- Mermaid 节点 label 外层使用双引号时，label 内部不得保留英文双引号；JSON 示例、提示文案中的 `"` 必须改为单引号或中文引号，避免 Mermaid 解析失败。
- 代码块只保留给真实代码、命令、配置和日志。
- 不新增、不推断、不改写业务含义，只修复 Markdown 结构。

智能体处理候选 Markdown 时应先调用 `normalize_requirement_markdown_tool`，再基于工具结果做质量检查和 JSON 输出。
