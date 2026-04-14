from app.services.llm.base import LLMProvider
from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.groq_provider import GroqProvider
from app.models.schemas import LLMProvider as LLMProviderEnum


_REGISTRY: dict[str, type[LLMProvider]] = {
    LLMProviderEnum.OLLAMA: OllamaProvider,
    LLMProviderEnum.OPENAI: OpenAIProvider,
    LLMProviderEnum.ANTHROPIC: AnthropicProvider,
    LLMProviderEnum.GROQ: GroqProvider,
}


def get_llm_provider(provider: LLMProviderEnum | str) -> LLMProvider:
    """Factory: returns the correct LLMProvider instance by name."""
    cls = _REGISTRY.get(str(provider))
    if not cls:
        raise ValueError(f"Unknown LLM provider: {provider}. Available: {list(_REGISTRY.keys())}")
    return cls()


def all_providers() -> list[LLMProvider]:
    return [cls() for cls in _REGISTRY.values()]
