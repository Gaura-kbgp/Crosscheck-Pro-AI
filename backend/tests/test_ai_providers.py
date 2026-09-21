import pytest
from app.core.config import settings
from app.integrations.ai.factory import get_ai_provider
from app.integrations.ai.gemini import GeminiProvider
from app.integrations.ai.openai_provider import OpenAIProvider
from app.schemas.extraction import DesignExtraction


def test_ai_provider_factory_default(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    provider = get_ai_provider()
    assert isinstance(provider, GeminiProvider)


def test_ai_provider_factory_openai(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-fake-key")
    provider = get_ai_provider()
    assert isinstance(provider, OpenAIProvider)
    assert provider.model_name == "gpt-4o"


def test_openai_provider_no_client(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    provider = OpenAIProvider()
    provider.client = None
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        provider.extract_structured_data(
            file_bytes=b"dummy",
            mime_type="text/plain",
            prompt="extract",
            schema=DesignExtraction
        )
