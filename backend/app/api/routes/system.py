from fastapi import APIRouter
from app.models.schemas import SystemStatus, ProviderStatus
from app.services.llm import all_providers
from app.services.transcription import get_transcription_provider
from app.core.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/status", response_model=SystemStatus)
async def get_status():
    """Check availability of all configured providers."""
    settings = get_settings()

    llm_statuses = []
    for provider in all_providers():
        available = await provider.is_available()
        llm_statuses.append(ProviderStatus(
            provider=provider.provider_name,
            available=available,
            model=provider.model_name,
        ))

    transcription_statuses = []
    for name in ["local", "openai"]:
        p = get_transcription_provider(name)
        available = await p.is_available()
        model = "whisper-1 (API)" if name == "openai" else f"whisper-{settings.WHISPER_MODEL} (local)"
        transcription_statuses.append(ProviderStatus(
            provider=name,
            available=available,
            model=model,
        ))

    return SystemStatus(
        transcription_providers=transcription_statuses,
        llm_providers=llm_statuses,
        default_transcription=settings.DEFAULT_TRANSCRIPTION_PROVIDER,
        default_llm=settings.DEFAULT_LLM_PROVIDER,
    )


@router.get("/ollama/models")
async def list_ollama_models():
    """List models available in local Ollama."""
    from app.services.llm.ollama_provider import OllamaProvider
    provider = OllamaProvider()
    models = await provider.list_models()
    return {"models": models}


@router.post("/ollama/pull")
async def pull_ollama_model(model: str):
    """Pull a model from Ollama registry (e.g. llama3.2, mistral, gemma2)."""
    from app.services.llm.ollama_provider import OllamaProvider
    provider = OllamaProvider()
    result = await provider.pull_model(model)
    return {"status": "ok", "model": model, "result": result}
