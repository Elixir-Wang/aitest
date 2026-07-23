# Learnings

## [LRN-20260713-001] correction

**Logged**: 2026-07-13T19:40:00+08:00
**Priority**: high
**Status**: resolved
**Area**: requirements

### Summary
对话流长文本需求中的10,000和20,000均为变量长度规则，不是请求或用户输入长度限制。

### Details
- 变量长度小于等于10,000字符时不外置，超过10,000字符时外置。
- 单个普通文本变量最大长度为20,000字符。
- 用户消息、API请求或节点输入不存在独立的20,000字符请求长度限制。
- 当内容被节点写入变量时，才执行变量长度校验。

### Source
- User correction

### Tags
requirements, long-text, variable-length, correction

## [LRN-20260713-002] correction

**Logged**: 2026-07-13T19:50:00+08:00
**Priority**: high
**Status**: resolved
**Area**: requirements

### Summary
20,000字符仅作为变量长度兜底配置，不需要设计超过20,000字符的业务测试场景。

### Details
- 超过10,000字符后变量已经进入外置存储流程。
- 测试重点是10,000字符外置边界、外置后的传递与消费、页面分块展示。
- 20,000字符只验证兜底配置不影响外置逻辑。
- 不生成20,001字符及以上测试点。

### Source
- User correction

### Tags
requirements, long-text, boundary, correction

## [LRN-20260723-UIA-001] correction

**Logged**: 2026-07-23T00:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: ui-automation-architecture

### Summary
UI 自动化不是每个业务项目一套 pytest-Playwright 工程，而是整个平台共用一套自动化环境；业务项目和用例只是共享工程中的命名空间资产。

### Details
- 共享根目录为 `apps/backend/data/ui_automation/pytest_playwright/`。
- POM、测试代码和数据分别按 `project_key` 放入 `pages/generated/`、`testcases/generated/` 和 `data/projects/`。
- 平台只初始化一次公共 fixture、配置和工具。
- 修改共享工程和执行全量 collection 时使用共享工作区锁。

### Source
- User correction

### Tags
ui-automation, pytest-playwright, shared-suite, correction
## [LRN-20260723-001] correction

**Logged**: 2026-07-23T00:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: frontend

### Summary
When asked to migrate an existing list style, matching only the toolbar and table border is insufficient; the source list's selection model and aggregate-list structure must also be preserved.

### Details
- The first UI automation migration retained page-level project and environment filters.
- The reference API automation list has no such filter block and uses header/row checkboxes backed by `useLocalTableSelection`.
- Execution-specific environment selection belongs in the execution action flow, not in the aggregate list header.

### Pattern-Key
frontend-list-style-migration-includes-interaction-model

---
