import pytest
import io
import wave
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.schemas import TranscriptionResult, SummaryResult, Insight


def make_wav_bytes() -> bytes:
    """Generate minimal WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)
    return buf.getvalue()


MOCK_TRANSCRIPTION = TranscriptionResult(
    text="Revenue increased by 15% this quarter due to strong product sales.",
    language="en",
    duration_seconds=12.5,
    provider="local-whisper",
)

MOCK_ANALYSIS = SummaryResult(
    short_summary="Revenue grew 15% from product sales.",
    detailed_summary="The quarter saw strong revenue performance driven by product sales.",
    key_points=["Revenue up 15%", "Product sales strong"],
    insights=[Insight(category="Financial", content="15% growth is healthy", confidence="high")],
    action_items=["Review pricing strategy"],
    sentiment="positive",
    topics=["revenue", "sales"],
    word_count=12,
    provider="ollama",
    model="llama3.2",
)


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
class TestAnalyzeEndpoint:
    async def test_full_pipeline_success(self, client):
        wav_bytes = make_wav_bytes()

        with patch("app.services.transcription.LocalWhisperProvider.transcribe",
                   new_callable=AsyncMock, return_value=MOCK_TRANSCRIPTION), \
             patch("app.services.llm.ollama_provider.OllamaProvider.analyze",
                   new_callable=AsyncMock, return_value=MOCK_ANALYSIS):

            resp = await client.post(
                "/api/v1/analyze",
                files={"file": ("test.wav", wav_bytes, "audio/wav")},
                data={
                    "transcription_provider": "local",
                    "llm_provider": "ollama",
                    "analysis_depth": "standard",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["transcription"]["text"] == MOCK_TRANSCRIPTION.text
        assert data["analysis"]["sentiment"] == "positive"
        assert "job_id" in data
        assert data["processing_time_ms"] is not None

    async def test_unsupported_format_returns_400(self, client):
        resp = await client.post(
            "/api/v1/analyze",
            files={"file": ("test.pdf", b"fake-pdf-content", "application/pdf")},
            data={"transcription_provider": "local", "llm_provider": "ollama"},
        )
        assert resp.status_code == 400
        assert "Unsupported format" in resp.json()["detail"]

    async def test_failed_transcription_returns_failed_status(self, client):
        wav_bytes = make_wav_bytes()

        with patch("app.services.transcription.LocalWhisperProvider.transcribe",
                   new_callable=AsyncMock, side_effect=RuntimeError("Whisper model error")):
            resp = await client.post(
                "/api/v1/analyze",
                files={"file": ("test.wav", wav_bytes, "audio/wav")},
                data={"transcription_provider": "local", "llm_provider": "ollama"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert "Whisper model error" in data["error"]

    async def test_provider_switching_openai(self, client):
        """Verify that specifying openai provider routes to OpenAI."""
        wav_bytes = make_wav_bytes()

        with patch("app.services.transcription.OpenAIWhisperProvider.transcribe",
                   new_callable=AsyncMock, return_value=MOCK_TRANSCRIPTION) as mock_asr, \
             patch("app.services.llm.openai_provider.OpenAIProvider.analyze",
                   new_callable=AsyncMock, return_value=MOCK_ANALYSIS) as mock_llm:

            resp = await client.post(
                "/api/v1/analyze",
                files={"file": ("test.wav", wav_bytes, "audio/wav")},
                data={
                    "transcription_provider": "openai",
                    "llm_provider": "openai",
                    "analysis_depth": "quick",
                },
            )

        assert resp.status_code == 200
        mock_asr.assert_called_once()
        mock_llm.assert_called_once()


@pytest.mark.asyncio
class TestTranscribeOnlyEndpoint:
    async def test_transcribe_only_returns_no_analysis(self, client):
        wav_bytes = make_wav_bytes()

        with patch("app.services.transcription.LocalWhisperProvider.transcribe",
                   new_callable=AsyncMock, return_value=MOCK_TRANSCRIPTION):
            resp = await client.post(
                "/api/v1/transcribe-only",
                files={"file": ("test.wav", wav_bytes, "audio/wav")},
                data={"provider": "local"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["transcription"] is not None
        assert data["analysis"] is None


@pytest.mark.asyncio
class TestStatusEndpoint:
    async def test_status_returns_all_providers(self, client):
        with patch("app.services.llm.ollama_provider.OllamaProvider.is_available",
                   new_callable=AsyncMock, return_value=True), \
             patch("app.services.llm.openai_provider.OpenAIProvider.is_available",
                   new_callable=AsyncMock, return_value=False), \
             patch("app.services.llm.anthropic_provider.AnthropicProvider.is_available",
                   new_callable=AsyncMock, return_value=False), \
             patch("app.services.llm.groq_provider.GroqProvider.is_available",
                   new_callable=AsyncMock, return_value=False), \
             patch("app.services.transcription.LocalWhisperProvider.is_available",
                   new_callable=AsyncMock, return_value=True), \
             patch("app.services.transcription.OpenAIWhisperProvider.is_available",
                   new_callable=AsyncMock, return_value=False):

            resp = await client.get("/api/v1/status")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["llm_providers"]) == 4
        assert len(data["transcription_providers"]) == 2
        ollama = next(p for p in data["llm_providers"] if p["provider"] == "ollama")
        assert ollama["available"] is True
