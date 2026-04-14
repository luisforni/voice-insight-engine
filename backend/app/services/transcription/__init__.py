import os
import time
import tempfile
from pathlib import Path
from abc import ABC, abstractmethod

from app.models.schemas import TranscriptionResult
from app.core.config import get_settings


class TranscriptionProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str, language: str | None = None) -> TranscriptionResult: ...

    @abstractmethod
    async def is_available(self) -> bool: ...


class LocalWhisperProvider(TranscriptionProvider):
    """Uses openai-whisper running locally."""

    _model_cache: dict = {}

    async def is_available(self) -> bool:
        try:
            import whisper  # noqa
            return True
        except ImportError:
            return False

    def _load_model(self):
        import whisper
        settings = get_settings()
        key = f"{settings.WHISPER_MODEL}_{settings.WHISPER_DEVICE}"
        if key not in self._model_cache:
            self._model_cache[key] = whisper.load_model(
                settings.WHISPER_MODEL,
                device=settings.WHISPER_DEVICE,
            )
        return self._model_cache[key]

    async def transcribe(self, audio_path: str, language: str | None = None) -> TranscriptionResult:
        import asyncio
        import functools

        loop = asyncio.get_event_loop()

        def _run():
            model = self._load_model()
            opts = {"verbose": False}
            if language:
                opts["language"] = language
            result = model.transcribe(audio_path, **opts)
            return result

        start = time.time()
        result = await loop.run_in_executor(None, _run)
        elapsed = time.time() - start

        # Estimate audio duration from segments
        duration = 0.0
        if result.get("segments"):
            duration = result["segments"][-1].get("end", 0.0)

        return TranscriptionResult(
            text=result["text"].strip(),
            language=result.get("language", "unknown"),
            duration_seconds=duration,
            provider="local-whisper",
            segments=result.get("segments", []),
        )


class OpenAIWhisperProvider(TranscriptionProvider):
    """Uses OpenAI Whisper API (cloud)."""

    async def is_available(self) -> bool:
        return bool(get_settings().OPENAI_API_KEY)

    async def transcribe(self, audio_path: str, language: str | None = None) -> TranscriptionResult:
        from openai import AsyncOpenAI

        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        with open(audio_path, "rb") as f:
            kwargs = {"model": "whisper-1", "file": f, "response_format": "verbose_json"}
            if language:
                kwargs["language"] = language
            result = await client.audio.transcriptions.create(**kwargs)

        return TranscriptionResult(
            text=result.text.strip(),
            language=result.language or "unknown",
            duration_seconds=result.duration or 0.0,
            provider="openai-whisper",
            segments=[],
        )


def get_transcription_provider(provider: str) -> TranscriptionProvider:
    registry = {
        "local": LocalWhisperProvider,
        "openai": OpenAIWhisperProvider,
    }
    cls = registry.get(provider)
    if not cls:
        raise ValueError(f"Unknown transcription provider: {provider}")
    return cls()
