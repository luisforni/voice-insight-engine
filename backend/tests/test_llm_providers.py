import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm import get_llm_provider, all_providers
from app.services.llm.base import LLMProvider
from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.groq_provider import GroqProvider
from app.models.schemas import TranscriptionResult


SAMPLE_JSON = json.dumps({
    "short_summary": "Test summary.",
    "detailed_summary": "Detailed test summary paragraph.",
    "key_points": ["Point 1", "Point 2"],
    "insights": [{"category": "Test", "content": "Insight content", "confidence": "high"}],
    "action_items": ["Action 1"],
    "sentiment": "positive",
    "topics": ["test", "demo"],
    "word_count": 10,
})


@pytest.fixture
def transcription():
    return TranscriptionResult(
        text="This is a test transcription.",
        language="en",
        duration_seconds=10.0,
        provider="local-whisper",
    )


class TestProviderFactory:
    def test_get_valid_providers(self):
        for name in ["ollama", "openai", "anthropic", "groq"]:
            provider = get_llm_provider(name)
            assert isinstance(provider, LLMProvider)

    def test_get_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider("invalid_provider")

    def test_all_providers_returns_all(self):
        providers = all_providers()
        names = {p.provider_name for p in providers}
        assert names == {"ollama", "openai", "anthropic", "groq"}


class TestOllamaProvider:
    @pytest.mark.asyncio
    async def test_is_available_true(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                get=AsyncMock(return_value=mock_response)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            provider = OllamaProvider()
            result = await provider.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_available_false_on_connection_error(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            provider = OllamaProvider()
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_analyze_returns_summary(self, transcription):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": SAMPLE_JSON}}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_response)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            provider = OllamaProvider()
            result = await provider.analyze(transcription)

        assert result.short_summary == "Test summary."
        assert result.provider == "ollama"
        assert len(result.key_points) == 2
        assert result.sentiment == "positive"

    @pytest.mark.asyncio
    async def test_list_models(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llama3.2"}, {"name": "mistral"}]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                get=AsyncMock(return_value=mock_response)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            provider = OllamaProvider()
            models = await provider.list_models()

        assert "llama3.2" in models
        assert "mistral" in models


class TestOpenAIProvider:
    @pytest.mark.asyncio
    async def test_is_available_with_key(self):
        with patch.object(OpenAIProvider, "__init__", lambda self: None):
            provider = OpenAIProvider()
            provider._settings = MagicMock(OPENAI_API_KEY="sk-test123", OPENAI_MODEL="gpt-4o-mini")
            result = await provider.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_not_available_without_key(self):
        with patch.object(OpenAIProvider, "__init__", lambda self: None):
            provider = OpenAIProvider()
            provider._settings = MagicMock(OPENAI_API_KEY="", OPENAI_MODEL="gpt-4o-mini")
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_analyze_calls_openai(self, transcription):
        mock_message = MagicMock()
        mock_message.content = SAMPLE_JSON
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create = AsyncMock(return_value=mock_completion)
            with patch.object(OpenAIProvider, "__init__", lambda self: None):
                provider = OpenAIProvider()
                provider._settings = MagicMock(OPENAI_API_KEY="sk-test", OPENAI_MODEL="gpt-4o-mini")
                result = await provider.analyze(transcription)

        assert result.provider == "openai"
        assert result.model == "gpt-4o-mini"


class TestAnthropicProvider:
    @pytest.mark.asyncio
    async def test_analyze_calls_anthropic(self, transcription):
        mock_content = MagicMock()
        mock_content.text = SAMPLE_JSON
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        with patch("anthropic.AsyncAnthropic") as mock_anthropic:
            mock_anthropic.return_value.messages.create = AsyncMock(return_value=mock_response)
            with patch.object(AnthropicProvider, "__init__", lambda self: None):
                provider = AnthropicProvider()
                provider._settings = MagicMock(
                    ANTHROPIC_API_KEY="test-key",
                    ANTHROPIC_MODEL="claude-3-5-haiku-20241022"
                )
                result = await provider.analyze(transcription)

        assert result.provider == "anthropic"
        assert result.insights[0].category == "Test"


class TestJsonParsing:
    def test_parse_with_markdown_fences(self, transcription):
        provider = OllamaProvider()
        raw = f"```json\n{SAMPLE_JSON}\n```"

        with patch("httpx.AsyncClient"):
            result = provider._parse_analysis_json(raw, "test", "test-model")

        assert result.short_summary == "Test summary."

    def test_parse_invalid_json_raises(self):
        provider = OllamaProvider()
        with pytest.raises(Exception):
            provider._parse_analysis_json("not json at all", "test", "model")
