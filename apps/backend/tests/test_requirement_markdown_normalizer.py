from __future__ import annotations

import unittest

from app.services.requirement_markdown_normalizer import normalize_requirement_markdown


class RequirementMarkdownNormalizerTest(unittest.TestCase):
    def test_unwraps_business_flow_code_fence_to_mermaid(self):
        markdown = """## 五、核心链路

```
用户访问新版官网 ↓用户完成官网登录（手机号/邮箱） ↓官网跳转至产品 sso_entry_url，携带 login_ticket + state
```
"""

        normalized = normalize_requirement_markdown(markdown)

        self.assertIn("```mermaid", normalized)
        self.assertIn("flowchart TD", normalized)
        self.assertIn('S1["用户访问新版官网"]', normalized)
        self.assertIn('S2["用户完成官网登录（手机号/邮箱）"]', normalized)
        self.assertIn('S3["官网跳转至产品 sso_entry_url，携带 login_ticket + state"]', normalized)
        self.assertIn("S1 --> S2", normalized)

    def test_keeps_real_code_fence(self):
        markdown = """```python
def login():
    return True
```
"""

        self.assertEqual(normalize_requirement_markdown(markdown), markdown)

    def test_converts_plain_business_flow_line_to_mermaid(self):
        markdown = "用户访问官网 → 用户登录 → 产品后端调用认证中心\n"

        normalized = normalize_requirement_markdown(markdown)

        self.assertIn("```mermaid", normalized)
        self.assertIn('S1["用户访问官网"]', normalized)
        self.assertIn('S2["用户登录"]', normalized)
        self.assertIn('S3["产品后端调用认证中心"]', normalized)

    def test_mermaid_labels_replace_inner_double_quotes(self):
        markdown = '用户访问官网 → context/register 预注册 {invite_code: "BG_INV_XXX"} → 产品后端校验邀请码\n'

        normalized = normalize_requirement_markdown(markdown)

        self.assertIn('S2["context/register 预注册 {invite_code: \'BG_INV_XXX\'}"]', normalized)
        self.assertNotIn('\\"BG_INV_XXX\\"', normalized)

    def test_keeps_business_logic_rules_as_markdown(self):
        markdown = """### 业务逻辑

校验 session_token，获取 unified_uid

查询产品配置（不存在 → PRODUCT_INVALID，禁用 → PRODUCT_DISABLED）

如果 require_invite_code = false：action = CREATE_TICKET_DIRECTLY

如果 require_invite_code = true：

查询 auth_product_user_access 是否存在 CONNECTED 记录

存在 → action = CREATE_TICKET_DIRECTLY

不存在 → action = SHOW_INVITE_DIALOG
"""

        normalized = normalize_requirement_markdown(markdown)

        self.assertNotIn("```mermaid", normalized)
        self.assertIn("不存在 → action = SHOW_INVITE_DIALOG", normalized)

    def test_does_not_convert_markdown_sections_with_flow_lines_to_mermaid(self):
        markdown = """## 3 建设原则
### 3.1 统一认证，产品自治
统一登录认证授权中心负责统一身份识别与认证授权。
## 5 总体架构
官网统一入口 → 统一登录认证授权中心 → 百系产品 → 本地账号映射
## 6 核心机制设计
映射关系：Unified UID ↔ Local User ID
"""

        normalized = normalize_requirement_markdown(markdown)

        self.assertNotIn("```mermaid", normalized)
        self.assertIn("### 3.1 统一认证，产品自治", normalized)
        self.assertIn("官网统一入口 → 统一登录认证授权中心 → 百系产品 → 本地账号映射", normalized)
        self.assertIn("映射关系：Unified UID ↔ Local User ID", normalized)


if __name__ == "__main__":
    unittest.main()
