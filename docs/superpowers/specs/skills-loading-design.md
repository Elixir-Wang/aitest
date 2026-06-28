# Page Exploration Agent - Skills 加载设计

## 1. 概述

根据 LangChain DeepAgents 的 Skills 机制，设计页面探索 Agent 的 skills 加载方案。

---

## 2. 核心概念

### 2.1 什么是 Skill？

Skill 是一组领域知识和最佳实践的封装，以 Markdown 格式定义，在运行时注入到 Agent 的 system prompt 中。

**特点**:
- ✅ 声明式定义（Markdown）
- ✅ 按需加载（只加载需要的 skills）
- ✅ 动态注入（运行时组合到 system prompt）
- ✅ 可复用（跨不同 agents 复用）

---

### 2.2 Skill vs Tool

| 维度 | Skill | Tool |
|------|-------|------|
| **本质** | 知识和指令 | 可执行函数 |
| **格式** | Markdown 文档 | Python 函数 |
| **加载方式** | 注入到 system prompt | 注册为工具 |
| **使用时机** | 整个对话生命周期 | Agent 主动调用 |
| **示例** | 定位器最佳实践 | playwright_cli 工具 |

---

## 3. Skills 目录结构

```
apps/backend/app/agents/page_exploration/
├── skills/                              # Skills 根目录
│   ├── __init__.py                      # Skills 加载器
│   ├── locator_best_practices/          # Skill 1: 定位器最佳实践
│   │   └── SKILL.md                     # Skill 定义
│   └── page_explorer/                   # Skill 2: 页面探索策略
│       └── SKILL.md                     # Skill 定义
├── prompts/                             # Prompts 目录
│   ├── __init__.py
│   ├── system_prompt.py                 # 基础 system prompt
│   └── exploration_prompt.py            # 探索任务 prompt
├── agent.py                             # Agent 初始化（使用 SkillsMiddleware）
├── tools.py                             # Tools 定义
└── service.py                           # Service 层
```

---

## 4. Skills 加载机制设计

### 4.1 SkillsLoader（技能加载器）

**职责**: 从文件系统加载和解析 Skill 定义

```python
# apps/backend/app/agents/page_exploration/skills/__init__.py

from pathlib import Path
from typing import List, Dict

class Skill:
    """Skill 数据模型"""
    def __init__(self, name: str, content: str, path: Path):
        self.name = name           # skill 名称，如 "locator_best_practices"
        self.content = content     # SKILL.md 的完整内容
        self.path = path           # 文件路径

    def __repr__(self):
        return f"Skill(name={self.name}, path={self.path})"


class SkillsLoader:
    """Skills 加载器"""
    
    def __init__(self, skills_dir: Path = None):
        if skills_dir is None:
            # 默认指向当前模块的 skills 目录
            skills_dir = Path(__file__).parent
        self.skills_dir = skills_dir
    
    def load_skill(self, skill_name: str) -> Skill:
        """加载单个 skill"""
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill not found: {skill_path}")
        
        content = skill_path.read_text(encoding="utf-8")
        return Skill(name=skill_name, content=content, path=skill_path)
    
    def load_skills(self, skill_names: List[str]) -> List[Skill]:
        """批量加载多个 skills"""
        return [self.load_skill(name) for name in skill_names]
    
    def list_available_skills(self) -> List[str]:
        """列出所有可用的 skills"""
        skills = []
        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skills.append(item.name)
        return sorted(skills)


# 全局加载器实例
_loader = SkillsLoader()

def load_skill(skill_name: str) -> Skill:
    """便捷函数：加载单个 skill"""
    return _loader.load_skill(skill_name)

def load_skills(skill_names: List[str]) -> List[Skill]:
    """便捷函数：批量加载 skills"""
    return _loader.load_skills(skill_names)

def list_available_skills() -> List[str]:
    """便捷函数：列出可用 skills"""
    return _loader.list_available_skills()
```

---

### 4.2 SkillsMiddleware（技能中间件）

**职责**: 将加载的 Skills 注入到 Agent 的 system prompt 中

```python
# apps/backend/app/agents/page_exploration/skills/__init__.py

from typing import List

class SkillsMiddleware:
    """Skills 中间件 - 将 skills 注入到 system prompt"""
    
    def __init__(self, skills: List[Skill]):
        self.skills = skills
    
    def build_skills_section(self) -> str:
        """构建 skills 部分的 prompt"""
        if not self.skills:
            return ""
        
        sections = []
        sections.append("## Available Skills\n")
        sections.append("You have access to the following specialized knowledge:\n")
        
        for skill in self.skills:
            sections.append(f"\n### Skill: {skill.name}\n")
            sections.append(skill.content)
            sections.append("\n---\n")
        
        return "\n".join(sections)
    
    def inject_into_prompt(self, base_prompt: str) -> str:
        """将 skills 注入到基础 prompt 中"""
        skills_section = self.build_skills_section()
        
        if not skills_section:
            return base_prompt
        
        # 在 base_prompt 后面追加 skills section
        return f"{base_prompt}\n\n{skills_section}"


def create_skills_middleware(skill_names: List[str]) -> SkillsMiddleware:
    """便捷函数：创建 skills 中间件"""
    skills = load_skills(skill_names)
    return SkillsMiddleware(skills)
```

---

## 5. Agent 集成

### 5.1 Agent 初始化（with Skills）

```python
# apps/backend/app/agents/page_exploration/agent.py

from langchain.agents import create_agent
from app.agents.page_exploration.skills import create_skills_middleware
from app.agents.page_exploration.prompts.system_prompt import BASE_SYSTEM_PROMPT
from app.agents.page_exploration.tools import get_exploration_tools


def create_page_exploration_agent(
    model,
    *,
    skill_names: List[str] = None,
    tools: List = None,
):
    """
    创建页面探索 Agent
    
    Args:
        model: LangChain 模型实例
        skill_names: 要加载的 skills 列表，默认加载所有
        tools: 工具列表，默认使用标准探索工具
    
    Returns:
        LangChain Agent 实例
    """
    # 1. 确定要加载的 skills
    if skill_names is None:
        # 默认加载所有核心 skills
        skill_names = [
            "locator_best_practices",  # 定位器最佳实践
            "page_explorer",           # 页面探索策略
        ]
    
    # 2. 创建 skills 中间件
    skills_middleware = create_skills_middleware(skill_names)
    
    # 3. 注入 skills 到 system prompt
    system_prompt = skills_middleware.inject_into_prompt(BASE_SYSTEM_PROMPT)
    
    # 4. 获取工具
    if tools is None:
        tools = get_exploration_tools()
    
    # 5. 创建 agent
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )
```

---

### 5.2 Base System Prompt

```python
# apps/backend/app/agents/page_exploration/prompts/system_prompt.py

BASE_SYSTEM_PROMPT = """
你是一个专业的网页探索智能体。

## 核心任务

1. **智能探索网站**: 发现所有重要页面和交互元素
2. **生成稳定定位器**: 为每个元素生成最佳的 Playwright 定位器
3. **生成页面产物**: 输出 YAML 格式的页面描述文件

## 工作流程

1. 访问目标页面
2. 获取页面快照（playwright-cli snap）
3. 识别页面类型（Dashboard/List/Detail/Form）
4. 为关键元素选择最佳定位器
5. 提取页面链接
6. 生成页面产物（YAML）
7. 继续探索下一个页面

## 输出格式

每个探索的页面生成一个 YAML 文件：

```yaml
page:
  id: "page-001"
  title: "智能体工作台"
  normalized_path: "/workspace/agents"
  explored_at: "2026-06-27T10:00:00Z"
  
  elements:
    - id: "create_agent_btn"
      name: "创建智能体"
      role: "button"
      locators:
        - kind: "role"
          code: "getByRole('button', { name: '创建智能体' })"
          priority: 1
```

## 注意事项

- ✅ 使用语义定位器（getByRole > getByLabel > getByTestId）
- ✅ 避免危险操作（删除、支付、登出）
- ✅ 控制探索深度（默认 3 层）
- ❌ 不要使用 ref 定位器（ref=e15 等临时引用）
- ❌ 不要填写和提交表单（除非是搜索）
- ❌ 不要点击分页和"加载更多"

你将拥有以下专业技能的支持。请在探索过程中遵循这些最佳实践。
""".strip()
```

---

## 6. 使用示例

### 6.1 加载所有 Skills

```python
from app.agents.page_exploration.agent import create_page_exploration_agent
from langchain_openai import ChatOpenAI

# 创建模型
model = ChatOpenAI(model="gpt-4")

# 创建 agent（默认加载所有 skills）
agent = create_page_exploration_agent(model)

# 使用 agent
result = agent.invoke({
    "messages": [
        {"role": "user", "content": "探索 https://example.com/workspace"}
    ]
})
```

---

### 6.2 加载特定 Skills

```python
# 只加载定位器最佳实践
agent = create_page_exploration_agent(
    model,
    skill_names=["locator_best_practices"]
)

# 自定义 skills 组合
agent = create_page_exploration_agent(
    model,
    skill_names=[
        "locator_best_practices",
        "page_explorer",
        # 可以添加更多 skills
    ]
)
```

---

### 6.3 列出可用 Skills

```python
from app.agents.page_exploration.skills import list_available_skills

# 列出所有可用的 skills
skills = list_available_skills()
print(skills)
# Output: ['locator_best_practices', 'page_explorer']
```

---

## 7. Skills 的优势

### 7.1 vs 硬编码在 System Prompt

| 方式 | 硬编码 | Skills 机制 |
|------|--------|------------|
| **可维护性** | ❌ 修改需要改代码 | ✅ 只需修改 Markdown |
| **可复用性** | ❌ 难以跨 agent 复用 | ✅ 任意 agent 可加载 |
| **可扩展性** | ❌ 添加知识需改代码 | ✅ 添加目录即可 |
| **按需加载** | ❌ 所有知识都加载 | ✅ 只加载需要的 |
| **版本管理** | ❌ 混在代码中 | ✅ 独立的 Markdown 文件 |

---

### 7.2 vs Tools

| 维度 | Skills | Tools |
|------|--------|-------|
| **性能开销** | ✅ 零开销（只是文本） | ⚠️ 需要 LLM 调用 |
| **适用场景** | 知识、原则、指南 | 外部操作、数据获取 |
| **Token 消耗** | 一次性（system prompt） | 每次调用都消耗 |
| **响应速度** | ✅ 立即可用 | ⚠️ 需要工具调用往返 |

**结论**: Skills 适合"告诉 Agent 怎么做"，Tools 适合"让 Agent 做什么"

---

## 8. 最佳实践

### 8.1 Skill 设计原则

1. ✅ **单一职责**: 每个 skill 聚焦一个领域
2. ✅ **自包含**: skill 内容完整，不依赖外部
3. ✅ **结构化**: 使用清晰的标题和列表
4. ✅ **示例丰富**: 提供正反示例
5. ✅ **简洁明了**: 避免冗长的描述

---

### 8.2 何时创建新 Skill？

**应该创建新 skill**:
- ✅ 有明确的领域知识（如"表单验证规则"）
- ✅ 知识会被多次复用
- ✅ 知识会频繁更新
- ✅ 知识独立于特定任务

**不应该创建 skill**:
- ❌ 任务特定的指令（放在 task prompt 中）
- ❌ 一次性的说明
- ❌ 与其他 skill 重复的内容

---

### 8.3 Skill 命名规范

- 使用 `snake_case`
- 描述性强
- 避免缩写

**好的命名**:
- `locator_best_practices`
- `page_explorer`
- `form_validation_rules`

**不好的命名**:
- `skill1`
- `locators`
- `misc`

---

## 9. 扩展方向

### 9.1 动态 Skill 加载

根据任务类型动态选择 skills：

```python
def get_skills_for_task(task_type: str) -> List[str]:
    """根据任务类型返回推荐的 skills"""
    skill_map = {
        "navigation": ["page_explorer"],
        "form": ["locator_best_practices", "form_validation_rules"],
        "full": ["locator_best_practices", "page_explorer"],
    }
    return skill_map.get(task_type, [])

# 使用
agent = create_page_exploration_agent(
    model,
    skill_names=get_skills_for_task("form")
)
```

---

### 9.2 Skill 版本管理

支持同一 skill 的多个版本：

```
skills/
├── locator_best_practices/
│   ├── SKILL.md              # 当前版本
│   └── v1/
│       └── SKILL.md          # 历史版本
```

---

### 9.3 Skill 依赖管理

某些 skills 可能依赖其他 skills：

```yaml
# skills/form_validation_rules/metadata.yaml
name: form_validation_rules
description: 表单验证规则
depends_on:
  - locator_best_practices
```

---

## 10. 对比：有无 Skills 机制

### 10.1 无 Skills 机制

```python
# ❌ 所有知识硬编码在 system prompt
SYSTEM_PROMPT = """
你是网页探索智能体。

优先使用 getByRole...
不要使用 ref...
避免点击删除按钮...
表单不要提交...
分页不要点击...
... (3000+ 行)
"""

agent = create_agent(model, tools, system_prompt=SYSTEM_PROMPT)
```

**问题**:
- ❌ system_prompt 文件巨大（3000+ 行）
- ❌ 难以维护
- ❌ 无法按需加载
- ❌ 难以复用

---

### 10.2 有 Skills 机制

```python
# ✅ 知识模块化
agent = create_page_exploration_agent(
    model,
    skill_names=["locator_best_practices", "page_explorer"]
)
```

**优势**:
- ✅ system_prompt 简洁（100 行）
- ✅ 知识模块化（每个 skill 400 行）
- ✅ 按需加载（只加载需要的）
- ✅ 易于维护和复用

---

## 11. 实施步骤

### Step 1: 创建 SkillsLoader

```bash
# 创建 skills/__init__.py
touch apps/backend/app/agents/page_exploration/skills/__init__.py
```

实现 `SkillsLoader` 和 `SkillsMiddleware`（参考 4.1 和 4.2）

---

### Step 2: 提取 Base System Prompt

```bash
# 创建 prompts/system_prompt.py
touch apps/backend/app/agents/page_exploration/prompts/system_prompt.py
```

定义简洁的 `BASE_SYSTEM_PROMPT`（参考 5.2）

---

### Step 3: 创建 Agent 初始化函数

```bash
# 创建 agent.py
touch apps/backend/app/agents/page_exploration/agent.py
```

实现 `create_page_exploration_agent`（参考 5.1）

---

### Step 4: 测试

```python
# 测试加载机制
from app.agents.page_exploration.skills import list_available_skills

skills = list_available_skills()
print(f"Available skills: {skills}")

# 测试 agent 创建
from app.agents.page_exploration.agent import create_page_exploration_agent

agent = create_page_exploration_agent(model)
print(f"Agent created with skills")
```

---

## 12. 总结

### 核心价值

1. **解耦**: 知识（Skills）与逻辑（Agent）分离
2. **复用**: Skills 可跨 agents 复用
3. **维护**: Markdown 格式，易于编辑
4. **扩展**: 添加新 skill 无需改代码

### 关键组件

1. **SkillsLoader**: 从文件系统加载 skills
2. **SkillsMiddleware**: 将 skills 注入到 system prompt
3. **Agent Factory**: 组装 agent 时集成 skills

### 适用场景

- ✅ 领域知识丰富的 Agent
- ✅ 需要频繁更新知识的场景
- ✅ 多个 agents 共享知识的场景
- ✅ 需要按需加载知识的场景

---

**下一步**: 实施 SkillsLoader 和 SkillsMiddleware，并集成到页面探索 Agent 中。
