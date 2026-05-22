# Agents 目录结构重设计

## 背景

当前 `apps/backend/app/agents` 同时存在三类概念：

- 框架级运行代码，例如 `registry.py`、`runtime.py`、`definitions.py`、`skill_loader.py`。
- 智能体目录，例如当前的 `raw_requirement_format_converter`；`raw_requirement_analyzer` 属于后续需求分析阶段，本次先不注册。
- 公共 skills 目录，例如 `apps/backend/app/agents/skills/pdf-to-markdown`、`docx-to-markdown`。

这个结构让“智能体注册”“skill 注册”“上传文件转换时查找 skill”产生了多套来源。结果是：用户把 skill 放进后端公共目录后，上传 PDF 的转换逻辑仍然没有使用该目录，而是继续查用户目录或回退到内置 parser。

本次重设计的目标是让目录本身表达运行边界：每个智能体目录拥有自己的定义和可用 skills；框架目录只负责发现、运行和加载。上传文件接口属于后端业务服务，不属于 Agent Runtime。

## 设计目标

1. 移除 `apps/backend/app/agents/skills` 作为公共 skills 池的运行语义。
2. 每个智能体一个目录，目录名就是智能体能力边界。
3. 智能体定义文件统一使用 `*_agent.py` 结尾。
4. 每个智能体目录下的 `skills/` 只存储该智能体可能调用的 skill。
5. 注册逻辑只从智能体目录发现 `*_agent.py` 和该目录下的 `skills/`。
6. 文件上传格式转换由 `app.services.requirement_file_converter` 提供确定性服务，不进入大模型 Agent Runtime。
7. 需要大模型判断的需求解析、评审、知识库生成等能力再进入 Agent Runtime。

## 目标目录结构

```text
apps/backend/app/agents/
  __init__.py
  definitions.py
  registry.py
  runtime.py
  skill_loader.py

  raw_requirement_format_converter/
    __init__.py
    raw_requirement_format_converter_agent.py
    skills/
      pdf_to_markdown/
        SKILL.md
        package.json
        package-lock.json
        scripts/
          convert.cjs
          lib/
      docx_to_markdown/
        SKILL.md
        package.json
        package-lock.json
        scripts/
          convert.cjs
          lib/

```

说明：

- `__init__.py` 只保留包初始化，不承载 `agent_definition`。
- `*_agent.py` 是智能体定义入口，必须导出 `agent_definition`。
- `skills/` 放该智能体可使用的技能，技能可以包含 Python tool，也可以包含 Node CLI、模板、测试等资源。
- 上传接口所需的确定性文件转换服务放在 `apps/backend/app/services/requirement_file_converter.py`，不放进智能体目录。

## 注册与发现规则

### Agent 发现

`AgentRegistry` 扫描：

```text
apps/backend/app/agents/*/*_agent.py
```

每个 `*_agent.py` 必须导出：

```python
agent_definition = AgentDefinition(...)
```

注册时使用 `agent_definition.id` 作为唯一键。目录名和 `agent_definition.id` 原则上保持一致，便于定位。

### Skill 发现

`SkillRegistry` 不再扫描 `apps/backend/app/agents/skills`。

新的 skill 加载规则：

1. 读取某个 agent 的 `agent_definition.skill_ids`。
2. 只在该 agent 目录下的 `skills/` 查找对应 skill。
3. skill id 来自 `SKILL.md` frontmatter 的 `name`，没有时使用目录名。
4. 若多个智能体需要相同能力，应复制或显式放入各自目录，不通过公共池隐式共享。

这样可以避免“上传文件转换到底用的是谁的 pdf-to-markdown”这种不清晰状态。

## 原始需求格式转换链路

上传 PDF、DOCX、TXT、MD 属于后端上传服务职责，不属于 Agent Runtime 职责。`raw_requirement_format_converter` 智能体只注册可在模型运行中使用的真实转换 skill。

目标链路：

```text
document_service
→ requirement_file_converter.convert_requirement_file_to_markdown(...)
→ raw_requirement_format_converter/skills/pdf_to_markdown/scripts/convert.cjs
→ markdown/conversions/{mapping_id}.md
→ 文件映射 conversion_status / conversion_summary
```

规则：

- `.md`、`.markdown`、`.txt`：直接解码保存为 Markdown 转换稿。
- `.pdf`：优先调用该智能体目录内 `pdf_to_markdown` skill 的 `convert.cjs`。
- `.doc`、`.docx`：优先调用该智能体目录内 `docx_to_markdown` skill 的 `convert.cjs`。
- 工具缺失、依赖缺失或执行失败时，返回明确失败原因。
- `conversion_summary` 必须写明实际使用的转换路径，例如 `已通过 pdf_to_markdown skill 转换`。
- `raw_requirement_format_converter_agent.py` 的 `skill_ids` 只包含 `("pdf_to_markdown", "docx_to_markdown")`，不再存在同名 wrapper skill。

## Agent Runtime 使用边界

文件格式转换默认不进入大模型 Agent Runtime，因为它是确定性工具执行。

Agent Runtime 用于以下场景：

- 需求语义解析。
- 待确认问题识别。
- 需求评审。
- 知识库生成。
- 测试用例设计。
- 自动化代码生成。
- 失败诊断和自愈建议。

这样可以保持转换链路可测试、可审计，也避免为了转换文件而额外依赖模型配置。

## 迁移步骤

1. 新增 registry 发现规则：扫描 `*/*_agent.py`。
2. 为 `raw_requirement_format_converter` 新增 `raw_requirement_format_converter_agent.py`。
3. 将 `apps/backend/app/agents/skills/pdf-to-markdown` 移入 `raw_requirement_format_converter/skills/pdf_to_markdown`。
4. 将 `apps/backend/app/agents/skills/docx-to-markdown` 移入 `raw_requirement_format_converter/skills/docx_to_markdown`。
5. 删除或停用 `apps/backend/app/agents/skills` 公共目录的运行语义。
6. 更新 `skill_loader`，让它支持按 agent 目录加载 skills。
7. 更新 PDF/DOCX 转换查找逻辑，只查 `raw_requirement_format_converter/skills/...`。
8. 更新测试，覆盖 agent 发现、skill 发现、PDF skill 路径和 fallback 摘要。
9. 清理旧 `__pycache__`、旧公共 skill 文件和无效测试期文件。

## 验证要求

至少覆盖以下验证：

- `agent_registry.list()` 当前只发现 `raw_requirement_format_converter`；`raw_requirement_analyzer` 后续需求分析阶段再加入。
- `raw_requirement_format_converter` 的 `skill_ids` 能从自身目录加载。
- 上传 PDF 时，若 `pdf_to_markdown` 依赖完整，`conversion_summary` 显示使用该 skill。
- 上传 PDF 时，若 skill 缺依赖，错误信息包含缺失依赖和 skill 路径。
- 上传 MD 时仍直接保存内容，不进入 PDF/DOCX 转换逻辑。
- 需求详情页能读取 `markdown/conversions/*.md`。
- 归并动作仍负责生成标准工作稿版本，不和单文件转换混淆。

## 非目标

- 本次设计不改需求业务状态流转。
- 本次设计不改变项目级标准工作稿必须通过归并生成的规则。
- 本次设计不引入全局公共 skill 池。
- 本次设计不要求所有文件转换都通过大模型运行。
