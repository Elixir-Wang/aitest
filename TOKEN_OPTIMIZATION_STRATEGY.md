# Token 优化策略 - 需求分析工作流

基于 baigong-platform-requirement-analyzer 的最佳实践

---

## 📊 问题现状

当前工作流：**理解 → 质疑 → 质量评估 → 澄清**

### Token 爆炸点分析

| 节点 | 输入 | 输出 | 传递给下游 | Token 消耗 |
|------|------|------|-----------|----------|
| 理解 | 需求文档(10K) | 理解结果(15K) + **Mermaid(3K)** | 完整 JSON | **28K** |
| 质疑 | 理解结果(15K) + 需求文档(10K) | 质疑结果(12K) | 完整 JSON | **37K** |
| 质量评估 | 理解(15K) + 质疑(12K) + 需求(10K) | 质量结果(8K) | 完整 JSON | **45K** |
| 澄清 | 理解(15K) + 质疑(12K) + 质量(8K) | 澄清结果(10K) | - | **45K** |
| **总计** | - | - | - | **155K tokens** |

### 痛点

1. **理解节点生成 Mermaid**：状态图/领域模型图，3-5K tokens
2. **下游重复读取**：每个节点都传完整 JSON，累积 token
3. **无增量更新**：修改一个小问题，重新生成整个结果

---

## ✅ 优化方案（参考 baigong）

### 策略 1：分层摘要传递（Brief Pattern）

**核心思想**：下游节点只接收**摘要版**，需要时才读完整版。

#### 1.1 创建轻量化摘要类

```python
# core/schemas.py - 新增

class QuestioningBrief(BaseModel):
    """质疑分析摘要：供下游使用"""
    high_risk_count: int = Field(description="🔴高风险数量")
    medium_risk_count: int = Field(description="🟡中风险数量")
    breaker_status: str = Field(description="熔断状态：halt/review/pass")
    
    # 仅传递关键疑点 ID，不传完整内容
    critical_question_ids: list[str] = Field(description="关键疑点ID列表")
    adversarial_scenario_count: int = Field(description="反向场景数量")
    
    # 9宫格摘要（仅传统计，不传完整矩阵）
    nine_grid_summary: dict[str, int] = Field(
        description="9宫格统计：{WHAT: 3, WHY: 0, WHO: 2, ...}"
    )


class UnderstandingBriefV2(BaseModel):
    """需求理解摘要 v2：供质疑/质量评估使用"""
    business_goal: str
    modules: list[str]
    actors: list[str]
    p0_flows: list[str]
    
    # 新增：Mermaid 引用路径，不传源码
    mermaid_files: dict[str, str] = Field(
        default_factory=dict,
        description="Mermaid 文件路径：{state_machine: 'path/to/state.mmd', ...}"
    )
    
    # 新增：关键风险 ID，不传完整风险对象
    high_risk_ids: list[str] = Field(description="高风险 ID 列表")
```

#### 1.2 修改 orchestrator 传递逻辑

```python
# orchestrator.py

async def run_requirement_analysis(input_data: RequirementAnalysisInputV2):
    # ... 理解节点
    understanding, deep_understanding = await run_understanding_agent(...)
    
    # 生成摘要（传递给下游）
    understanding_brief = build_understanding_brief_v2(understanding)
    
    # 保存 Mermaid 到文件系统（不传递源码）
    mermaid_paths = await save_mermaid_diagrams(
        deep_understanding.get("domain_model"),
        output_dir=f"release_version/{input_data.version}/{input_data.requirement_name}/diagrams/"
    )
    understanding_brief.mermaid_files = mermaid_paths
    
    # 质疑节点：只传摘要
    questioning, questioning_metadata = await run_questioning_agent(
        model=model,
        primary_markdown_content=input_data.primary_markdown_content,
        understanding_brief=understanding_brief,  # ✅ 摘要版
        run_id=input_data.run_id,
    )
    
    # 生成质疑摘要
    questioning_brief = build_questioning_brief(questioning)
    
    # 质量评估节点：传摘要
    quality = await run_quality_assessment_agent(
        model=model,
        understanding_brief=understanding_brief,    # ✅ 摘要版
        questioning_brief=questioning_brief,         # ✅ 摘要版
        primary_markdown_content=input_data.primary_markdown_content,
    )
```

**Token 节省效果**：
- 理解结果：15K → 2K（摘要） = **节省 87%**
- 质疑结果：12K → 1.5K（摘要） = **节省 88%**
- 质量评估输入：27K → 3.5K = **节省 87%**

---

### 策略 2：Mermaid 分离存储（不传递源码）

**核心思想**：Mermaid 代码生成后立即保存为文件，传递**路径引用**。

#### 2.1 创建 Mermaid 管理工具

```python
# utils/mermaid_manager.py

from pathlib import Path
import json

class MermaidManager:
    """Mermaid 图管理器：生成 → 保存 → 引用"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_state_machine(
        self,
        state_object_name: str,
        mermaid_code: str,
    ) -> str:
        """保存状态机图"""
        filename = f"{state_object_name}_state_machine.mmd"
        filepath = self.output_dir / filename
        
        filepath.write_text(mermaid_code, encoding="utf-8")
        
        # 可选：调用 Kroki API 生成 PNG
        png_path = await self._render_to_png(mermaid_code, filepath)
        
        return str(filepath.relative_to(self.output_dir.parent))
    
    async def save_domain_model(
        self,
        mermaid_code: str,
    ) -> str:
        """保存领域模型图"""
        filename = "domain_model.mmd"
        filepath = self.output_dir / filename
        filepath.write_text(mermaid_code, encoding="utf-8")
        return str(filepath.relative_to(self.output_dir.parent))
    
    def load_mermaid(self, relative_path: str) -> str:
        """按需加载 Mermaid 源码"""
        filepath = self.output_dir.parent / relative_path
        return filepath.read_text(encoding="utf-8")
    
    async def _render_to_png(self, mermaid_code: str, mmd_path: Path) -> str:
        """调用 Kroki API 渲染为 PNG"""
        import urllib.request
        import base64
        import zlib
        
        compressed = zlib.compress(mermaid_code.encode('utf-8'))
        encoded = base64.urlsafe_b64encode(compressed).decode('ascii')
        
        png_url = f'https://kroki.io/mermaid/png/{encoded}'
        png_path = mmd_path.with_suffix('.png')
        
        try:
            req = urllib.request.Request(png_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                png_path.write_bytes(response.read())
            return str(png_path.relative_to(self.output_dir.parent))
        except Exception as e:
            print(f"PNG 生成失败: {e}")
            return ""
```

#### 2.2 修改理解节点生成逻辑

```python
# agents/understanding.py

async def run_understanding_agent(
    model,
    primary_markdown_content: str,
    *,
    run_id: str = "",
    metadata: dict[str, Any] | None = None,
    output_dir: str = "",  # 新增：输出目录
) -> tuple[RequirementUnderstandingOutput, dict[str, Any]]:
    """Run the requirement understanding agent."""
    from datetime import datetime
    from app.agents.requirement_analysis.utils.mermaid_manager import MermaidManager
    
    metadata = metadata if metadata is not None else {}
    explainer = ExplanationGenerator()
    
    # ... 原有逻辑 ...
    
    # 新增：保存 Mermaid 图到文件系统
    if output_dir:
        mermaid_mgr = MermaidManager(output_dir)
        mermaid_paths = {}
        
        # 保存状态机图
        for state_flow in deep_result.domain_model.state_machines:
            if state_flow.mermaid_code:
                path = await mermaid_mgr.save_state_machine(
                    state_flow.object_name,
                    state_flow.mermaid_code
                )
                mermaid_paths[f"state_{state_flow.object_name}"] = path
        
        # 保存领域模型图（如果有）
        if hasattr(deep_result.domain_model, 'mermaid_diagram'):
            path = await mermaid_mgr.save_domain_model(
                deep_result.domain_model.mermaid_diagram
            )
            mermaid_paths["domain_model"] = path
        
        # 在元数据中记录路径，不传源码
        metadata["mermaid_files"] = mermaid_paths
    
    return (
        _map_deep_result_to_understanding(deep_result),
        _build_deep_understanding_metadata(deep_result),
    )
```

**Token 节省效果**：
- Mermaid 源码：3-5K tokens
- 传递路径：0.05K tokens
- **节省 99%**

---

### 策略 3：按需读取（Lazy Loading）

**核心思想**：下游节点收到路径引用，仅在**强依赖时**才加载完整内容。

#### 3.1 创建按需加载工具

```python
# utils/context_loader.py

from pathlib import Path
from typing import Optional

class ContextLoader:
    """上下文按需加载器"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
    
    def load_if_needed(
        self,
        brief_obj: Any,
        full_result_path: Optional[str] = None,
        need_conditions: list[str] = None,
    ) -> Any:
        """
        按需加载完整结果
        
        Args:
            brief_obj: 摘要对象
            full_result_path: 完整结果文件路径
            need_conditions: 需要加载的条件列表
        
        Returns:
            如果满足条件，返回完整对象；否则返回摘要
        """
        # 检查是否需要完整内容
        needs_full = False
        
        for condition in (need_conditions or []):
            if condition == "high_risk_exists":
                if hasattr(brief_obj, 'high_risk_count') and brief_obj.high_risk_count > 0:
                    needs_full = True
            elif condition == "breaker_triggered":
                if hasattr(brief_obj, 'breaker_status') and brief_obj.breaker_status != "pass":
                    needs_full = True
        
        if needs_full and full_result_path:
            # 从文件加载完整结果
            full_path = self.base_dir / full_result_path
            if full_path.exists():
                import json
                return json.loads(full_path.read_text(encoding="utf-8"))
        
        return brief_obj
```

#### 3.2 修改质量评估节点

```python
# agents/quality.py

async def run_quality_assessment_agent(
    model,
    understanding_brief: UnderstandingBriefV2,
    questioning_brief: QuestioningBrief,
    primary_markdown_content: str,
    *,
    context_loader: Optional[ContextLoader] = None,
) -> QualityAssessmentOutput:
    """Run the quality assessment agent."""
    
    # 按需加载完整结果（仅当有高风险或熔断时）
    questioning_full = None
    if context_loader and questioning_brief.breaker_status != "pass":
        questioning_full = context_loader.load_if_needed(
            questioning_brief,
            full_result_path="questioning_result.json",
            need_conditions=["breaker_triggered", "high_risk_exists"]
        )
    
    # 构建 prompt（优先使用摘要，需要时用完整版）
    user_content = f"""
# 需求理解摘要
{understanding_brief.model_dump_json(indent=2)}

# 质疑分析摘要
{questioning_brief.model_dump_json(indent=2)}

{"# 质疑分析详情（因触发熔断，加载完整内容）" if questioning_full else ""}
{questioning_full.model_dump_json(indent=2) if questioning_full else ""}

# 主需求文档
{primary_markdown_content}
"""
    
    # ... 原有逻辑 ...
```

**Token 节省效果**：
- 正常情况：仅传摘要（3.5K tokens）
- 熔断触发：传摘要 + 完整质疑结果（3.5K + 12K = 15.5K tokens）
- **平均节省 70-80%**（大部分需求不会触发熔断）

---

### 策略 4：增量更新（Incremental Update）

**核心思想**：修改反馈时，只更新相关部分，不全量重做。

#### 4.1 创建增量更新工具

```python
# utils/incremental_updater.py

from typing import Any, Dict
import json

class IncrementalUpdater:
    """增量更新工具"""
    
    @staticmethod
    def update_questioning_nine_grid(
        original_result: QuestioningOutput,
        feedback: str,
        target_dimension: str,  # 例如 "WHO"（权限维度）
    ) -> QuestioningOutput:
        """
        增量更新 9 宫格矩阵
        
        Args:
            original_result: 原始质疑结果
            feedback: 用户反馈（例如："WHO 维度太弱，补充权限相关疑点"）
            target_dimension: 目标维度
        
        Returns:
            更新后的结果（仅修改相关维度）
        """
        updated = original_result.model_copy(deep=True)
        
        # 定位目标矩阵和维度
        for matrix in updated.nine_grid_matrices:
            for item in matrix.grid_items:
                if item.dimension == target_dimension:
                    # 仅更新这一个维度
                    item.status = "Q-NEW"
                    item.question = f"[根据反馈补充] {feedback}"
                    item.issue = "需要进一步明确权限边界"
        
        return updated
    
    @staticmethod
    def update_clarification_items(
        original_result: ClarificationOutput,
        feedback: str,
        target_item_ids: list[str],
    ) -> ClarificationOutput:
        """
        增量更新澄清项
        
        Args:
            original_result: 原始澄清结果
            feedback: 用户反馈
            target_item_ids: 需要更新的澄清项 ID
        
        Returns:
            更新后的结果（仅修改指定项）
        """
        updated = original_result.model_copy(deep=True)
        
        for item in updated.items:
            if item.item_id in target_item_ids:
                # 根据反馈更新
                item.why_clarify += f"\n\n【用户反馈】{feedback}"
                item.test_impact += f"\n- 根据反馈补充的影响分析"
        
        return updated
```

#### 4.2 在 orchestrator 中支持增量更新

```python
# orchestrator.py

async def run_requirement_analysis_with_feedback(
    input_data: RequirementAnalysisInputV2,
    previous_result: Optional[RequirementAnalysisResultV2] = None,
    user_feedback: Optional[str] = None,
) -> RequirementAnalysisResultV2:
    """
    支持增量更新的需求分析
    
    Args:
        input_data: 输入数据
        previous_result: 上一次的分析结果
        user_feedback: 用户反馈
    """
    if previous_result and user_feedback:
        # 增量更新模式
        updater = IncrementalUpdater()
        
        # 解析反馈，判断需要更新哪个节点
        if "9宫格" in user_feedback or "质疑" in user_feedback:
            # 仅重新运行质疑节点
            questioning = updater.update_questioning_nine_grid(
                previous_result.questioning,
                user_feedback,
                target_dimension="WHO" if "权限" in user_feedback else "WHAT"
            )
            
            # 其他节点复用
            return RequirementAnalysisResultV2(
                status=previous_result.status,
                understanding=previous_result.understanding,  # 复用
                questioning=questioning,  # 增量更新
                quality_assessment=previous_result.quality_assessment,  # 复用
                clarification=previous_result.clarification,  # 复用
                ...
            )
    
    # 否则，全量生成（首次运行）
    return await run_requirement_analysis(input_data)
```

**Token 节省效果**：
- 全量重做：155K tokens
- 增量更新（仅质疑节点）：3K tokens（更新质疑） + 0K（其他复用） = 3K tokens
- **节省 98%**

---

### 策略 5：结果文件化（Persistence Pattern）

**核心思想**：每个节点的结果立即保存到文件系统，跨节点传递**路径引用**。

#### 5.1 创建结果持久化工具

```python
# utils/result_persistence.py

from pathlib import Path
import json
from typing import Any
from datetime import datetime

class ResultPersistence:
    """结果持久化管理器"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_understanding_result(
        self,
        result: RequirementUnderstandingOutput,
        metadata: dict,
    ) -> str:
        """保存理解结果"""
        filename = "01_understanding_result.json"
        filepath = self.base_dir / filename
        
        data = {
            "result": result.model_dump(),
            "metadata": metadata,
            "timestamp": datetime.now().isoformat(),
        }
        
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(filepath.relative_to(self.base_dir.parent))
    
    def save_questioning_result(
        self,
        result: QuestioningOutput,
        metadata: dict,
    ) -> str:
        """保存质疑结果"""
        filename = "02_questioning_result.json"
        filepath = self.base_dir / filename
        
        data = {
            "result": result.model_dump(),
            "metadata": metadata,
            "timestamp": datetime.now().isoformat(),
        }
        
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(filepath.relative_to(self.base_dir.parent))
    
    def load_result(self, relative_path: str) -> dict:
        """加载结果"""
        filepath = self.base_dir.parent / relative_path
        return json.loads(filepath.read_text(encoding="utf-8"))
```

#### 5.2 修改 orchestrator 使用持久化

```python
# orchestrator.py

async def run_requirement_analysis(input_data: RequirementAnalysisInputV2):
    # 初始化持久化管理器
    persistence = ResultPersistence(
        f"release_version/{input_data.version}/{input_data.requirement_name}/analysis_results/"
    )
    
    # 1. 理解节点
    understanding, deep_understanding = await run_understanding_agent(...)
    understanding_path = persistence.save_understanding_result(understanding, deep_understanding)
    understanding_brief = build_understanding_brief_v2(understanding)
    
    # 2. 质疑节点（传摘要 + 路径）
    questioning, questioning_metadata = await run_questioning_agent(
        understanding_brief=understanding_brief,
        understanding_full_path=understanding_path,  # 路径引用
        ...
    )
    questioning_path = persistence.save_questioning_result(questioning, questioning_metadata)
    questioning_brief = build_questioning_brief(questioning)
    
    # 3. 质量评估节点（传摘要 + 路径）
    quality = await run_quality_assessment_agent(
        understanding_brief=understanding_brief,
        questioning_brief=questioning_brief,
        understanding_full_path=understanding_path,  # 路径引用
        questioning_full_path=questioning_path,      # 路径引用
        ...
    )
    
    # ... 后续节点类似
```

**Token 节省效果**：
- 跨节点传递：完整 JSON（15K） → 路径引用（0.05K）
- 4 个节点累积：4 × 15K = 60K → 4 × 0.05K = 0.2K
- **节省 99.7%**

---

## 📊 综合优化效果

### 优化前

| 节点 | 输入 Token | 输出 Token | 总计 |
|------|----------|----------|------|
| 理解 | 10K | 18K (含Mermaid 3K) | 28K |
| 质疑 | 10K + 15K(理解完整) = 25K | 12K | 37K |
| 质量评估 | 10K + 15K + 12K = 37K | 8K | 45K |
| 澄清 | 10K + 15K + 12K + 8K = 45K | 10K | 55K |
| **总计** | - | - | **165K** |

### 优化后

| 节点 | 输入 Token | 输出 Token | 总计 |
|------|----------|----------|------|
| 理解 | 10K | 15K (Mermaid保存文件,不计入) | 25K |
| 质疑 | 10K + 2K(理解摘要) = 12K | 12K | 24K |
| 质量评估 | 10K + 2K + 1.5K(质疑摘要) = 13.5K | 8K | 21.5K |
| 澄清 | 10K + 2K + 1.5K + 8K = 21.5K | 10K | 31.5K |
| **总计** | - | - | **102K** |
| **节省** | - | - | **38% ↓** |

### 修改循环优化（3次修改）

| 场景 | 优化前 | 优化后 | 节省 |
|------|-------|-------|------|
| 首次生成 | 165K | 102K | 38% |
| 修改 1 次 | 165K × 2 = 330K | 102K + 3K(增量) = 105K | 68% |
| 修改 2 次 | 165K × 3 = 495K | 102K + 6K(增量) = 108K | 78% |
| 修改 3 次 | 165K × 4 = 660K | 102K + 9K(增量) = 111K | 83% |

---

## 🚀 实施计划

### Phase 1：核心优化（立即实施）

#### 1.1 创建摘要类
- [ ] `QuestioningBrief` - 质疑摘要
- [ ] `UnderstandingBriefV2` - 理解摘要 v2（含 Mermaid 路径）

#### 1.2 Mermaid 分离
- [ ] `MermaidManager` - Mermaid 管理器
- [ ] 修改理解节点，保存 Mermaid 到文件
- [ ] 修改摘要传递逻辑

#### 1.3 更新 orchestrator
- [ ] 使用摘要传递
- [ ] 集成 Mermaid 管理器

### Phase 2：高级优化（1周内）

#### 2.1 按需加载
- [ ] `ContextLoader` - 上下文加载器
- [ ] 修改质量评估/澄清节点支持按需加载

#### 2.2 增量更新
- [ ] `IncrementalUpdater` - 增量更新工具
- [ ] 修改 orchestrator 支持反馈增量更新

#### 2.3 结果持久化
- [ ] `ResultPersistence` - 结果持久化管理器
- [ ] 跨节点传递路径引用

### Phase 3：监控优化（后续）

#### 3.1 Token 使用监控
```python
# utils/token_monitor.py

class TokenMonitor:
    """Token 使用监控"""
    
    def log_node_usage(self, node_name: str, input_tokens: int, output_tokens: int):
        """记录节点 token 使用"""
        pass
    
    def generate_report(self) -> dict:
        """生成 token 使用报告"""
        pass
```

---

## 📖 使用示例

### 优化后的调用方式

```python
from app.agents.requirement_analysis import run_requirement_analysis
from app.agents.requirement_analysis.utils.mermaid_manager import MermaidManager

# 首次分析
result = await run_requirement_analysis(
    RequirementAnalysisInputV2(
        primary_markdown_content="需求文档内容",
        project_id="proj-001",
        document_id="doc-001",
        version="V1.0.0",
        requirement_name="用户登录功能",
    )
)

# Mermaid 图已保存到：
# release_version/V1.0.0/用户登录功能/diagrams/
#   ├── order_state_machine.mmd
#   ├── order_state_machine.png
#   └── domain_model.mmd
#   └── domain_model.png

# 增量更新（用户反馈）
updated_result = await run_requirement_analysis_with_feedback(
    input_data=RequirementAnalysisInputV2(...),
    previous_result=result,
    user_feedback="9宫格的WHO维度太弱，补充权限相关疑点",
)

# Token 消耗：
# 首次：102K
# 增量：3K
# 总计：105K（vs 优化前 330K）
```

---

## 🎯 关键要点

1. **分层摘要**：下游节点默认接收摘要，需要时才读完整版
2. **Mermaid 分离**：生成后立即保存，传递路径引用
3. **按需加载**：仅在强依赖（熔断/高风险）时加载完整结果
4. **增量更新**：修改反馈只更新相关部分，不全量重做
5. **结果持久化**：跨节点传递路径，不传副本

---

*文档生成时间：2026-06-16*
*Token 优化版本：v1.0*
