# 00-15 AI测试系统 - 系统设置 PRD

## 1. 这份文档解决什么问题

系统设置用于配置第一版运行所需的基础能力，包括本地文件存储、本地 Runner、Playwright、Allure、SQLite 和 Agent 安全策略。

核心规则：

- 第一版部署形态以本地开发/单机使用为主。
- 数据库使用 SQLite。
- 上传文件、Markdown、知识库、自动化代码、Allure 报告保存在本地文件系统。
- UI 自动化第一版本地运行，不接 CI、不接 Git 仓库。

---

## 2. 业务边界

### 2.1 本模块负责

- 配置本地文件根目录。
- 配置 SQLite 数据库路径。
- 配置本地 Runner 工作目录。
- 配置 Playwright 运行参数。
- 配置 Allure 结果和报告目录。
- 配置 Agent 安全策略。

### 2.2 本模块不负责

- 不负责模型 Provider，模型配置见模型配置 PRD。
- 不负责用户账号，用户与权限见权限管理 PRD。
- 不负责外部 CI/CD。
- 不负责 Git 仓库连接，第一版不做。

---

## 3. 配置项

### 3.1 文件存储

| 配置 | 说明 |
| --- | --- |
| 文件根目录 | 保存上传文件、转换产物、知识库、自动化代码、报告 |
| 上传文件目录 | 原始需求文档、附件 |
| Markdown 目录 | 转换后的需求文档和探索文档 |
| 知识库目录 | llm-wiki 产物 |
| 自动化代码目录 | pytest + Playwright 代码 |
| 报告目录 | Allure results 和 Allure report |

### 3.2 SQLite

| 配置 | 说明 |
| --- | --- |
| 数据库路径 | SQLite 文件路径 |
| 备份目录 | 手动或定期备份位置 |
| 连接超时 | SQLite busy timeout |
| WAL 模式 | 建议开启 |

### 3.3 本地 Runner

| 配置 | 说明 |
| --- | --- |
| 工作目录 | 自动化执行工作区 |
| Python 路径 | pytest 执行环境 |
| pytest 参数 | 默认执行参数 |
| 并发数 | 第一版建议 1 |
| 超时时间 | 单次运行最大时长 |

### 3.4 Playwright

| 配置 | 说明 |
| --- | --- |
| 浏览器 | chromium、firefox、webkit，第一版默认 chromium |
| 有头模式 | 用于调试和验证码场景 |
| 默认超时 | 页面和 locator 等待 |
| trace | on、retain-on-failure |
| video | off、retain-on-failure |
| screenshot | only-on-failure |

### 3.5 Allure

| 配置 | 说明 |
| --- | --- |
| Allure 命令路径 | 本地 Allure CLI |
| results 目录 | pytest 输出 |
| report 目录 | Allure 生成报告 |
| 历史保留数量 | 本地报告保留策略 |

### 3.6 Agent 安全策略

| 配置 | 说明 |
| --- | --- |
| 允许读目录 | Agent 可读取的目录 |
| 允许写目录 | Agent 可写入的目录 |
| 禁止路径 | 不能探索或写入的路径 |
| 高风险动作确认 | 自愈补丁、删除资产、覆盖知识库等必须人工确认 |
| 敏感信息脱敏 | 密码、token、验证码日志脱敏 |

---

## 4. 页面设计

### 4.1 文件存储设置

展示当前目录、可用性检查、写入测试结果。

### 4.2 本地 Runner 设置

展示 Python、pytest、Playwright、Allure 检查结果。

### 4.3 Playwright 设置

配置浏览器、trace、video、screenshot、有头模式。

### 4.4 Allure 设置

配置 Allure CLI 和报告目录，并提供生成测试报告的连通性检查。

### 4.5 Agent 安全策略

配置允许目录、禁止目录和高风险动作确认策略。

---

## 5. 权限规则

| 操作 | 管理员 | 测试工程师 | 访客 |
| --- | --- | --- | --- |
| 查看系统设置 | 是 | 否 | 是 |
| 修改系统设置 | 是 | 否 | 否 |
| 执行连通性检查 | 是 | 否 | 否 |

---

## 6. 验收标准

- 管理员能配置文件存储根目录。
- 管理员能配置本地 Runner、Playwright、Allure。
- 系统能检查 Python、pytest、Playwright、Allure 是否可用。
- SQLite 路径和文件目录能被系统读取。
- 访客可查看但不能修改配置。
- 测试工程师不能修改系统级配置。
