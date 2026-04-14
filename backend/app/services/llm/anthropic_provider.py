from app.services.llm.base import LLMProvider, SUMMARY_SYSTEM_PROMPT, build_analysis_prompt
from app.models.schemas import SummaryResult, TranscriptionResult
from app.core.config import get_settings


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self._settings = get_settings()

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._settings.ANTHROPIC_MODEL

    async def is_available(self) -> bool:
        return bool(self._settings.ANTHROPIC_API_KEY)

    async def analyze(self, transcription: TranscriptionResult, depth: str = "standard") -> SummaryResult:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self._settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=self.model_name,
            max_tokens=2048,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_analysis_prompt(transcription, depth)},
            ],
            temperature=0.3,
        )
        raw = response.content[0].text
        return self._parse_analysis_json(raw, self.provider_name, self.model_name)
