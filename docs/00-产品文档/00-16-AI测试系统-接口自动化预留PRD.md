# 00-16 AI测试系统 - 接口自动化预留 PRD

## 1. 这份文档解决什么问题

接口自动化是后续能力，第一期只做导航占位、数据模型扩展点和技术栈约定，不提供接口用例生成、代码生成、执行和报告归档。

核心规则：

- 第一版左侧导航展示“接口自动化”，标记 `Soon`。
- 接口自动化不可选择或只进入占位说明页。
- 不允许创建接口自动化任务。
- 不允许生成 pytest + requests 代码。
- 不统计接口自动化覆盖率、执行结果或报告。
- 后续技术栈预留为 pytest + requests + Allure。

---

## 2. 一期范围

### 2.1 一期做

- 左侧导航展示入口。
- 页面展示 Soon 占位说明。
- 数据模型预留自动化类型字段：UI、API。
- 报告中心预留接口自动化报告类型，但不展示统计数据。
- 系统设置中可保留接口自动化后续说明。

### 2.2 一期不做

- 不上传 OpenAPI 后生成接口用例。
- 不生成 requests 代码。
- 不执行接口测试。
- 不生成接口 Allure 报告。
- 不做接口断言配置。
- 不做接口环境和变量管理。

---

## 3. 占位页面

路由：

- `/projects/:projectId/automation/api`

展示内容：

- 标题：接口自动化 Soon。
- 说明：后续支持基于 pytest + requests + Allure 的接口自动化。
- 当前状态：第一期未开放。
- 禁用操作：创建接口套件、生成代码、执行测试、查看报告。
- 可展示规划能力，但不能出现可操作表单。

---

## 4. 后续预留能力

| 能力 | 后续说明 |
| --- | --- |
| 接口来源 | OpenAPI、Postman、抓包、人工录入 |
| 接口用例 | 参数组合、边界值、鉴权、错误码、幂等 |
| 代码生成 | pytest + requests |
| 报告 | Allure |
| 环境管理 | base_url、headers、token、变量 |
| 数据依赖 | 前置接口、清理接口、数据提取 |
| 与 UI 自动化关系 | 可作为 UI 自动化前置数据准备 |

---

## 5. 数据模型预留

以下字段需要在相关表中预留：

| 表/对象 | 字段 | 说明 |
| --- | --- | --- |
| TestCase | automation_type | UI、API、NONE |
| AutomationSuite | suite_type | UI、API |
| AutomationRun | run_type | UI、API |
| AutomationRunReport | report_type | UI、API |
| ModelProfile | usage | api_test_generation 预留 |

---

## 6. 验收标准

- 左侧导航能看到接口自动化入口。
- 接口自动化入口显示 `Soon`。
- 点击后不能创建、生成、执行接口自动化。
- 控制台不统计接口自动化指标。
- 报告中心不展示接口自动化报告数据。
- 代码生成 Agent 不生成 requests 代码。
