# 接口环境塞伯坦凭据编辑 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许接口环境的塞伯坦 key、token、username 为空保存，并支持回填和按需查看已保存的 key/token。

**Architecture:** 后端继续在现有 `auth_config_json` 中加密存储 key/token，但列表序列化时解密并放入 `auth_config`。更新请求始终按输入值重建塞伯坦凭据，因此空字符串会清除旧值。前端从返回的 `auth_config` 回填表单，并在现有页面内为 key/token 添加独立显示切换。

**Tech Stack:** FastAPI、Pydantic、SQLite repository、pytest、Next.js、React、TypeScript、lucide-react、Biome。

**Implementation Status (2026-07-27):** Completed. 后端凭据明文返回、空值清除、前端回填和独立可见性切换均已实现并通过聚焦测试。

## Global Constraints

- `cybertron-robot-key`、`cybertron-robot-token`、`username` 必须可为空保存。
- `GET /api-environments` 必须返回 key/token 明文；这是已确认的安全边界。
- key/token 空值更新必须清除旧加密凭据；不得隐式保留。
- 账号密码鉴权校验、接口环境权限、运行和报告中的脱敏逻辑不得改变。
- 不新增依赖、数据表或 API 路由。
- 不创建提交，除非用户明确要求。

---

### Task 1: 后端凭据返回与可选保存

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py:365-510,2816-2833`
- Modify: `apps/backend/tests/test_api_automation_environment.py`

**Interfaces:**
- Consumes: `ApiEnvironmentIn.auth_config: dict` 和已加密的 `cybertron_robot_key_encrypted` / `cybertron_robot_token_encrypted`。
- Produces: `ApiEnvironmentOut.auth_config` 中的 `cybertron_robot_key`、`cybertron_robot_token`、`username` 字段。

- [x] **Step 1: 写失败的服务测试。**

```python
created = service.create_api_environment(project_id, cybertron_payload(key="robot-key", token="robot-token", username="tmp"), admin)
assert created["auth_config"]["cybertron_robot_key"] == "robot-key"
assert created["auth_config"]["cybertron_robot_token"] == "robot-token"

updated = service.update_api_environment(project_id, created["id"], cybertron_payload(key="", token="", username=""), admin)
assert updated["auth_config"]["cybertron_robot_key"] == ""
assert updated["auth_config"]["cybertron_robot_token"] == ""
assert updated["auth_config"]["username"] == ""
```

- [x] **Step 2: 运行测试确认当前实现不满足返回或清空要求。**

Run: `rtk pytest apps/backend/tests/test_api_automation_environment.py -q`

Expected: 断言 key/token 不存在、为空或更新后仍被保留时失败。

- [x] **Step 3: 最小化修改服务层。**

```python
# 序列化：解密凭据并暴露为 auth_config 的三个字段。
# 更新：塞伯坦配置始终调用加密准备函数，空值映射为空加密存储字段。
```

将 `_serialize_api_environment` 从单纯掩码改为按已确认方案返回解密后的塞伯坦凭据；调整创建/更新逻辑，使空的 `auth_config` 值不会被旧密文回填。保持非塞伯坦鉴权与已有 saved 标记兼容。

- [x] **Step 4: 运行后端环境测试。**

Run: `rtk pytest apps/backend/tests/test_api_automation_environment.py -q`

Expected: PASS。

### Task 2: 前端可选校验、回填与小眼睛

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx:1-90,733-770,2297-2325,3011-3027`
- Modify: `apps/frontend/tests/api-environment-cybertron-credentials-contract.test.mjs`

**Interfaces:**
- Consumes: `ApiAutomationEnvironment.auth_config` 的 `cybertron_robot_key`、`cybertron_robot_token` 和 `username`。
- Produces: 塞伯坦环境表单允许三字段为空，编辑时可回填，key/token 提供独立的显示切换按钮。

- [x] **Step 1: 写失败的前端契约测试。**

```js
assert.match(source, /cybertronRobotKey:\s*asString\(authConfig\.cybertron_robot_key\)/);
assert.match(source, /cybertronRobotToken:\s*asString\(authConfig\.cybertron_robot_token\)/);
assert.doesNotMatch(source, /塞伯坦智能体必须填写/);
assert.match(source, /Eye|EyeOff/);
```

测试还应断言仅 key/token 启用显示切换，且按钮包含描述显示状态的 `aria-label`。

- [x] **Step 2: 运行契约测试确认当前实现失败。**

Run: `node --test apps/frontend/tests/api-environment-cybertron-credentials-contract.test.mjs`

Expected: FAIL，原因是当前字段不回填、存在必填校验且没有显示切换。

- [x] **Step 3: 最小化修改页面。**

```tsx
const [showCybertronRobotKey, setShowCybertronRobotKey] = useState(false);
// key/token 的 Input type 在 "password" 与 "text" 间切换，按钮切换对应状态。
```

移除塞伯坦三字段的必填分支；将三个表单字段原样放入 `auth_config`；从环境返回值回填；使用已有 `lucide-react` 图标实现独立眼睛按钮，不扩展到账号密码字段。

- [x] **Step 4: 运行前端契约测试和格式检查。**

Run: `node --test apps/frontend/tests/api-environment-cybertron-credentials-contract.test.mjs && npm run check -- --files 'src/app/(main)/projects/[projectId]/automation/api/page.tsx' 'tests/api-environment-cybertron-credentials-contract.test.mjs'`

Expected: PASS。

### Task 3: 集成回归验证

**Files:**
- Modify: 无。

**Interfaces:**
- Consumes: Tasks 1–2 产出的后端响应和前端表单行为。
- Produces: 已验证的实现结果。

- [x] **Step 1: 运行后端完整目标测试。**

Run: `rtk pytest apps/backend/tests/test_api_automation_environment.py -q`

Expected: PASS。

- [x] **Step 2: 运行前端相关契约测试。**

Run: `node --test apps/frontend/tests/api-environment-cybertron-credentials-contract.test.mjs apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs`

Expected: PASS。

- [x] **Step 3: 检查变更范围。**

Run: `rtk git diff --check && rtk git diff -- apps/backend/app/services/api_automation/service.py apps/backend/tests/test_api_automation_environment.py "apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx" apps/frontend/tests/api-environment-cybertron-credentials-contract.test.mjs`

Expected: 无空白错误，且只有计划内改动。

## Verification Result

- 后端目标测试：`9 passed`。
- 本功能前端契约测试：`2 passed`；Biome 和 TypeScript 类型检查通过。
- 既有 `api-automation-interface-set-copy-contract.test.mjs` 为 `29 passed, 2 failed`；失败断言在变更前的 `HEAD` 页面中已不成立，与本功能无关。
- 本地页面可访问，但浏览器没有登录态，停留在登录检查页；未使用未知凭据绕过认证。
