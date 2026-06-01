from langchain.chat_models import init_chat_model

from app.agents.model_selection import ModelSelection, normalize_provider


def build_agent_model(selection: ModelSelection):
    provider = normalize_provider(selection.provider)
    model_provider = "openai" if provider == "openai-compatible" else provider
    return init_chat_model(
        model=selection.model,
        model_provider=model_provider,
        api_key=selection.api_key,
        base_url=selection.base_url,
        temperature=0,
    )
