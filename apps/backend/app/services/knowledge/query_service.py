from app.schemas.knowledge import KnowledgeQueryInput, KnowledgeQueryOutput
from app.services.knowledge.codex_query import run_knowledge_query_with_codex


async def run_knowledge_query(input_data: KnowledgeQueryInput) -> KnowledgeQueryOutput:
    return await run_knowledge_query_with_codex(input_data)


__all__ = ["run_knowledge_query"]
