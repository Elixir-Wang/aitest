# 字母 AI 验证码通用登录计划复用设计

## 背景

当前字母 AI 自动登录链路已经拆成两层：

- `apps/backend/runners/playwright/ai-letter-login.mjs` 负责打开网页、采集登录页元素、截图验证码、填表、勾选协议、点击登录和保存 `storage-state.json`。
- `apps/backend/app/services/auto_auth_service.py` 负责启动 runner，读取 runner 的 JSON Lines 事件，调用 `login_form_analyzer_service` 规划登录表单，再调用 `captcha_solver_service` 识别验证码。

这条链路能跑通一次性自动登录，但每次都重新分析登录页 DOM。目标是把第一次成功登录得到的 Playwright 登录计划保存下来，让后续登录只需要打开网页、按已验证 selector 取验证码图、发给大模型识别、填验证码并登录。

## 目标

1. 首次登录仍走“发现模式”：打开网页、获取 DOM 元素和页面截图、让模型规划登录控件。
2. 首次登录成功后保存结构化登录计划，作为该环境的 Playwright 登录脚本。
3. 后续自动登录优先走“快速复用模式”：读取已保存计划，不再重新分析 DOM。
4. 如果复用计划失效，自动降级回发现模式，成功后覆盖保存新计划。
5. 验证码识别仍由后端调用大模型，使用非深度思考模型配置，runner 不直接调用模型。
6. 协议候选存在时，登录前自动勾选，再点击登录。
7. 成功后保存登录态到既有 `storage-state.json`。

## 非目标

- 不支持滑块、点选、短信、MFA 或动态口令验证码。
- 不把账号密码、验证码答案写入日志、操作记录或长期产物。
- 不把 runner 改成多次 shell 调用的 `playwright-cli open/fill/click` 命令串；保留现有 Node Playwright runner。
- 不在探索任务执行中临时登录；探索任务只复用已有有效登录态。

## 登录计划文件

每个环境在登录态目录下新增：

```text
auth/login-plan.json
```

建议结构：

```json
{
  "version": 1,
  "strategy": "planned",
  "site_url": "https://example.test/login",
  "username_selector": "[data-ai-testing-login-el=\"login-el-1\"]",
  "password_selector": "[data-ai-testing-login-el=\"login-el-2\"]",
  "captcha_image_selector": "[data-ai-testing-login-el=\"login-el-3\"]",
  "captcha_input_selector": "[data-ai-testing-login-el=\"login-el-4\"]",
  "agreement_selector": "[data-ai-testing-login-el=\"login-el-5\"]",
  "login_button_selector": "[data-ai-testing-login-el=\"login-el-6\"]",
  "has_agreement_checkbox": true,
  "created_from": "successful_login",
  "created_at": "2026-06-16T00:00:00Z",
  "dom_fingerprint": {
    "host": "example.test",
    "title": "登录",
    "element_count": 32
  }
}
```

计划文件只保存 selector 和页面指纹，不保存用户名、密码、验证码答案、cookie 或 token。

## 两阶段流程

### 发现模式

触发条件：

- 环境没有 `auth/login-plan.json`。
- 复用模式找不到关键 selector。
- 复用模式点击登录后无法确认成功。

流程：

1. runner 打开 `site_url`，自动填用户名和密码。
2. runner 关闭阻塞弹窗，等待验证码区域出现。
3. runner 采集可见 DOM 元素列表，写入 `login-elements.json`，并保存登录页截图。
4. runner 输出 `login_page_observed` 事件。
5. `auto_auth_service` 调用 `login_form_analyzer_service.analyze_login_form(...)`。
6. analyzer 返回包含用户名、密码、验证码、协议、登录按钮 selector 的计划。
7. runner 按计划执行验证码截图、填验证码、勾协议、登录。
8. 登录成功后 runner 保存 `storage-state.json`，并将实际成功计划写入 `login-plan.json`。

### 快速复用模式

触发条件：

- `auth/login-plan.json` 存在，且 `strategy=planned`。

流程：

1. runner 启动时读取 `login-plan.json`。
2. 打开网页后先按计划 selector 填用户名和密码。
3. 直接定位 `captcha_image_selector`，截图验证码。
4. `auto_auth_service` 把截图发给 `captcha_solver_service.solve_letter_captcha(...)`。
5. runner 填入 `captcha_input_selector`，勾选 `agreement_selector`，点击 `login_button_selector`。
6. 成功后覆盖保存 `storage-state.json`，并刷新 `login-plan.json` 的 `created_at` 与页面指纹。
7. 如果任一关键 selector 不可见，runner 输出 `plan_invalid`，后端切换到发现模式重试一次。

## Runner 协议扩展

启动参数从：

```text
node ai-letter-login.mjs <siteUrl> <storageStatePath> [channel]
```

扩展为：

```text
node ai-letter-login.mjs <siteUrl> <storageStatePath> [channel] [loginPlanPath]
```

也可以通过环境变量传入：

```text
AI_TESTING_LOGIN_PLAN_PATH=/abs/path/login-plan.json
```

新增 stdout 事件：

```json
{ "kind": "login_plan_loaded", "path": "/abs/path/login-plan.json" }
{ "kind": "login_plan_invalid", "reason": "captcha_image_selector_not_visible" }
{ "kind": "login_plan_saved", "path": "/abs/path/login-plan.json" }
```

保留现有事件：

```json
{ "kind": "login_page_observed", "page_image_path": "...", "elements_path": "...", "element_count": 12 }
{ "kind": "captcha_challenge", "attempt": 1, "image_path": "..." }
{ "kind": "login_succeeded", "attempt": 1, "reasons": ["stored_auth_off_login_page"] }
{ "kind": "login_failed", "reason": "captcha_exhausted" }
```

stdin 继续使用：

```json
{ "type": "login_form_plan", "strategy": "planned", "...": "..." }
{ "type": "captcha_answer", "attempt": 1, "value": "ABCD" }
{ "type": "abort" }
```

## 模型职责

### 登录页规划模型

`login_form_analyzer_service` 需要扩展输出字段：

- `username_element_id`
- `password_element_id`
- `captcha_image_element_id`
- `captcha_input_element_id`
- `agreement_element_id`
- `login_button_element_id`

所有 ID 必须来自 runner 提供的 `elements` 列表。服务端再映射成 selector。若关键字段缺失，返回 `strategy=heuristic`。

### 验证码识别模型

`captcha_solver_service` 继续只接收验证码截图，返回 3-6 位验证码字符。模型调用要求：

- 只输出验证码字符。
- 不输出解释、推理过程、标点或空格。
- 仍走非深度思考模型配置。
- 后端日志不记录验证码答案。

## 协议勾选策略

协议候选以计划 selector 优先：

1. `agreement_selector` 可见时，优先点击或 check。
2. 若计划无协议 selector，使用现有启发式 `ensureUserAgreementChecked(page)`。
3. 禁止把“用户协议”“隐私政策”纯链接当作勾选目标。
4. 登录按钮点击前必须先尝试协议勾选。

## 失败与降级

| 场景 | 行为 |
|------|------|
| `login-plan.json` 缺失 | 发现模式 |
| 计划 JSON 解析失败 | 记录 `login_plan_invalid`，发现模式 |
| 用户名/密码 selector 不可用 | 发现模式 |
| 验证码图片 selector 不可见 | 发现模式 |
| 验证码输入框 selector 不可编辑 | 发现模式 |
| 登录按钮 selector 不可见 | 发现模式 |
| 发现模式也失败 | 按既有 `login_failed` 失败状态处理 |
| 验证码识别失败 | 后端写 `CAPTCHA_SOLVE_FAILED`，runner abort |
| 验证码被拒绝 | 刷新验证码，最多 3 次 |

复用模式最多降级一次，避免在同一次后台任务里反复分析。

## 文件改动范围

| 文件 | 改动 |
|------|------|
| `apps/backend/runners/playwright/ai-letter-login.mjs` | 读取/保存 login plan，增加复用模式、失效事件和计划成功持久化 |
| `apps/backend/runners/playwright/ai-letter-login.test.mjs` | 覆盖计划加载、计划失效降级、成功保存计划、协议勾选 |
| `apps/backend/app/services/auto_auth_service.py` | 计算 `login-plan.json` 路径，处理新增 runner 事件，复用失败后允许发现模式 |
| `apps/backend/app/services/login_form_analyzer_service.py` | 扩展用户名/密码 selector 规划字段 |
| `apps/backend/tests/test_auto_auth_service.py` | 覆盖首次保存计划、后续传入计划路径、计划失效降级 |
| `apps/backend/tests/test_login_form_analyzer_service.py` | 覆盖新增用户名/密码字段映射和缺失降级 |

## 验证计划

后端：

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_auto_auth_service.py tests/test_login_form_analyzer_service.py tests/test_captcha_solver_service.py -q
```

Runner：

```powershell
cd apps/backend/runners/playwright
npm test -- ai-letter-login.test.mjs
```

手工验收：

1. 新建账号密码 + 字母 AI 校验 + 复用登录态环境。
2. 首次自动登录成功后检查 `auth/storage-state.json` 和 `auth/login-plan.json` 都存在。
3. 删除 `storage-state.json`，保留 `login-plan.json`，重新触发自动登录。
4. 确认第二次不再重新分析登录页 DOM，只输出验证码挑战并保存登录态。
5. 手动破坏 `login-plan.json` 的验证码 selector，确认任务降级到发现模式并重新保存计划。

## 决策

- 保存结构化计划，不保存生成的 JS 脚本文件。这样 runner 仍是唯一执行器，站点差异只体现在数据计划里，后续升级执行逻辑不需要批量改脚本。
- 后端继续负责模型调用。runner 不持有模型配置，也不会把验证码图直接发给模型。
- 成功登录后保存计划。失败计划不落盘，避免把错误 selector 固化。
