import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.models.schemas import TranscriptionResult, SummaryResult, Insight


@pytest.fixture
def mock_transcription() -> TranscriptionResult:
    return TranscriptionResult(
        text="The quarterly revenue grew by 23% exceeding all forecasts. "
             "The team should focus on customer retention in Q4.",
        language="en",
        duration_seconds=45.2,
        provider="local-whisper",
        segments=[],
    )


@pytest.fixture
def mock_analysis() -> SummaryResult:
    return SummaryResult(
        short_summary="Revenue grew 23% exceeding forecasts; Q4 focus on retention.",
        detailed_summary="The quarterly report shows strong revenue growth of 23%, "
                         "surpassing all initial forecasts. The leadership recommends "
                         "focusing efforts on customer retention for Q4.",
        key_points=[
            "Revenue grew by 23% this quarter",
            "Results exceeded all forecasts",
            "Q4 strategy should prioritize customer retention",
        ],
        insights=[
            Insight(category="Financial", content="23% growth indicates strong market performance", confidence="high"),
            Insight(category="Strategy", content="Retention focus suggests growth plateau awareness", confidence="medium"),
        ],
        action_items=["Define Q4 retention KPIs", "Prepare retention campaign brief"],
        sentiment="positive",
        topics=["revenue", "forecasts", "retention", "Q4"],
        word_count=34,
        provider="ollama",
        model="llama3.2",
    )


@pytest.fixture
def audio_file(tmp_path):
    """Creates a minimal valid WAV file for testing."""
    import struct
    import wave

    path = tmp_path / "test.wav"
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 1 second of silence
        wf.writeframes(b"\x00\x00" * 16000)
    return path


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
