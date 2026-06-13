"""
需求分析 v3.0 - LangChain 重构版

核心改进：
- Agentic Search：按需搜索辅助文档，token 节省 90%+
- LangGraph：状态机编排，支持并行和条件路由
- Callbacks：完整的可观测性
- 纯 Python：移除 Codex CLI 依赖
"""

from app.agents.requirement_analysis.v3.workflow import run_requirement_analysis_v3

__all__ = ["run_requirement_analysis_v3"]
