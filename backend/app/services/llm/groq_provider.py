from app.services.llm.base import LLMProvider, SUMMARY_SYSTEM_PROMPT, build_analysis_prompt
from app.models.schemas import SummaryResult, TranscriptionResult
from app.core.config import get_settings


class GroqProvider(LLMProvider):
    def __init__(self):
        self._settings = get_settings()

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._settings.GROQ_MODEL

    async def is_available(self) -> bool:
        return bool(self._settings.GROQ_API_KEY)

    async def analyze(self, transcription: TranscriptionResult, depth: str = "standard") -> SummaryResult:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=self._settings.GROQ_API_KEY)
        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": build_analysis_prompt(transcription, depth)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        raw = response.choices[0].message.content
        return self._parse_analysis_json(raw, self.provider_name, self.model_name)
