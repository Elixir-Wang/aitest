# 需求澄清方法论

本文档已并入项目级 skill：

```text
.agents/skills/requirements-analysis
```

新的需求分析架构将「需求理解」和「需求澄清」放在同一个 skill 中：

```text
需求输入
-> 需求理解
-> 待澄清内容生成
```

使用方式：

```text
使用 $requirements-analysis 分析需求，输出结构化需求理解和待澄清问题清单。
```

详细方法位置：

```text
.agents/skills/requirements-analysis/SKILL.md
.agents/skills/requirements-analysis/references/understanding.md
.agents/skills/requirements-analysis/references/clarification.md
```

质量保证内容不再放入该方法论中。风险分析、测试策略、验收标准、上线检查等内容后续移动到最终需求或独立质量保证流程。
