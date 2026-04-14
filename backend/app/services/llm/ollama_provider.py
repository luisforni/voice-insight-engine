import httpx
from app.services.llm.base import LLMProvider, SUMMARY_SYSTEM_PROMPT, build_analysis_prompt
from app.models.schemas import SummaryResult, TranscriptionResult
from app.core.config import get_settings


class OllamaProvider(LLMProvider):
    def __init__(self):
        self._settings = get_settings()

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._settings.OLLAMA_MODEL

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{self._settings.OLLAMA_BASE_URL}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self._settings.OLLAMA_BASE_URL}/api/tags")
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    async def pull_model(self, model: str) -> dict:
        """Trigger a model pull on Ollama (async, streams progress)."""
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(
                f"{self._settings.OLLAMA_BASE_URL}/api/pull",
                json={"name": model, "stream": False},
            )
            return r.json()

    async def analyze(self, transcription: TranscriptionResult, depth: str = "standard") -> SummaryResult:
        prompt = build_analysis_prompt(transcription, depth)

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.3},
                },
            )
            data = response.json()
            raw = data["message"]["content"]

        return self._parse_analysis_json(raw, self.provider_name, self.model_name)
