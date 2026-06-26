# 页面探索功能完整设计规范

**项目**: 基于 Playwright CLI + LangChain 的页面探索功能  
**日期**: 2026-06-26  
**状态**: 设计完成，待实施

---

## 目录

1. [概述和背景](#1-概述和背景)
2. [整体架构设计](#2-整体架构设计)
3. [核心组件设计](#3-核心组件设计)
4. [Skills设计](#4-skills设计)
5. [探索流程和终止逻辑](#5-探索流程和终止逻辑)
6. [错误处理策略](#6-错误处理策略)
7. [实施计划](#7-实施计划)
8. [验收标准](#8-验收标准)

---

## 1. 概述和背景

### 1.1 背景

当前项目需要实现基于 Playwright CLI 和 LangChain 的页面元素探索功能，用于：
- 探索项目页面结构和交互元素
- 生成可复用的页面元素定位器快照
- 为后续自动化测试用例生成提供准确的元素定位信息

### 1.2 核心需求

1. 根据探索范围、探索目标、禁止路径进行智能探索
2. 使用语义化定位器（getByRole/getByText/getByLabel/getByTestId），避免不可复用的ref或CSS选择器
3. 探索过程中验证定位器的唯一性和可用性
4. 生成 playwright 探索快照（YAML格式）
5. 支持探索缓存，避免重复探索同一页面
6. 跨环境URL归一化（测试环境和生产环境URL不同但路径相同）

### 1.3 非目标

- 不在本阶段实现测试用例生成
- 不在本阶段实现自动化测试执行
- 不使用 ref 定位器（因为不能复用）

---

## 2. 整体架构设计

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (React)                          │
│  - 创建探索任务（范围、目标、禁止路径）                      │
│  - 实时查看探索进度（SSE）                                   │
│  - 查看探索结果和产物                                        │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/SSE
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Exploration Service (FastAPI)                    │
│  - 任务CRUD                                                 │
│  - 任务调度与生命周期管理                                    │
│  - SSE事件推送                                              │
│  - 缓存索引管理                                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         LangChain Exploration Agent                         │
│  职责：                                                      │
│  - 理解探索目标和范围                                        │
│  - 制定探索计划                                              │
│  - 决策下一步动作（访问哪个链接、点击哪个按钮）              │
│  - 判断是否已探索（缓存检查）                                │
│  - 生成探索报告                                             │
│                                                             │
│  Tools:                                                     │
│  - playwright_cli_snapshot_tool                            │
│  - playwright_cli_navigate_tool                            │
│  - playwright_cli_click_tool                               │
│  - playwright_cli_fill_tool                                │
│  - cache_lookup_tool                                       │
│  - artifact_write_tool                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Playwright CLI Wrapper (Python)                  │
│  - 执行 playwright-cli 命令                                 │
│  - 解析快照输出（YAML）                                     │
│  - 会话管理                                                 │
│  - 登录态保存/恢复                                          │
└────────────────────┬────────────────────────────────────────┘
                     │ subprocess
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              playwright-cli (Node.js)                       │
│  - 浏览器自动化                                             │
│  - 页面快照生成                                             │
│  - 元素定位与交互                                           │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Artifact Service (Python)                        │
│  - 页面产物生成（pages/*.yaml）                            │
│  - 探索图谱生成（graph.yaml）                              │
│  - 探索报告生成（report.md）                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
data/projects/{project_id}/
├── requirements/                    # 需求文档（定义测试场景）
│   └── req-001-agent-management.md
│
├── page_exploration/                # 页面探索产物
│   ├── pages/                       # ✅ 项目级pages（全局复用）
│   │   ├── page-workspace-agents.yaml
│   │   ├── page-workspace-settings.yaml
│   │   └── pages-index.yaml
│   │
│   ├── cache_index.yaml             # 项目级缓存索引
│   │
│   └── runs/                        # 探索运行历史
│       ├── run-001/
│       │   ├── run.yaml             # 运行配置 + 统计摘要
│       │   ├── discovered_pages.yaml  # 本次发现的页面（引用全局pages）
│       │   ├── graph.yaml           # 页面关系图
│       │   ├── screenshots/
│       │   ├── logs/
│       │   └── reports/
│       └── run-002/
│
└── test_cases/                      # 生成的测试用例
    └── agent-management/
        └── create-agent.spec.ts
```

### 2.3 Pages全局共享架构

**核心价值：**
- 一次探索，所有环境（测试/生产/本地）都能复用同一份pages产物
- pages产物存储在项目级目录，不随探索run变化
- 跨环境URL映射，支持不同环境的URL归一化

**工作流程：**

#### 阶段1：需求分析（定义测试内容）
需求文档定义测试场景、步骤和预期结果

#### 阶段2：页面探索（生成全局pages产物）
- 首次探索某页面 → 生成项目级pages产物
- 再次探索相同页面 → 检查缓存，如果一致则复用
- 跨环境探索 → 仅更新env_urls映射

#### 阶段3：测试用例生成（引用pages产物）
- 读取需求文档中的测试场景
- 从项目级pages中查找对应元素
- 生成测试代码

---

## 3. 核心组件设计

### 3.1 URL归一化策略

**目的**: 支持跨环境缓存复用

**关键设计点：**
- 提取路径部分作为归一化标识
- 保留环境映射关系（在pages产物的env_urls字段）
- 支持路径到完整URL的还原

**示例：**
```python
# 测试环境
url = "https://test.example.com/workspace/agents"
normalized = "/workspace/agents"

# 生产环境
url = "https://prod.example.com/workspace/agents"
normalized = "/workspace/agents"  # 相同

# 缓存检查时使用normalized_path，因此三个环境共享缓存
```

### 3.2 定位器优先级

**优先级顺序（从高到低）：**
1. `getByRole(role, { name })` - 最稳定，语义化最强
2. `getByLabel(label)` - 表单字段首选
3. `getByTestId(testId)` - 开发专门添加的测试ID
4. `getByText(text)` - 文本内容定位
5. `getByPlaceholder(placeholder)` - 输入框占位符
6. CSS选择器 - 最后选择，不推荐

**验证要求：**
- 每个定位器必须验证唯一性（count === 1）
- 每个定位器必须验证可见性（visible === true）
- 探索时直接使用语义定位器，不使用临时ref

### 3.3 缓存检查逻辑

```python
def check_cache(normalized_path: str, project_id: str) -> Optional[dict]:
    """
    检查页面是否已探索（项目级缓存）
    """
    cache_index_path = f"data/projects/{project_id}/page_exploration/cache_index.yaml"
    cache_index = load_yaml(cache_index_path)
    
    for page in cache_index.get('pages', []):
        if page['normalized_path'] == normalized_path:
            page_file = f"data/projects/{project_id}/page_exploration/{page['page_file']}"
            
            if Path(page_file).exists():
                return {
                    'cache_hit': True,
                    'page_file': page_file,
                    'page_id': page['page_id'],
                    'last_explored_at': page['last_explored_at']
                }
    
    return {'cache_hit': False}
```

### 3.4 产物Schema

#### cache_index.yaml（项目级缓存索引）

```yaml
version: "1.0"
project_id: "proj-123"

pages:
  - normalized_path: "/workspace/agents"
    page_id: "page-workspace-agents"
    page_file: "pages/page-workspace-agents.yaml"
    
    last_explored_at: "2026-06-26T11:00:00Z"
    last_run_id: "run-001"
    
    signature:
      title: "智能体工作台"
      element_count: 15
      interactive_element_count: 8
    
    env_urls:
      prod: "https://prod.example.com/workspace/agents"
      test: "https://test.example.com/workspace/agents"
```

#### discovered_pages.yaml（本次探索发现的页面清单）

```yaml
run_id: "run-001"
discovered_at: "2026-06-26T11:00:00Z"

pages:
  - page_id: "page-workspace-agents"
    page_file: "../../pages/page-workspace-agents.yaml"
    normalized_path: "/workspace/agents"
    cache_status: "miss"  # miss=本次新探索, hit=复用缓存
    elements_count: 15
    exploration_status: "completed"
```

#### pages/page-*.yaml（项目级页面产物）

```yaml
page:
  id: "page-001"
  title: "智能体工作台"
  normalized_path: "/workspace/agents"
  explored_at: "2026-06-26T11:00:00Z"

states:
  - id: "default"
    type: "page"
    elements:
      - id: "create_agent_btn"
        name: "创建智能体"
        role: "button"
        
        locators:
          - kind: "role"
            code: "getByRole('button', { name: '创建智能体' })"
            priority: 1
            validation:
              is_unique: true
              is_visible: true
```

---

## 4. Skills设计

### 4.1 推荐方案

采用 **2个核心skills** 的方案：

1. **page_explorer** - 探索策略和页面分析
2. **locator_best_practices** - 定位器选择最佳实践

**不包括**：
- ❌ cache_strategy - 缓存是纯编程逻辑，由CacheManager处理

### 4.2 Skill 1: page_explorer

**职责**：指导Agent如何智能探索网站

**核心内容**：
- 探索顺序策略（广度优先 vs 深度优先）
- 如何判断页面是否值得探索
- 如何识别导航元素（菜单、面包屑、链接）
- 探索深度控制
- 错误处理策略

### 4.3 Skill 2: locator_best_practices

**职责**：指导如何选择最佳定位器

**核心内容**：
- 定位器优先级规则
- 为什么不使用ref和CSS选择器
- 如何为不同类型元素选择定位器
- 定位器唯一性验证方法
- 何时标记需要人工review

---

## 5. 探索流程和终止逻辑

### 5.1 探索流程

```
1. 启动探索任务
   ↓
2. 加载项目级缓存索引 (cache_index.yaml)
   ↓
3. Agent 探索循环：
   a. 获取当前页面快照 (playwright-cli snapshot)
   b. 归一化URL并检查缓存
   c. 如已探索 → 复用项目级pages产物，跳过该页
   d. 如未探索 → 继续探索
   e. 识别操作场景（导航/表单/搜索）
   f. 为元素生成语义定位器
   g. 执行操作（导航点击/表单填写/搜索）
   h. 关键点获取快照
   i. 写入/更新项目级pages产物
   j. 更新项目级缓存索引
   k. 记录到discovered_pages.yaml
   l. 判断是否继续
   ↓
4. 生成本次run的探索报告
   ↓
5. 更新任务状态
```

### 5.2 终止条件

满足任一即停止：

#### 1. 目标达成终止
```python
if exploration_queue.is_empty():
    stop_reason = "all_pages_explored"
    terminate()
```

#### 2. 达到限制终止
- 页面数量达到上限
- 探索时间达到上限
- 探索深度达到上限

#### 3. 错误终止
- 连续失败次数过多
- Agent无法继续

#### 4. 手动终止
- 用户主动停止

### 5.3 URL队列管理

```python
class ExplorationQueue:
    def __init__(self, start_url, scope):
        self.queue = deque([start_url])
        self.explored = set()
        self.scope = scope
    
    def add_url(self, url):
        normalized = normalize_url(url)
        
        if normalized in self.explored:
            return False
        
        if not self._in_scope(url):
            return False
        
        if url in self.queue:
            return False
        
        self.queue.append(url)
        return True
    
    def pop(self):
        if self.is_empty():
            return None
        return self.queue.popleft()
    
    def mark_explored(self, url):
        normalized = normalize_url(url)
        self.explored.add(normalized)
```

### 5.4 循环检测

**场景A: 双向链接**
```
Page A → Page B
Page B → Page A
```
**解决**: 使用explored set

**场景B: 同一页面多个URL**
```
/workspace/agents
/workspace/agents?tab=all
/workspace/agents#section1
```
**解决**: URL归一化（去除query和fragment）

**场景C: 分页链接**
```
/agents?page=1
/agents?page=2
...
```
**解决**: 限制同一路径的探索次数

---

## 6. 错误处理策略

### 6.1 核心原则

1. **分类处理** - 不同类型的错误用不同策略
2. **快速失败** - 不可恢复的错误立即停止
3. **智能重试** - 可恢复的错误自动重试
4. **记录详细** - 所有错误都要记录

### 6.2 错误分类和处理

#### 定位器错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| 定位器不唯一 | 0 | Agent优化定位器 |
| 元素未找到 | 1 | 等待2秒后重试 |
| 元素不可见 | 1 | 滚动后重试 |

#### 页面加载错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| 页面加载超时 | 2 | 等待3秒后重试 |
| 404错误 | 0 | 不重试 |
| 500错误 | 1 | 等待5秒后重试 |

#### Agent错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| Agent决策失败 | 3 | LLM可能临时故障 |
| Token超限 | 1 | 简化快照后重试 |

#### 网络错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| 连接超时 | 3 | 等待5秒后重试 |
| 连接中断 | 2 | 等待3秒后重试 |

#### Playwright CLI错误

| 错误类型 | 重试次数 | 处理策略 |
|---------|---------|---------|
| Playwright崩溃 | 1 | 重启进程后重试 |

### 6.3 致命错误（立即终止）

以下错误不重试，直接终止：
1. 认证失败 - Session过期
2. 权限不足 - 403 Forbidden
3. Playwright无法启动 - 环境问题
4. 配置错误 - 探索配置无效

### 6.4 错误处理流程

```python
class ErrorHandler:
    def __init__(self):
        self.consecutive_failures = 0
        self.total_failures = 0
        self.max_consecutive = 3
        self.max_total = 10
    
    def handle_error(self, error, context):
        # 1. 记录错误
        self.log_error(error, context)
        
        # 2. 增加计数
        self.total_failures += 1
        self.consecutive_failures += 1
        
        # 3. 检查是否应该终止
        if self.should_terminate():
            raise ExplorationFailedError("错误过多，终止探索")
        
        # 4. 分类处理
        error_type = self.classify_error(error)
        strategy = self.get_strategy(error_type)
        
        # 5. 执行策略
        result = strategy.handle(error, context)
        
        # 6. 如果成功，重置连续失败计数
        if result['status'] == 'success':
            self.consecutive_failures = 0
        
        return result
```

---

## 7. 实施计划

### 7.1 已完成（30%）

- [x] 架构设计 100%
- [x] Skills设计 100%
- [x] 基础设施 80%（URLNormalizer, LocatorValidator, PlaywrightCLIWrapper, Schemas）
- [x] ProjectPagesService（项目级pages管理）

### 7.2 实施阶段

#### 阶段1: Agent核心实现（优先级 P0）
**预计时间**: 3-4天

- [ ] Agent定义（agent.py）
- [ ] Agent Tools（playwright_tools.py, cache_tools.py, artifact_tools.py）
- [ ] Prompts（system_prompt.py, exploration_prompt.py）

#### 阶段2: 探索服务实现（优先级 P0）
**预计时间**: 3-4天

- [ ] 探索编排器（orchestrator.py）
- [ ] 产物服务（artifact_service.py）

#### 阶段3: SSE进度传输（优先级 P1）
**预计时间**: 2-3天

- [ ] 事件发射器（event_emitter.py）
- [ ] 数据库模型（ExplorationRun, ExplorationEventLog）
- [ ] API路由（page_exploration.py）

#### 阶段4: 前端集成（优先级 P1）
**预计时间**: 2天

- [ ] SSE Hook（useExplorationStream.ts）
- [ ] 进度展示组件（ExplorationProgressPanel.tsx）
- [ ] 探索任务表单（CreateExplorationForm.tsx）

#### 阶段5: 测试（优先级 P1）
**预计时间**: 4天

- [ ] 单元测试
- [ ] 集成测试
- [ ] E2E测试

#### 阶段6: 依赖和环境（优先级 P0）
**预计时间**: 0.5天

- [ ] 安装playwright-cli
- [ ] 验证playwright-cli可用
- [ ] 安装Python依赖

### 7.3 时间表

- **第1周（5天）**: Agent核心 + 探索服务
- **第2周（5天）**: SSE进度 + 前端集成 + 单元测试
- **第3周（3天）**: 集成测试 + E2E测试 + 文档完善

**总计**: 约13个工作日

### 7.4 里程碑

- **Milestone 1**: Agent核心完成（第1周结束）
- **Milestone 2**: 完整流程打通（第2周结束）
- **Milestone 3**: 生产就绪（第3周结束）

---

## 8. 验收标准

### 8.1 功能验收

- [ ] 能创建探索任务并指定范围、目标、禁止路径
- [ ] 探索过程中使用语义定位器（无ref）
- [ ] 每个定位器都经过唯一性和可见性验证
- [ ] 生成符合Schema的页面产物YAML
- [ ] 缓存系统正常工作，相同路径不重复探索
- [ ] 跨环境URL归一化正确
- [ ] 生成探索图谱和报告
- [ ] SSE实时推送探索进度
- [ ] 页面刷新后能恢复历史进度
- [ ] 前端能查看探索结果和产物

### 8.2 性能验收

- [ ] 缓存命中率 > 30%（第二次探索）
- [ ] 单页探索时间 < 1分钟
- [ ] SSE事件延迟 < 1秒

### 8.3 质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试全部通过
- [ ] E2E测试全部通过
- [ ] 元素定位器覆盖率 > 95%
- [ ] 定位器唯一性 = 100%

---

## 9. 关键技术决策

### 9.1 为什么不使用ref？
- ref是playwright-cli快照时生成的临时引用（e15, e20等）
- ref在下次快照时会变化，不能在测试用例中复用
- 语义定位器稳定且可读性强，适合测试用例

### 9.2 为什么采用项目级pages？
- 一次探索，所有run共享
- 跨环境复用（测试/生产/本地）
- 维护成本低，页面更新只需更新一个文件

### 9.3 缓存何时失效？
- 手动清除缓存
- 页面结构发生重大变化（通过element_count检测）
- 指定缓存过期时间（可选）

---

## 附录

### A. 参考资料

- DeepAgents文档
- Playwright CLI文档
- SSE规范
- 项目架构设计

### B. 未来扩展

- 支持登录流程自动化
- 支持验证码识别
- 支持动态内容等待策略
- 支持多浏览器并行探索
- 与测试用例生成模块集成

---

**文档版本**: 1.0  
**最后更新**: 2026-06-26
