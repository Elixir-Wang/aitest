# 知识库智能体与 Karpathy llm-wiki 实施 Spec

## 背景

当前知识库页面已有项目知识库/公司知识库页签，但项目知识库仍是静态空表。已有 PRD 要求项目知识库使用 Karpathy `llm-wiki` 思路：基于已确认需求版本和已完成探索结果生成模块化 Markdown wiki，不使用向量检索。

## 目标

- 新增 `KnowledgeBuilderAgent`，绑定本地 `karpathy_llm_wiki` skill。
- 提供项目知识库生成、列表、详情、页面查看和发布 API。
- 生成 `knowledge/KB-xxx/` 目录，包含 `AGENTS.md`、`index.md`、`modules/`、`maps/`、`quality/`、`testing/`、`build/`。
- 前端知识库页面接入真实项目知识库接口，支持生成、查看构建、发布。

## 非目标

- 不实现向量检索。
- 不实现公司知识库上传和管理。
- 不实现完整异步任务队列；本次沿用当前后端同步 Agent 调用风格，后续再接 TaskRun。
- 不自动把待确认问题、阻塞项、未确认冲突写入正式知识条目。

## 数据准入

项目知识库首版输入：

- 当前项目下有 `current_version_id` 的需求文档版本。
- 当前项目下状态为 `completed` 或 `partial` 的探索结果。

阻塞规则：

- 没有可用需求版本时，构建状态为 `blocked`。
- 存在打开的需求归并冲突时，构建状态为 `blocked`。
- 探索阻塞项只进入 `build/build-blockers.md`，不进入正式模块知识。

## API

- `GET /api/v1/projects/{project_id}/knowledge/builds`
- `POST /api/v1/projects/{project_id}/knowledge/builds`
- `GET /api/v1/projects/{project_id}/knowledge/builds/{build_id}`
- `POST /api/v1/projects/{project_id}/knowledge/builds/{build_id}/publish`
- `GET /api/v1/projects/{project_id}/knowledge/builds/{build_id}/pages/{page_id}`

## 产物结构

```text
knowledge/
  KB-001/
    AGENTS.md
    index.md
    log.md
    00-项目总览.md
    01-模块索引.md
    modules/
    maps/
      source-reference-matrix.md
      module-source-map.md
      page-requirement-map.md
    quality/
      stale-claims.md
      lint-report.md
    testing/
      test-focus.md
      risk-paths.md
      state-flows.md
    build/
      build-summary.md
      update-plan.md
      build-blockers.md
      conflict-check.md
```

## 验收标准

- 当前项目下可点击生成项目知识库。
- 后端生成 KnowledgeBuild、WikiPage、KnowledgeItem、SourceReference。
- 列表展示构建编号、状态、来源数、页面数、更新时间。
- 详情页可查看 wiki 页面列表、lint、阻塞、来源引用。
- 草稿/阻塞构建不能用于正式下游；发布后状态为 `published`。
- 后端测试和前端 lint/build 不新增失败。
