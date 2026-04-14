from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum


class TranscriptionProvider(str, Enum):
    LOCAL = "local"
    OPENAI = "openai"


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"


class AnalysisRequest(BaseModel):
    transcription_provider: TranscriptionProvider = TranscriptionProvider.LOCAL
    llm_provider: LLMProvider = LLMProvider.OLLAMA
    language: Optional[str] = None  # None = auto-detect
    analysis_depth: Literal["quick", "standard", "deep"] = "standard"


class TranscriptionResult(BaseModel):
    text: str
    language: str
    duration_seconds: float
    provider: str
    segments: list[dict] = []


class Insight(BaseModel):
    category: str
    content: str
    confidence: Literal["high", "medium", "low"] = "medium"


class SummaryResult(BaseModel):
    short_summary: str        # 1-2 sentences
    detailed_summary: str     # paragraph
    key_points: list[str]
    insights: list[Insight]
    action_items: list[str]
    sentiment: Literal["positive", "negative", "neutral", "mixed"]
    topics: list[str]
    word_count: int
    provider: str
    model: str


class AnalysisResponse(BaseModel):
    job_id: str
    status: Literal["processing", "completed", "failed"]
    transcription: Optional[TranscriptionResult] = None
    analysis: Optional[SummaryResult] = None
    error: Optional[str] = None
    processing_time_ms: Optional[int] = None


class ProviderStatus(BaseModel):
    provider: str
    available: bool
    model: str
    details: Optional[str] = None


class SystemStatus(BaseModel):
    transcription_providers: list[ProviderStatus]
    llm_providers: list[ProviderStatus]
    default_transcription: str
    default_llm: str
