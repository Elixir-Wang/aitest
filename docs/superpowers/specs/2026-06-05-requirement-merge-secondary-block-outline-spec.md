# 需求合并二级来源块与二级大纲归属 Spec

## 背景

当前需求合并链路曾采用“旧文档标题树 -> AI 生成二三级目标大纲 -> 旧节点归属目标章节 -> 逐章合并”的方案。该方案的问题是：

1. 大纲阶段输入字段过多，例如 `level`、`node_role`、`must_assign`、完整 `children` 节点树。
2. `children` 作为完整子节点树会浪费 token，且容易让 AI 误以为子节点也需要独立归属。
3. 大纲阶段没有读取正文，却要求生成三级目标标题，容易生成看似精确但缺少正文依据的目录。
4. 三级标题本质上更适合在模块正文生成阶段，根据真实来源块内容自动生成。
5. 原始来源块按三级标题拆分会破坏二级主题上下文，尤其会拆散接口说明、表格、示例、流程图和补充规则。

本规范将需求合并主路径调整为：

```text
阶段 1：按二级标题抽取原始来源块
阶段 2：AI 生成新的二级大纲，并输出来源块到新二级模块的归属
阶段 3：后端按新二级模块分组来源块
阶段 4：AI 在每个二级模块内基于真实正文生成三级结构和正文
阶段 5：后端组装初始需求、产物和质量结果
```

## 目标

- 原始来源块默认只按二级标题拆分，不按三级标题拆分。
- 三级及更深标题只作为来源块内的 `children`/`sub_headings` 字符串列表，用于帮助 AI 理解该二级块覆盖内容。
- 大纲阶段只生成新二级框架，不生成三级标题，不生成正文。
- 大纲阶段同时输出来源块归属关系：旧二级块被放到哪个新二级模块。
- 模块正文阶段再基于归属块的真实 Markdown 自动生成三级标题和正文。
- 每个来源块必须且只能归属一个新二级模块。
- 保留来源块覆盖、冲突、质量检测和调试产物，便于人工审计。

## 非目标

- 不恢复 fragment 级段落、列表项、表格、代码块拆分。
- 不在大纲阶段生成三级标题。
- 不在大纲阶段传完整 Markdown 正文。
- 不让 AI 在一个步骤里同时完成大纲、归属和正文合并。
- 不让后端根据业务含义私自创造需求规则。
- 不让冲突内容绕过人工确认写入正式版本。

## SourceBlock 抽取

### 抽取粒度

标准 Markdown 按二级标题切分来源块：

```markdown
# 统一登录需求

## SSO 登录

### login_ticket 生成
...

### ticket 校验
...

## 账号映射

### 统一 UID
...
```

生成：

```json
[
  {
    "id": "A-01",
    "title": "SSO 登录",
    "children": ["login_ticket 生成", "ticket 校验"]
  },
  {
    "id": "A-02",
    "title": "账号映射",
    "children": ["统一 UID"]
  }
]
```

规则：

- 一级标题只作为文档标题，不形成来源块。
- 二级标题形成一个完整来源块。
- 二级标题下的正文、列表、表格、代码块、Mermaid、图片说明全部保留在同一个来源块内。
- 三级及更深标题只提取标题文本，写入 `children`/`sub_headings`。
- 即使二级块很大，也不按三级标题拆成多个来源块。
- 如果全文没有二级标题，后端可以生成一个 `全文` 来源块。

### 内部完整结构

后端内部可以保留完整来源块：

```json
{
  "block_id": "A-01",
  "source_code": "A",
  "mapping_id": "docmap-001",
  "source_file": "统一登录需求.md",
  "original_heading": "SSO 登录",
  "heading_path": ["SSO 登录"],
  "sub_headings": ["login_ticket 生成", "ticket 校验"],
  "markdown": "## SSO 登录\n\n### login_ticket 生成\n...",
  "content_hash": "sha256:..."
}
```

但大纲阶段只发送精简索引：

```json
{
  "id": "A-01",
  "title": "SSO 登录",
  "children": ["login_ticket 生成", "ticket 校验"]
}
```

## 阶段 1：生成新二级大纲与归属

### AI 输入

```json
{
  "document_name": "统一登录需求",
  "source_blocks": [
    {
      "id": "A-01",
      "title": "SSO 登录",
      "children": ["login_ticket 生成", "ticket 校验", "首次进入处理"]
    },
    {
      "id": "A-02",
      "title": "账号映射",
      "children": ["统一 UID", "本地账号绑定", "异常处理"]
    },
    {
      "id": "B-01",
      "title": "登录票据",
      "children": ["票据生成", "票据有效期", "票据校验"]
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `document_name` | 当前需求文档名称，后端最终作为一级标题 |
| `source_blocks[].id` | 来源块 ID，后续归属必须引用该值 |
| `source_blocks[].title` | 来源块二级标题 |
| `source_blocks[].children` | 该二级块下的三级及更深标题文本列表，只用于理解内容范围，不能被归属引用 |

禁止发送到阶段 1 的字段：

- `mapping_id`
- `source_file`
- `document_code`
- `level`
- `node_role`
- `must_assign`
- `has_content`
- 完整子节点对象
- `markdown`
- `plain_text`
- `own_body_markdown`

### AI 输出

```json
{
  "outline": [
    {
      "id": "module-login",
      "title": "统一登录与票据"
    },
    {
      "id": "module-account-mapping",
      "title": "统一账号映射"
    }
  ],
  "placements": [
    {
      "source_id": "A-01",
      "target_id": "module-login"
    },
    {
      "source_id": "B-01",
      "target_id": "module-login"
    },
    {
      "source_id": "A-02",
      "target_id": "module-account-mapping"
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `outline` | 新需求文档二级模块列表 |
| `outline[].id` | 新二级模块 ID，AI 生成，本次输出内唯一 |
| `outline[].title` | 新二级模块标题 |
| `placements` | 来源块到新二级模块的归属关系 |
| `placements[].source_id` | 输入 `source_blocks[].id` |
| `placements[].target_id` | 输出 `outline[].id` |

可选调试字段：

- `reason`：AI 归并理由。主链路不依赖该字段，产物可选择展示。

### Prompt 约束

Prompt 必须明确：

- 只输出 JSON。
- 只生成二级大纲，不生成三级标题。
- 不输出正文。
- `children` 只是来源块内部子标题文本，不能被 `placements.source_id` 引用。
- 每个 `source_blocks[].id` 必须且只能出现在 `placements` 中一次。
- `placements[].target_id` 必须来自 `outline[].id`。
- 不创造输入中没有依据的业务模块。
- 合并相似或重叠来源块时，以新二级模块承接多个 `source_id`。

### 后端校验

后端必须校验：

- `outline` 非空。
- `outline[].id` 唯一且非空。
- `outline[].title` 非空。
- `placements[].source_id` 都存在于输入 `source_blocks[].id`。
- 每个来源块 ID 出现且只出现一次。
- `placements[].target_id` 都存在于 `outline[].id`。
- `placements.source_id` 不允许引用 `children` 字符串。
- AI 输出不得包含正文 Markdown。
- AI 输出不得包含三级目录结构。

校验失败时：

- 不写正式版本。
- 写入阶段错误产物。
- 返回 preview 或 failed 状态，由现有质量门禁策略决定。

## 阶段 2：按二级模块生成三级结构和正文

后端根据 `placements` 分组：

```json
{
  "module-login": ["A-01", "B-01"],
  "module-account-mapping": ["A-02"]
}
```

然后逐个新二级模块调用 AI。

### AI 输入

```json
{
  "module": {
    "id": "module-login",
    "title": "统一登录与票据"
  },
  "source_blocks": [
    {
      "id": "A-01",
      "title": "SSO 登录",
      "children": ["login_ticket 生成", "ticket 校验", "首次进入处理"],
      "markdown": "## SSO 登录\n\n### login_ticket 生成\n..."
    },
    {
      "id": "B-01",
      "title": "登录票据",
      "children": ["票据生成", "票据有效期", "票据校验"],
      "markdown": "## 登录票据\n\n### 票据生成\n..."
    }
  ]
}
```

### AI 输出

```json
{
  "module_id": "module-login",
  "title": "统一登录与票据",
  "sections": [
    {
      "title": "登录入口与上下文",
      "content": [
        "系统应支持从业务系统跳转至统一登录入口。",
        "进入登录流程前应完成上下文预注册。"
      ]
    },
    {
      "title": "票据生成与校验",
      "content": [
        "login_ticket 由统一登录服务生成。",
        "业务系统应在服务端校验 ticket 的有效性和有效期。"
      ]
    }
  ],
  "coverage": [
    {
      "source_id": "A-01",
      "status": "merged"
    },
    {
      "source_id": "B-01",
      "status": "merged"
    }
  ],
  "conflicts": []
}
```

阶段 2 约束：

- 只处理当前 `module`。
- 只能读取当前模块归属的 `source_blocks`。
- 可以基于正文自动生成三级标题。
- 不要求沿用来源块的三级标题。
- 重复内容应合并。
- 明显冲突、口径不清、缺少决策依据的内容进入 `conflicts`，不得写成确定结论。
- 每个输入来源块必须出现在 `coverage` 中。

## 最终 Markdown 组装

后端按阶段 1 的 `outline` 顺序组装：

```markdown
# 统一登录需求

## 统一登录与票据

### 登录入口与上下文

系统应支持从业务系统跳转至统一登录入口。

### 票据生成与校验

login_ticket 由统一登录服务生成。

## 统一账号映射

### 统一 UID

...
```

## 用户可见与调试产物

建议写入：

```text
source-blocks.json
outline-placements.json
module-merge-results.json
merged-preview.md
mapping.md
quality.md
conflicts.md
stage-errors.json
```

`outline-placements.json` 使用精简格式：

```json
{
  "outline": [
    {
      "id": "module-login",
      "title": "统一登录与票据"
    }
  ],
  "placements": [
    {
      "source_id": "A-01",
      "source_title": "SSO 登录",
      "target_id": "module-login",
      "target_title": "统一登录与票据"
    }
  ]
}
```

`source_title` 和 `target_title` 由后端补全，不要求 AI 输出。

## 与现有实现的关系

当前实现中的以下概念应逐步替换：

| 现有概念 | 新方案 |
| --- | --- |
| `source_title_tree` | `source_blocks` 精简索引 |
| 完整 `children` 节点树 | `children` 三级标题字符串列表 |
| `must_assign` / `node_role` | 不传给大纲 AI |
| AI 输出二级、三级 `sections` | AI 输出二级 `outline` |
| `source_node_ids` 绑定目标叶子章节 | `placements` 绑定来源块到二级模块 |
| 大纲阶段生成三级标题 | 模块正文阶段基于正文生成三级标题 |

## 测试要求

SourceBlock 抽取：

- 一级标题不形成来源块。
- 二级标题形成一个完整来源块。
- 二级标题下的三级标题不拆成独立来源块。
- 即使 `max_chars` 很小，也不按三级标题拆分二级块。
- 二级标题下的表格、代码块、Mermaid、图片说明不被拆出去。
- `children`/`sub_headings` 能提取三级及更深标题文本。

阶段 1 大纲与归属：

- AI 输入不包含 `markdown`、`level`、`node_role`、`must_assign`。
- 输出 `outline` 只包含二级模块。
- 每个来源块必须且只能有一个 `placement`。
- `placement.target_id` 必须存在。
- `placement.source_id` 不能引用 `children` 字符串。

阶段 2 模块正文：

- 每个模块只接收归属给自己的来源块。
- AI 可以生成三级标题。
- 每个来源块必须有 coverage。
- conflicts 存在时不写正式版本。

## 验收标准

- 合并运行的大纲阶段 token 明显下降。
- 用户可在产物中看到“新二级大纲”和“旧二级块归属到哪个新模块”。
- 原始二级块不会因三级标题拆分而丢失上下文。
- 最终初始需求仍可生成三级结构，但三级结构来自模块正文生成阶段。
- 质量产物能追踪每个来源块的处理状态。
