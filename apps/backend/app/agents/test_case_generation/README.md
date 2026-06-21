# 测试用例生成 Agent 设计文档

## 概述

测试用例生成 Agent 用于根据最终需求文档生成完整、系统、可执行的测试用例集。

## 目录结构

```
apps/backend/app/agents/test_case_generation/
├── __init__.py                 # 模块导出
├── agent.py                    # Agent 定义
├── middleware.py               # Skill 中间件
├── schemas.py                  # 数据结构定义
├── service.py                  # 服务层
└── skills/
    └── test-case-generation/
        ├── SKILL.md            # Skill 定义
        └── references/         # 参考文档（可选）
```

## 数据结构

### 输入（TestCaseGenerationInput）

```python
{
    "requirement_name": "用户管理系统",
    "requirement_content": "# 需求理解\n\n## 1. 需求背景\n...",
    "generation_scope": "只生成登录模块和用户管理模块",  # 可选
    "include_company_knowledge": false  # 是否包含公司知识库
}
```

### 输出（TestCaseGenerationResult）

```python
{
    "summary": "本测试用例集覆盖了用户管理系统的核心功能...",
    "total_count": 25,
    "modules": [
        {
            "module_name": "登录模块",
            "test_cases": [
                {
                    "id": "tc-001",
                    "module": "登录模块",
                    "title": "使用正确的用户名和密码登录",
                    "priority": "P0",
                    "type": "功能测试",
                    "precondition": "用户已注册且状态为启用",
                    "steps": [
                        "打开登录页面",
                        "在用户名输入框输入 'test@example.com'",
                        "在密码输入框输入正确的密码",
                        "点击'登录'按钮"
                    ],
                    "expected_result": "登录成功，页面跳转到首页",
                    "test_data": "用户名: test@example.com",
                    "notes": ""
                }
            ]
        }
    ]
}
```

## API 接口

### POST /api/v1/projects/{project_id}/test-case-sets/generate

生成测试用例集。

**请求体**：

```json
{
    "requirement_doc_id": "req-abc123",
    "generation_scope": "只生成登录模块和订单模块的测试用例",
    "include_company_knowledge": false
}
```

**响应**：

```json
{
    "summary": "本测试用例集覆盖了...",
    "total_count": 25,
    "modules": [...],
    "markdown": "# 测试用例集\n\n..."
}
```

## 前端组件

### TestCaseGenerationForm

测试用例生成表单组件。

**属性**：
- `projectId`: 项目 ID
- `requirementDocId`: 需求文档 ID
- `requirementDocTitle`: 需求文档标题
- `onSuccess`: 生成成功回调
- `onCancel`: 取消回调

### TestCaseGenerationResult

测试用例展示组件。

**属性**：
- `summary`: 测试用例集概述
- `totalCount`: 测试用例总数
- `modules`: 按模块组织的测试用例
- `markdown`: Markdown 格式（可下载）

## 使用示例

### 后端调用

```python
from app.agents.test_case_generation import generate_test_cases
from app.agents.test_case_generation.schemas import TestCaseGenerationInput

# 构建输入
input_data = TestCaseGenerationInput(
    requirement_name="用户管理系统",
    requirement_content=final_requirement_content,
    generation_scope="",
    include_company_knowledge=False,
)

# 生成测试用例
result = await generate_test_cases(input_data)

print(f"生成了 {result.total_count} 个测试用例")
print(result.to_markdown())
```

### 前端调用

```typescript
import { TestCaseGenerationForm } from "@/components/ai-testing/test-case-generation-form";

<TestCaseGenerationForm
  projectId="proj-123"
  requirementDocId="req-456"
  requirementDocTitle="用户管理系统"
  onSuccess={(result) => {
    console.log(`生成了 ${result.total_count} 个测试用例`);
  }}
/>
```

## 测试用例类型

1. **功能测试** - 验证正常功能
2. **异常测试** - 验证异常处理
3. **边界测试** - 验证边界条件
4. **性能测试** - 验证性能要求
5. **安全测试** - 验证权限和安全
6. **兼容测试** - 验证兼容性

## 优先级定义

- **P0（核心功能）** - 主流程、核心业务
- **P1（重要功能）** - 重要分支、常用功能
- **P2（一般功能）** - 边界情况、辅助功能
- **P3（优化建议）** - 体验优化、性能优化

## 注意事项

1. 需要先完成需求分析，生成最终需求文档
2. Agent 会自动从最终需求文档中提取信息
3. 生成的测试用例可以导出为 Markdown 格式
4. 支持指定生成范围（只生成特定模块）
5. 可以选择是否包含公司测试规范

## 扩展方向

1. 支持导出为其他格式（Excel、TestRail）
2. 支持测试用例的编辑和管理
3. 支持测试执行和结果记录
4. 支持与 CI/CD 集成
5. 支持测试覆盖率分析
