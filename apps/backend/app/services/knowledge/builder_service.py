from app.schemas.knowledge import KnowledgeBuildInput, KnowledgeBuildOutput


async def run_knowledge_builder(input_data: KnowledgeBuildInput) -> KnowledgeBuildOutput:
    raise RuntimeError("knowledge_builder agent has not been migrated to canonical app.agents packages.")


__all__ = ["run_knowledge_builder"]
