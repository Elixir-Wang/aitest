# 需求分析 v2.0 - 前端集成指南

## 概述

本文档说明前端如何展示需求分析 v2.0 的四个子 tab。

---

## 四个子 Tab 架构

### 1. 需求理解 Tab
**数据源**: `result.understanding`

展示内容：
- 识别的模块列表
- 业务对象和规则
- 状态流转
- 风险和假设

**示例代码**:
```typescript
interface UnderstandingTab {
  modules: Module[];
  risks: Risk[];
  assumptions: Assumption[];
  summary: string;
}
```

---

### 2. 待处理内容 Tab
**数据源**: `result.clarification.items` (过滤后)

**重要**: 仅显示 `resolution_status !== "auto_resolved"` 的项

```typescript
// 过滤待处理项
const pendingItems = result.clarification.items.filter(
  item => item.resolution_status === "needs_manual" || 
          item.resolution_status === "has_suggestions"
);
```

展示内容：
- 按优先级排序的待澄清问题
- 严重程度标识（blocker/major/minor）
- 建议选项（如果有）
- 影响说明

**统计信息**: `result.clarification.summary`
```typescript
{
  total: 10,              // 总问题数
  auto_resolved: 2,       // 已自动解决
  has_suggestions: 5,     // 有建议选项
  needs_manual: 3         // 需要人工处理
}
```

---

### 3. 质量评估 Tab
**数据源**: `result.quality_assessment`

展示内容：
- 质量评分（完整性、清晰度、可测试性、一致性）
- 总分和决策结果（approved/conditional/rejected）
- 具体问题列表（NFR 缺口、模糊词、冲突等）
- 改进建议

**示例代码**:
```typescript
interface QualityTab {
  scores: {
    completeness: number;   // 0-100
    clarity: number;
    testability: number;
    consistency: number;
    overall: number;
  };
  decision: {
    result: "approved" | "conditional" | "rejected";
    rationale: string;
    blocking_issues: string[];
    recommended_actions: string[];
  };
}
```

---

### 4. 初步需求 Tab (新增)
**数据源**: `result.enhanced_requirement_markdown`

**功能**: 展示原始需求 + 自动补充的内容

展示格式：
1. **直接展示增强后的 Markdown**
2. **高亮显示补充内容**（标记为 `[自动补充]`）

**Markdown 结构**:
```markdown
# 增强版需求文档

> 本文档基于原始需求，补充了从辅助文档中自动解决的问题
> 标记为 **[自动补充]** 的内容来自辅助文档的增强

---

## 原始需求内容

[原始需求文档内容]

---

## 自动补充的内容

### 订单管理

> **[自动补充]** 响应时间要求是什么？
>
> **原始描述**: 系统应当快速
>
> **补充内容**: 响应时间 < 2秒
>
> **来源**: 技术标准.md
>
> **影响**: 无法评估性能

[更多补充内容...]
```

**前端渲染建议**:
- 使用 Markdown 渲染器（如 marked.js、react-markdown）
- 对 `[自动补充]` 标记的块应用特殊样式（如黄色背景高亮）
- 支持折叠/展开补充内容
- 显示补充内容的来源文档

**CSS 样式示例**:
```css
/* 高亮自动补充的内容 */
blockquote:has(strong:contains("[自动补充]")) {
  background-color: #fff3cd;
  border-left: 4px solid #ffc107;
  padding: 1rem;
  margin: 1rem 0;
}

/* 补充内容标记 */
.auto-enhanced-marker {
  color: #ff6b00;
  font-weight: bold;
}

/* 来源标识 */
.source-reference {
  color: #6c757d;
  font-size: 0.875rem;
  font-style: italic;
}
```

---

## API 响应结构

```typescript
interface RequirementAnalysisResult {
  status: "completed" | "needs_clarification" | "blocked";
  
  // Tab 1: 需求理解
  understanding: UnderstandingOutput;
  
  // Tab 2: 待处理内容
  clarification: {
    items: ClarificationItem[];  // 需要前端过滤
    summary: ClarificationSummary;
  };
  
  // Tab 3: 质量评估
  quality_assessment: QualityAssessmentOutput;
  
  // Tab 4: 初步需求
  enhanced_requirement_markdown: string;
  
  // 其他
  analysis_report_markdown: string;
  metadata: Record<string, any>;
}
```

---

## 前端实现示例

### React 组件结构

```tsx
import { Tabs } from '@/components/ui/tabs';
import ReactMarkdown from 'react-markdown';

function RequirementAnalysisView({ result }: { result: RequirementAnalysisResult }) {
  // 过滤待处理项
  const pendingItems = result.clarification.items.filter(
    item => item.resolution_status !== "auto_resolved"
  );

  return (
    <Tabs defaultValue="understanding">
      <TabsList>
        <TabsTrigger value="understanding">
          需求理解
        </TabsTrigger>
        <TabsTrigger value="pending">
          待处理内容
          <Badge>{result.clarification.summary.needs_manual}</Badge>
        </TabsTrigger>
        <TabsTrigger value="quality">
          质量评估
        </TabsTrigger>
        <TabsTrigger value="enhanced">
          初步需求
          <Badge variant="success">
            {result.clarification.summary.auto_resolved} 项已补充
          </Badge>
        </TabsTrigger>
      </TabsList>

      {/* Tab 1: 需求理解 */}
      <TabsContent value="understanding">
        <UnderstandingTab data={result.understanding} />
      </TabsContent>

      {/* Tab 2: 待处理内容 */}
      <TabsContent value="pending">
        <PendingItemsList items={pendingItems} />
      </TabsContent>

      {/* Tab 3: 质量评估 */}
      <TabsContent value="quality">
        <QualityAssessmentTab data={result.quality_assessment} />
      </TabsContent>

      {/* Tab 4: 初步需求 */}
      <TabsContent value="enhanced">
        <div className="markdown-enhanced">
          <ReactMarkdown
            components={{
              blockquote: ({ node, ...props }) => {
                const text = props.children?.toString() || '';
                const isAutoEnhanced = text.includes('[自动补充]');
                return (
                  <blockquote 
                    className={isAutoEnhanced ? 'auto-enhanced' : ''}
                    {...props}
                  />
                );
              }
            }}
          >
            {result.enhanced_requirement_markdown}
          </ReactMarkdown>
        </div>
      </TabsContent>
    </Tabs>
  );
}
```

---

## 数据过滤辅助函数

### 后端提供的辅助函数

```python
from app.agents.requirement_analysis import (
    get_auto_resolved_items,   # 获取已自动解决的项
    get_pending_items,          # 获取待处理的项
)

# 使用示例
pending_items = get_pending_items(result.clarification.items)
auto_resolved = get_auto_resolved_items(result.clarification.items)
```

### 前端 TypeScript 辅助函数

```typescript
// 获取待处理项（用于 Tab 2）
export function getPendingItems(items: ClarificationItem[]): ClarificationItem[] {
  return items.filter(
    item => item.resolution_status === "needs_manual" || 
            item.resolution_status === "has_suggestions"
  );
}

// 获取已自动解决的项
export function getAutoResolvedItems(items: ClarificationItem[]): ClarificationItem[] {
  return items.filter(item => item.resolution_status === "auto_resolved");
}

// 按严重程度分组
export function groupBySeverity(items: ClarificationItem[]): Record<string, ClarificationItem[]> {
  return items.reduce((groups, item) => {
    const severity = item.severity;
    if (!groups[severity]) {
      groups[severity] = [];
    }
    groups[severity].push(item);
    return groups;
  }, {} as Record<string, ClarificationItem[]>);
}
```

---

## 关键点总结

### Tab 2（待处理内容）
- ✅ **仅显示** `needs_manual` 和 `has_suggestions` 的项
- ✅ **不显示** `auto_resolved` 的项
- ✅ 使用 `result.clarification.summary` 显示统计信息

### Tab 4（初步需求）
- ✅ 直接渲染 `enhanced_requirement_markdown` 
- ✅ 高亮标记为 `[自动补充]` 的内容
- ✅ 显示补充内容的来源文档
- ✅ 支持折叠/展开功能

### 数据关系
```
全部澄清项 (clarification.items)
├── auto_resolved → 显示在 Tab 4（初步需求）
└── needs_manual + has_suggestions → 显示在 Tab 2（待处理内容）
```

---

## 测试要点

1. **验证过滤逻辑**: Tab 2 应该不显示 `auto_resolved` 的项
2. **验证统计准确性**: `clarification.summary` 的数字应该与实际过滤结果一致
3. **验证 Markdown 渲染**: Tab 4 应正确渲染高亮和特殊标记
4. **验证空状态**: 没有待处理项或没有自动补充内容时的显示

---

## 完整示例

参考集成测试: `tests/agents/requirement_analysis/test_integration_v2.py`

```python
# 后端返回的完整数据结构
result = await service.analyze(input_data)

# 前端可以直接使用：
# - result.understanding        → Tab 1
# - result.clarification.items  → Tab 2 (需过滤)
# - result.quality_assessment   → Tab 3
# - result.enhanced_requirement_markdown → Tab 4
```
