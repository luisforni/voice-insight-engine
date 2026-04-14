from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Voice Insight Engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Transcription
    WHISPER_MODEL: Literal["tiny", "base", "small", "medium", "large"] = "base"
    WHISPER_DEVICE: Literal["cpu", "cuda"] = "cpu"

    # Default providers
    DEFAULT_TRANSCRIPTION_PROVIDER: Literal["local", "openai"] = "local"
    DEFAULT_LLM_PROVIDER: Literal["ollama", "openai", "anthropic", "groq"] = "ollama"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # File upload
    MAX_FILE_SIZE_MB: int = 50
    UPLOAD_DIR: str = "/tmp/voice_insight_uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
