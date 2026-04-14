from abc import ABC, abstractmethod
from app.models.schemas import SummaryResult, TranscriptionResult


SUMMARY_SYSTEM_PROMPT = """You are an expert analyst specializing in audio content analysis.
Your task is to analyze transcribed speech and produce structured insights.
Always respond with valid JSON only — no markdown, no extra text."""


def build_analysis_prompt(transcription: TranscriptionResult, depth: str) -> str:
    depth_instruction = {
        "quick": "Be concise. short_summary max 1 sentence, 3 key_points, 2 insights.",
        "standard": "Balanced analysis. 2-sentence short_summary, 5 key_points, 3-4 insights.",
        "deep": "Thorough analysis. detailed short_summary, 8+ key_points, 5+ insights, identify implicit themes.",
    }[depth]

    return f"""Analyze this transcription and respond ONLY with a JSON object matching this exact schema:

{{
  "short_summary": "string (1-2 sentences)",
  "detailed_summary": "string (full paragraph)",
  "key_points": ["string", ...],
  "insights": [
    {{"category": "string", "content": "string", "confidence": "high|medium|low"}},
    ...
  ],
  "action_items": ["string", ...],
  "sentiment": "positive|negative|neutral|mixed",
  "topics": ["string", ...],
  "word_count": {transcription.word_count if hasattr(transcription, 'word_count') else len(transcription.text.split())}
}}

Instruction: {depth_instruction}

Transcription (language: {transcription.language}, duration: {transcription.duration_seconds:.1f}s):
---
{transcription.text}
---

Respond with JSON only."""


class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def analyze(
        self,
        transcription: TranscriptionResult,
        depth: str = "standard",
    ) -> SummaryResult: ...

    def _parse_analysis_json(self, raw: str, provider: str, model: str) -> SummaryResult:
        import json
        import re

        # Strip markdown fences if present
        clean = re.sub(r"```json\s*|\s*```", "", raw).strip()

        data = json.loads(clean)
        insights = [
            type("Insight", (), i)() if isinstance(i, dict) else i
            for i in data.get("insights", [])
        ]

        from app.models.schemas import Insight
        return SummaryResult(
            short_summary=data.get("short_summary", ""),
            detailed_summary=data.get("detailed_summary", ""),
            key_points=data.get("key_points", []),
            insights=[Insight(**i) for i in data.get("insights", [])],
            action_items=data.get("action_items", []),
            sentiment=data.get("sentiment", "neutral"),
            topics=data.get("topics", []),
            word_count=data.get("word_count", 0),
            provider=provider,
            model=model,
        )
