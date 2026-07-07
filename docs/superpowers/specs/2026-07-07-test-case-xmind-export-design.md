# 测试用例 XMind 导出 Spec

## 背景

当前测试用例评审页已经存在独立页面：

- 前端页面：`apps/frontend/src/app/(main)/test-cases/[setId]/review/page.tsx`
- 后端 API：`apps/backend/app/api/v1/test_cases.py`
- 后端服务：`apps/backend/app/services/test_case_service.py`
- 后端 schema：`apps/backend/app/schemas/test_case.py`
- 前端 API 客户端：`apps/frontend/src/lib/api-client.ts`

评审页顶部右侧目前只有“返回列表”按钮。用户需要在该按钮右侧或同一操作区增加“导出测试用例”，将当前测试用例集导出为 `.xmind` 文件，便于测试人员在 XMind 客户端中继续整理、评审和流转。

本地 `xmind` skill 对“测试用例 XMind”已有结构规范：优先使用 XMind 8 legacy 格式，并按层级表达测试用例字段。本需求沿用该层级结构，但不导出 `tx:` 用例描述节点。

## 目标

- 在测试用例评审页顶部操作区增加“导出测试用例”按钮。
- 导出当前测试用例集下的全部测试用例。
- 导出文件格式为 `.xmind`。
- 后端生成 XMind 文件，前端只负责触发下载。
- XMind 文件使用 XMind 8 legacy 兼容格式。
- XMind 节点不包含 `tx:` 用例描述。
- 每条测试用例保留模块、优先级、标题、前置条件、步骤和预期结果。
- 导出接口需要复用现有项目可见性和测试用例集归属校验。
- 导出失败时，前端给出明确错误提示。

## 非目标

- 不生成 `tx:` 用例描述节点。
- 不支持选择部分测试用例导出。
- 不支持按当前筛选结果导出。
- 不支持 Excel、Markdown、CSV、TestRail 等其他格式。
- 不新增异步导出任务。
- 不把导出文件持久化到服务器文件库。
- 不改测试用例生成 Agent 的输出结构。
- 不改变现有评审、采纳、不采纳逻辑。
- 不引入本机 skill 脚本作为运行时依赖。

## 术语

### 测试用例集

`test_case_sets` 表中的一条记录，包含测试用例生成来源、状态、统计信息和归属项目。

### 测试用例

`test_cases` 表中的一条记录，包含标题、模块、优先级、前置条件、步骤、预期结果和评审状态。

### XMind legacy 格式

兼容 XMind 8 的 zip 包结构，至少包含：

```text
content.xml
META-INF/manifest.xml
```

本轮优先生成 legacy 格式，避免简化 Zen 包在桌面客户端中兼容性不足。

## 推荐方案

采用“后端同步生成二进制文件 + 前端 blob 下载”的方案。

原因：

- XMind 文件结构属于导出格式细节，应由后端统一生成，避免前端维护 zip/xml 细节。
- 当前前端已经有 `apiBlobRequest`，操作日志导出也已有 blob 下载范式。
- 当前测试用例集详情接口已经能查询全部 `cases`，后端导出可复用同一数据来源。
- 导出文件不需要长时间生成，第一版同步返回即可。
- 本地 skill 适合作为格式参考，不应成为服务端运行时路径依赖。

## 页面设计

### 按钮位置

页面：`/test-cases/{setId}/review?project={projectId}`

在 `PageShell.actions` 中将现有单按钮改为按钮组：

```tsx
<div className="flex items-center gap-2">
  <Button onClick={() => router.push("/test-cases")} variant="outline">
    <ChevronLeft className="size-4" />
    返回列表
  </Button>
  <Button onClick={exportTestCases} variant="outline">
    <Download className="size-4" />
    导出测试用例
  </Button>
</div>
```

用户截图中“返回列表”位于页面右上角。本轮按用户要求，将“导出测试用例”放在“返回列表”按钮右侧。

### 前端状态

新增状态：

```ts
const [exporting, setExporting] = useState(false);
```

导出中：

- 禁用“导出测试用例”按钮。
- 按钮可显示 `Loader2` 或保持 `Download` 图标并禁用。
- 成功后触发浏览器下载。
- 失败时用 `toast.error` 展示错误。

### 文件名

前端下载文件名优先使用后端 `Content-Disposition`，如果前端直接指定，则使用：

```text
{testCaseSet.name}.xmind
```

需要对文件名做简单清理，避免 `/ \ : * ? " < > |` 等字符影响 Windows 下载。

## 后端 API

### 导出 XMind

```http
GET /api/v1/projects/{project_id}/test-case-sets/{set_id}/export/xmind
```

权限：

- 复用 `current_user`。
- 管理员、测试工程师、访客均可在可见项目内导出。
- 项目不可见返回 `403`。
- 测试用例集不存在或不属于该项目返回 `404`。

响应：

```http
200 OK
Content-Type: application/vnd.xmind.workbook
Content-Disposition: attachment; filename="{safe_name}.xmind"

<binary xmind content>
```

无用例处理：

- 如果测试用例集存在但没有用例，仍允许导出。
- XMind 中保留根节点，并增加一个子节点：`暂无测试用例`。

### API 模块改动

文件：`apps/backend/app/api/v1/test_cases.py`

新增：

```python
@router.get("/{set_id}/export/xmind")
def export_project_test_case_set_xmind(project_id: str, set_id: str, actor=Depends(current_user)) -> Response:
    content, filename = test_case_service.export_test_case_set_xmind(project_id, set_id, actor)
    return Response(
        content=content,
        media_type="application/vnd.xmind.workbook",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

## 后端服务设计

文件：`apps/backend/app/services/test_case_service.py`

新增服务函数：

```python
def export_test_case_set_xmind(project_id: str, set_id: str, actor) -> tuple[bytes, str]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = test_case_repo.find_set_by_id(db, set_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "测试用例集不存在。")
        cases = [_serialize_case(case) for case in test_case_repo.list_cases_by_set(db, row["id"])]
    content = build_test_case_set_xmind(row, cases)
    return content, safe_xmind_filename(row["name"])
```

推荐将 XMind 生成细节放入独立模块，避免 `test_case_service.py` 继续膨胀：

```text
apps/backend/app/services/test_case_xmind_exporter.py
```

职责：

- 接收测试用例集名称和已序列化用例列表。
- 按模块分组。
- 生成 XMind legacy `content.xml`。
- 打包为 zip bytes。
- 清理文件名。

## XMind 层级结构

导出结构：

```text
Sheet: {测试用例集名称}测试用例

{测试用例集名称}
- {模块名}
  - tc-{priority}: {用例标题}
    - pc: {前置条件}
    - 步骤1: {操作描述}
      - 结果1: {预期结果}
    - 步骤2: {操作描述}
      - 结果2: {预期结果}
```

字段映射：

| XMind 节点 | 来源字段 | 规则 |
| --- | --- | --- |
| 根节点 | `test_case_set.name` | 空值兜底为 `测试用例集` |
| 模块节点 | `case.module` | 空值兜底为 `未分组` |
| 用例节点 | `case.priority` + `case.title` | 例如 `tc-p0: 登录成功` |
| 前置条件 | `case.preconditions` | 空值兜底为 `pc: 无` |
| 步骤节点 | `case.steps[].action` | 从 1 开始编号 |
| 结果节点 | `case.steps[].expected_result` | 为空时兜底 `case.expected_result` |

明确不导出：

```text
tx: 用例描述
```

### 优先级规范

`case.priority` 归一为小写：

```text
P0 -> p0
P1 -> p1
P2 -> p2
其他 -> 原值 trim 后小写
空值 -> p2
```

用例节点格式：

```text
tc-p0: 用例标题
```

### 步骤兜底

如果某条用例没有结构化步骤：

```text
- 步骤1: 未提供测试步骤
  - 结果1: {case.expected_result 或 未提供预期结果}
```

## XMind 文件生成

### legacy zip 内容

第一版最小内容：

```text
content.xml
META-INF/manifest.xml
```

`content.xml` 使用 XMind 8 常见命名空间：

```xml
<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0" version="2.0">
  <sheet id="...">
    <title>...</title>
    <topic id="...">
      <title>...</title>
      <children>
        <topics type="attached">
          ...
        </topics>
      </children>
    </topic>
  </sheet>
</xmap-content>
```

实现要求：

- 使用 Python 标准库 `zipfile` 与 `xml.etree.ElementTree`。
- 不手写 XML 字符串拼接。
- 所有节点标题由 XML 库处理转义。
- topic id 可用 `uuid.uuid4().hex` 或稳定递增 id。
- zip 写入内存 `io.BytesIO` 后返回 bytes。

### 文件名清理

```python
def safe_xmind_filename(value: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", value.strip()) or "test-cases"
    return f"{name}.xmind"
```

如果需要支持中文文件名，后续可补 `filename*=`。第一版可先保持现有下载模式，前端也可指定下载文件名。

## 前端实现

文件：`apps/frontend/src/app/(main)/test-cases/[setId]/review/page.tsx`

新增导入：

```ts
import { Check, ChevronLeft, ChevronRight, CircleX, Download, Loader2, Pencil, Search, X } from "lucide-react";
import { apiBlobRequest, apiRequest } from "@/lib/api-client";
```

新增函数：

```ts
async function exportTestCases() {
  if (!testCaseSet || !projectId) return;
  setExporting(true);
  try {
    const blob = await apiBlobRequest(`/projects/${projectId}/test-case-sets/${testCaseSet.id}/export/xmind`);
    downloadBlob(blob, `${safeDownloadName(testCaseSet.name)}.xmind`);
    toast.success("测试用例已导出");
  } catch (requestError) {
    toast.error(requestError instanceof Error ? requestError.message : "测试用例导出失败");
  } finally {
    setExporting(false);
  }
}
```

可在页面内新增局部 helper，或后续抽公共下载工具：

```ts
function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
```

## 错误处理

后端错误：

| 场景 | 状态码 | 错误码 | 文案 |
| --- | --- | --- | --- |
| 项目不存在 | 404 | `NOT_FOUND` | 项目不存在。 |
| 无项目权限 | 403 | `PERMISSION_DENIED` | 无权访问该项目。 |
| 用例集不存在 | 404 | `NOT_FOUND` | 测试用例集不存在。 |
| XMind 生成失败 | 500 | `TEST_CASE_XMIND_EXPORT_FAILED` | 测试用例导出失败。 |

前端错误：

- 使用 `toast.error` 展示接口返回文案。
- 导出失败后恢复按钮可点击。
- 不清空当前页面数据。

## 验收标准

- 评审页右上角显示“导出测试用例”和“返回列表”两个按钮。
- 点击“导出测试用例”会下载 `.xmind` 文件。
- 文件可以作为 zip 打开，并包含 `content.xml` 与 `META-INF/manifest.xml`。
- `content.xml` 中包含测试用例集名称。
- `content.xml` 中按模块分组展示用例。
- 用例节点格式为 `tc-p0: 用例标题`、`tc-p1: 用例标题` 或 `tc-p2: 用例标题`。
- 每条用例包含 `pc:` 前置条件节点。
- 每个步骤节点下包含对应 `结果N:` 节点。
- 导出内容不包含 `tx:` 节点。
- 无用例的测试用例集也能导出，文件中显示 `暂无测试用例`。
- 无权限或不存在的用例集不能导出。

## 测试计划

### 后端单元测试

新增或更新：`apps/backend/tests/test_test_case_set_service.py`

覆盖：

- `export_test_case_set_xmind` 返回 bytes 和 `.xmind` 文件名。
- 导出 zip 包包含 `content.xml` 与 `META-INF/manifest.xml`。
- XML 中包含测试用例集名称、模块名、`tc-p0:`、`pc:`、`步骤1:`、`结果1:`。
- XML 中不包含 `tx:`。
- 空用例集导出包含 `暂无测试用例`。
- 项目不可见时返回 403。
- 用例集不属于项目时返回 404。

### 后端 API 测试

可增加 FastAPI TestClient 覆盖：

- `GET /projects/{project_id}/test-case-sets/{set_id}/export/xmind` 返回 200。
- `Content-Type` 为 `application/vnd.xmind.workbook`。
- `Content-Disposition` 包含 `.xmind`。

### 前端契约测试

更新：`apps/frontend/tests/test-case-review-page-contract.test.mjs`

断言：

- 页面包含 `导出测试用例`。
- 页面导入 `Download`。
- 页面调用 `apiBlobRequest`。
- 请求路径包含 `/test-case-sets/${testCaseSet.id}/export/xmind` 或等价模板。
- 页面存在 `downloadBlob` 或复用公共下载 helper。

## 建议实施顺序

1. 新增 `test_case_xmind_exporter.py`，完成 legacy XMind bytes 生成。
2. 在 `test_case_service.py` 增加 `export_test_case_set_xmind`。
3. 在 `test_cases.py` 增加导出 API。
4. 补后端导出测试。
5. 在评审页增加导出按钮和下载逻辑。
6. 补前端契约测试。
7. 执行后端目标测试与前端目标测试。

## 验证命令

后端：

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_test_case_set_service.py
```

前端：

```powershell
cd apps/frontend
npm test -- tests/test-case-review-page-contract.test.mjs
```
