# 需求最终化独立智能体规范

## 背景

当前需求分析流程已经能够产出：

- 初步需求 Markdown
- 澄清问题列表
- 已处理 / 未处理的澄清答复

但“转为最终需求”这一步目前要把初步需求直接落成版本，而不是让一个专门的智能体把以下信息真正汇总成一份结构化最终文档：

- 主需求标准 Markdown
- 需求分析结果
- 已处理的 P0 / P1 / P2 / P3 澄清项
- 源需求文件内容

本需求要补齐的是一个**单独的最终需求生成智能体**，它与需求分析智能体同属一条业务链，但职责不同。

最终产物不是重新生成一份泛化的“需求说明书模板”，而是以当前**标准需求文件**为主骨架，把已处理的澄清答复回填到原章节对应段落里，形成新的最终需求版本。

## 目标

- 新增一个独立的 `requirement_finalization` 智能体目录。
- 该智能体复用 `requirement_analysis` 的模型配置，不新增模型分配入口。
- “转为最终需求”时，由后端组装上下文并交给最终需求生成智能体。
- 最终生成一份结构清晰、适合展示和后续测试用例生成的 Markdown 文档。
- P2 / P3 若未处理，默认视为无需处理，不传给模型，也不在最终文档里单独展开。
- P0 / P1 若未处理，不允许进入最终化生成。
- 保留现有 `/analysis/finalize` API 入口和版本体系。

## 非目标

- 不新增第二套模型配置项。
- 不把前端改成拼装最终需求内容后再提交给模型。
- 不把最终化逻辑塞回 `requirement_analysis` 目录。
- 不改变现有需求分析结果的核心契约。
- 不重做需求分析页面整体交互。

## 推荐目录结构

```text
apps/backend/app
├─ agents
│  ├─ capabilities.py
│  ├─ model_selection.py
│  ├─ requirement_analysis
│  │  ├─ __init__.py
│  │  ├─ agent.py
│  │  ├─ middleware.py
│  │  ├─ schemas.py
│  │  ├─ service.py
│  │  ├─ system_prompt.py
│  │  └─ skills/...
│  └─ requirement_finalization
│     ├─ __init__.py
│     ├─ agent.py
│     ├─ schemas.py
│     ├─ service.py
│     ├─ system_prompt.py
│     └─ skills/
│        └─ requirement-finalization/
│           ├─ SKILL.md
│           └─ references/
│              └─ finalization-writing.md
├─ services
│  └─ document
│     ├─ service.py
│     ├─ finalization_context.py
│     ├─ file_service.py
│     └─ serializer.py
├─ repositories
│  ├─ document_repo.py
│  └─ requirement_clarification_answer_repo.py
└─ schemas
   └─ document.py
```

前端不新增独立页面，只改需求详情页的按钮显示和 finalize 调用条件。

## 架构选择

### 方案 A

独立 `requirement_finalization` 智能体目录，服务层复用 `requirement_analysis` 的模型配置。

优点：

- 目录职责清晰
- 未来可独立演化 prompt / schema / skill
- 不增加用户模型配置复杂度

### 方案 B

把最终化逻辑放进 `requirement_analysis` 目录下作为子模块。

缺点：

- 容易把“分析”和“最终生成”混在一起
- 后续 prompt 会越来越长
- 目录语义不够清楚

### 结论

采用 **方案 A**。

## 运行边界

### 1. 前端只做展示和触发

前端仅判断：

- 需求分析已完成
- 当前不是阻塞状态
- P0 / P1 已全部处理

满足后显示“转为最终需求”按钮。

### 2. 后端负责上下文组装

后端从数据库和文件系统读取：

- 当前初步需求
- 主需求标准文件
- 已处理澄清项


### 3. 智能体只负责生成最终 Markdown

最终化智能体不负责：

- 查数据库
- 读文件路径
- 写版本
- 写操作日志
- 判断按钮是否可点

## 模型复用规则

最终化智能体**复用需求分析模型**，即：

```text
resolve_model_selection("requirement_analysis")
```

不新增 `requirement_finalization` 的模型能力项。

## 数据输入规则

### 允许进入模型的内容

- 初步需求 Markdown
- 主需求标准 Markdown
- 辅助需求标准 Markdown
- 已处理的 P0 / P1 / p2 / p3 澄清答复

### 不进入模型的内容

- 未处理的 P0 / P1 / p2 / p3 条目
- 原始数据库字段
- 前端临时状态

### P2 / P3 规则

如果 P2 / P3 没处理，默认视为**无需处理**：

- 不阻塞最终化
- 不进入模型输入
- 不在最终文档里单独展开成问题清单

所有“无需处理”的结论都只保留在内部记录中，不进入模型输入。

如果后端需要保留痕迹，只记录在内部 diff / log，不写进最终文档正文。

## 智能体目录设计

### `agent.py`

职责：

- 创建最终需求生成智能体
- 使用结构化输出
- 绑定 `requirement-finalization` skill

建议结构：

```python
def requirement_finalization_agent(model, load_references: bool = True):
    ...
```

### `schemas.py`

职责：

- 定义最终化输入输出 schema
- 只保留最小必要字段

建议输入：

```python
class RequirementFinalizationInput(BaseModel):
    document_name: str
    standard_markdown: str
    preliminary_markdown: str
    primary_document: FinalizationSourceDocument
    supporting_documents: list[FinalizationSourceDocument] = Field(default_factory=list)
    handled_clarifications: list[HandledClarification] = Field(default_factory=list)
    no_op_clarifications: list[HandledClarification] = Field(default_factory=list)
```

建议输出：

```python
class RequirementFinalizationOutput(BaseModel):
    final_requirement_markdown: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    unresolved_notes: list[str] = Field(default_factory=list)
    merge_notes: list[str] = Field(default_factory=list)
```

### `system_prompt.py`

职责：

- 固化最终需求文档的写作规则
- 明确不能编造事实
- 明确 P2 / P3 无需处理时不要展开

## 最终 Markdown 结构

最终需求文档应**保持标准需求文件的章节骨架**，在原有章节中增强澄清内容，而不是改造成新的通用规格模板。

要求：

- 以标准文件现有结构为主，不重排业务主线
- 已处理澄清项优先写回其对应章节
- 如果某条澄清影响范围横跨多个章节，则分别回填到相关章节中
- 不把未处理的 P2 / P3 条目直接展开成问题清单
- 不输出碎片化聊天风格内容
- 不新增“澄清增强内容”“遗留说明”这类独立模块

### 增强规则

#### 1. 章节内增强

如果澄清答复明确对应某个标准章节，优先直接增强该章节内容，例如：

- 业务规则补进“规则”小节
- 状态变更补进“状态流转”小节
- 页面交互补进“交互说明”小节
- 数据字段补进“数据与系统交互”小节

#### 2. 多章节回填

如果某条澄清自然影响多个章节，则分别回填到相关章节中，不再抽象成末尾汇总模块。

#### 3. 遗留信息处理

对于确实需要保留的遗留信息，仅允许以下处理方式：

- 作为原章节中的“待确认/暂缓/补充说明”句子出现
- 作为原章节中的列表项或表格备注出现
- 作为与相关业务规则同级的约束说明出现

不得单独生成“遗留说明”章节。

## 后端上下文组装

新增 `services/document/finalization_context.py`，职责如下：

1. 读取最新需求分析结果。
2. 读取当前主需求文件和辅助文件内容。
3. 读取已处理澄清项。
4. 判断是否存在未处理 P0 / P1。
5. 过滤掉未处理的 P2 / P3。
6. 组装最小化的最终化输入。

### 过滤规则

- `P0` / `P1`：
  - `applied` 算已处理
  - `not_applicable` 算已处理
  - `open` 禁止最终化
- `P2` / `P3`：
  - 未处理默认视为无需处理
  - 不传给模型

## 服务层改造

`apps/backend/app/services/document/service.py` 的 `finalize_requirement_analysis()` 改为：

1. 校验分析结果是否为最新。
2. 校验 P0 / P1 是否都已处理。
3. 调用 finalization context 组装输入。
4. 调用独立 finalizer agent。
5. 将最终 Markdown 写入版本文件。
6. 继续沿用 `requirement_analysis_finalize` 版本动作。

版本写入仍保持现有版本体系，不新增独立文档类型。

## API 保持

现有接口保持不变：

```http
POST /projects/{project_id}/requirements/{document_id}/analysis/finalize
```

请求体保持：

```json
{
  "analysis_id": "xxx",
  "confirm_unresolved": false
}
```

不在前端新增“把文件和答复一起提交给模型”的接口。

## 前端交互

需求详情页只做两件事：

1. 在 P0 / P1 都处理完后显示“转为最终需求”按钮。
2. 点击按钮后继续调用现有 finalize 接口。

若 P2 / P3 未处理，不影响按钮显示，也不需要特殊提示。

## 测试策略

### 后端测试

新增测试覆盖：

- finalization context 是否过滤掉未处理 P2 / P3
- finalization context 是否阻止未处理 P0 / P1
- finalizer agent 是否走 `requirement_analysis` 模型配置
- finalizer 输出是否能写回标准文件原有章节
- finalizer 输出是否能保持标准 Markdown 的章节骨架
- `finalize_requirement_analysis()` 是否写入新版本而不是初步需求原文

### 前端测试

新增或更新 contract test：

- P0 / P1 未处理时不显示 finalize 按钮
- P0 / P1 已处理时显示 finalize 按钮
- finalize 后仍切换到“最终需求” tab

## 验收标准

- 存在独立的 `apps/backend/app/agents/requirement_finalization` 目录。
- finalizer 复用 `requirement_analysis` 的模型分配。
- P2 / P3 未处理时默认视为无需处理，不进模型。
- P0 / P1 未处理时禁止最终化。
- 最终产物是一份基于标准文件骨架增强后的结构化 Markdown，而不是简单拼接稿。
- 现有 `/analysis/finalize` API 不变。
- 最终版本继续进入现有需求版本体系。

## 推荐结论

采用以下组合：

```text
独立 requirement_finalization 智能体
复用 requirement_analysis 模型配置
后端组装最终化上下文
P2 / P3 默认无需处理且不进入模型
最终输出基于标准文件骨架增强后的 Markdown
```

这套方案既保持目录语义清楚，又不会把模型配置和产品流程弄复杂。
