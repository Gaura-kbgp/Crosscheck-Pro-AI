import pytest
from app.core.config import settings
from app.integrations.ai.factory import get_ai_provider, _FallbackAIProvider
from app.integrations.ai.gemini import GeminiProvider
from app.integrations.ai.openai_provider import OpenAIProvider
from app.schemas.extraction import DesignExtraction


def test_ai_provider_factory_default(monkeypatch):
    # No OpenAI key configured -> falls back to Gemini as the sole provider.
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    provider = get_ai_provider()
    assert isinstance(provider, _FallbackAIProvider)
    assert isinstance(provider._primary, GeminiProvider)
    assert provider._secondary is None


def test_ai_provider_factory_openai(monkeypatch):
    # OpenAI primary + Gemini fallback when both keys are present.
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-fake-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-gemini-key")
    provider = get_ai_provider()
    assert isinstance(provider, _FallbackAIProvider)
    assert isinstance(provider._primary, OpenAIProvider)
    assert provider._primary.model_name == "gpt-4o"
    assert isinstance(provider._secondary, GeminiProvider)


def test_ai_provider_factory_openai_no_gemini(monkeypatch):
    # OpenAI only when no Gemini key — secondary stays None.
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-fake-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    provider = get_ai_provider()
    assert isinstance(provider._primary, OpenAIProvider)
    assert provider._secondary is None


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
