# 站点探索日志服务端分页规范

## 背景

当前探索日志接口 `GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/log` 返回完整 `logs/run.log` 内容，前端再解析、筛选和分页。

这种方式只是视觉分页，不是真正分页。随着探索页面、动作和 edge 增多，完整加载会带来：

- 首次进入日志 tab 慢。
- 前端一次性解析大量日志行，内存和 CPU 成本高。
- 刷新日志时重复传输完整文件。
- 分页器语义不真实，切页不会减少网络和解析成本。
- 后续实时日志、关键字筛选和错误定位难以扩展。

因此，探索日志应改为后端按 `run.log` 行解析、筛选、分页，前端只请求当前页。

## 目标

- 后端从 `logs/run.log` 读取日志行，解析为结构化日志项。
- 探索日志接口支持 `page`、`page_size`、`keyword`、`type`、`level`、`page_ref` 等查询参数。
- 后端返回分页后的 `items`、`total`、`page`、`page_size`。
- 前端分页器切页、切每页条数和筛选条件变化时重新请求后端。
- 保留 `run.log` 作为唯一日志事实源，不新增第二套日志文件。
- 保留短期兼容：老前端仍可读取 `log_content`，新前端优先使用分页 `items`。

## 非目标

- 不把探索日志写入 `operation_logs`。
- 不新增日志数据库表。
- 不新增 `events.jsonl`。
- 不把完整 `run.log` 默认返回给前端。
- 不实现全文索引、ELK、OpenSearch 或外部日志平台。
- 不强制迁移旧探索 run。

## 现状依据

当前相关代码：

- API：`apps/backend/app/api/v1/exploration.py`
- Service：`apps/backend/app/services/exploration_service.py`
- Schema：`apps/backend/app/schemas/exploration.py`
- 前端探索页：`apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- 日志产物：`apps/backend/data/projects/{project_id}/exploration/{run_id}/logs/run.log`

当前接口：

```http
GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/log
```

当前响应：

```json
{
  "run_id": "explore-123",
  "log_content": "...完整 run.log...",
  "log_path": "project-1/exploration/explore-123/logs/run.log",
  "updated_at": "2026-05-30T10:00:00"
}
```

## 接口设计

### 路径

继续复用现有接口：

```http
GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/log
```

### 查询参数

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `page` | int | `1` | 页码，从 1 开始 |
| `page_size` | int | `10` | 每页条数 |
| `keyword` | string | 空 | 搜索摘要、原始行、URL、页面、动作、结果、产物路径 |
| `type` | string | 空 | 事件类型或事件分类 |
| `level` | string | 空 | `info`、`warning`、`error` |
| `page_ref` | string | 空 | 页面 ID、页面标题或 URL |
| `include_raw_content` | bool | `false` | 兼容开关；仅显式请求时返回完整 `log_content` |

约束：

- `page < 1` 时按 `1` 处理。
- `page_size` 最大值建议 `100`。
- 未识别 `type` 不报错，按无匹配返回空列表。
- 未识别 `level` 不报错，按无匹配返回空列表。

### 响应结构

```json
{
  "run_id": "explore-123",
  "log_path": "project-1/exploration/explore-123/logs/run.log",
  "updated_at": "2026-05-30T10:00:00",
  "items": [
    {
      "id": "log-000001",
      "timestamp": "2026-05-30 17:57:18",
      "event": "run_started",
      "event_label": "探索开始",
      "category": "run",
      "level": "info",
      "page_id": "",
      "page_title": "",
      "url": "https://example.test",
      "action_name": "",
      "result": "",
      "artifact_path": "",
      "summary": "开始探索 https://example.test",
      "raw": "{\"ts\":\"2026-05-30T09:57:18.357Z\",\"event\":\"run_started\"}",
      "payload": {
        "ts": "2026-05-30T09:57:18.357Z",
        "event": "run_started"
      }
    }
  ],
  "total": 123,
  "page": 1,
  "page_size": 10,
  "log_content": ""
}
```

说明：

- `items` 是分页后的日志项。
- `total` 是筛选后的总条数，不是完整文件总行数。
- `log_content` 默认为空字符串，只有 `include_raw_content=true` 时返回完整内容。
- `payload` 保留 JSON 行的原始结构化字段。
- 非 JSON 行也必须返回为一条 `raw` 日志项。

## 日志解析规则

### JSON Lines

runner 当前日志行多为 JSON Lines，例如：

```json
{"ts":"2026-05-30T09:57:18.357Z","event":"run_started","url":"https://example.test"}
```

后端解析规则：

- `timestamp` 来源：`ts`、`time`、`timestamp`。
- `event` 来源：`event`。
- `page_id` 来源：`page_id`、`page`、`source`。
- `page_title` 来源：`page_title`、`title`。
- `url` 来源：`url`、`target`。
- `action_name` 来源：`action`、`name`、`locator_hint`。
- `result` 来源：`status`、`reason`、`type`、`target`、`edge_id`。
- `artifact_path` 来源：`artifact_path`、`evidence_path`、`file_path`、`log_path`。

### 原始文本或堆栈

非 JSON 行必须兜底为：

```json
{
  "event": "raw",
  "event_label": "原始日志",
  "category": "raw",
  "level": "error 或 info",
  "summary": "原始行文本",
  "raw": "原始行文本",
  "payload": {}
}
```

如果原始文本包含 `error`、`traceback`、`typeerror`、`exception`、`failed`、`失败` 等关键词，`level` 设为 `error`。

### 分类规则

| event | category |
| --- | --- |
| `run_started`、`run_completed`、`login_*` | `run` |
| `page_*`、`accessibility_captured` | `page` |
| `action_*`、`edge_created` | `action` |
| `artifact_written` | `artifact` |
| `blocked` | `blocked` |
| `safety_blocked` | `safety` |
| `error` | `error` |
| 非 JSON 或未知 | `raw` |

### 级别规则

- 显式 `level` 为 `info`、`warning`、`error` 时直接使用。
- `event=error` 或 `status=failed` 时为 `error`。
- `blocked`、`safety_blocked`、`skipped` 为 `warning`。
- 其他为 `info`。

## 筛选规则

后端先解析日志，再应用筛选，最后分页。

筛选顺序：

1. `keyword`
2. `type`
3. `level`
4. `page_ref`
5. pagination

`keyword` 搜索字段：

- `summary`
- `raw`
- `url`
- `page_title`
- `page_id`
- `action_name`
- `result`
- `artifact_path`

`type` 可匹配：

- 具体事件名：`run_started`、`edge_created`
- 分类名：`run`、`page`、`action`、`blocked`、`error`、`safety`、`raw`

`page_ref` 可匹配：

- `page_id`
- `page_title`
- `url`

## 前端设计

探索日志前端改为服务端分页：

- `page`、`pageSize`、`keyword`、`category/type`、`level`、`page_ref` 变化时请求接口。
- 不再默认请求或解析完整 `log_content`。
- 表格只渲染接口返回的 `items`。
- 分页器的 `total` 使用接口返回值。
- 查看详情弹窗使用当前行的 `payload`、`raw`、上下文字段。

前端兼容策略：

1. 如果响应存在 `items`，使用 `items`。
2. 如果响应没有 `items` 但有 `log_content`，临时 fallback 到前端解析。
3. fallback 仅用于兼容旧后端，不作为长期路径。

## 后端实现建议

新增内部解析函数，避免 API 层处理日志：

- `parse_exploration_log_entries(log_content: str) -> list[dict]`
- `filter_exploration_log_entries(entries: list[dict], filters: dict) -> list[dict]`
- `paginate_exploration_log_entries(entries: list[dict], page: int, page_size: int) -> tuple[list[dict], int, int]`

这些函数可放在：

- `apps/backend/app/services/exploration_service.py`

如果后续复杂度上升，再拆到：

- `apps/backend/app/services/exploration_log_service.py`

第一阶段不需要单独拆服务。

## Schema 变更

新增：

```python
class ExplorationLogItemOut(BaseModel):
    id: str
    timestamp: str = ""
    event: str = "raw"
    event_label: str = "原始日志"
    category: str = "raw"
    level: str = "info"
    page_id: str = ""
    page_title: str = ""
    url: str = ""
    action_name: str = ""
    result: str = ""
    artifact_path: str = ""
    summary: str = ""
    raw: str = ""
    payload: dict = {}


class ExplorationLogOut(BaseModel):
    run_id: str
    log_content: str = ""
    log_path: str = ""
    updated_at: str | None = None
    items: list[ExplorationLogItemOut] = []
    total: int = 0
    page: int = 1
    page_size: int = 10
```

## API 变更

API 函数增加 query 参数：

```python
def get_project_run_log(
    project_id: str,
    run_id: str,
    page: int = 1,
    page_size: int = 10,
    keyword: str = "",
    type: str = "",
    level: str = "",
    page_ref: str = "",
    include_raw_content: bool = False,
    actor=Depends(current_user),
) -> dict:
```

## 验收标准

1. 探索日志 tab 首次打开只请求第一页日志，默认 `page_size=10`。
2. 切页时重新请求后端，不再本地 slice 完整日志。
3. 修改每页条数时重新请求后端，页码回到 1。
4. 关键词、类型、级别、页面筛选变化时重新请求后端，页码回到 1。
5. 表格总数来自后端 `total`。
6. 后端默认不返回完整 `log_content`。
7. 老 run 的纯文本错误日志仍能展示为 `raw` 项。
8. 旧前端兼容字段 `log_content` 仍存在，但默认为空。
9. 权限逻辑沿用现有探索日志接口。

## 测试要求

后端测试：

- JSON Lines 能解析为结构化 `items`。
- 纯文本/堆栈能解析为 raw/error。
- `page`、`page_size` 正确分页。
- `keyword` 能筛选摘要、URL、原始行。
- `type` 能筛选事件名和分类。
- `level` 能筛选 `error`。
- `page_ref` 能筛选页面。
- `include_raw_content=false` 时不返回完整日志。
- 权限和不存在 run 的行为不变。

前端验证：

- 初次打开只请求 `page=1&page_size=10`。
- 点击下一页请求下一页。
- 筛选变化请求后端并回到第一页。
- 查看详情弹窗使用当前行字段，不依赖完整 `log_content`。

## 迁移策略

第一阶段：

- 后端扩展现有接口，默认返回分页 `items`。
- 前端优先使用 `items`。
- 保留 `log_content` 字段但默认空。

第二阶段：

- 前端删除本地完整日志解析主路径，仅保留兼容 fallback。
- 若所有部署都升级完成，可移除 `include_raw_content` 的默认使用场景。

第三阶段：

- 如日志文件规模继续增大，可优化为按行流式读取和筛选，避免后端一次性读完整文件。

