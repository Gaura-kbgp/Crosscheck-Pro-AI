from app.core.config import settings
from app.integrations.ai.base import AIProvider
from app.integrations.ai.gemini import GeminiProvider
from app.integrations.ai.openai_provider import OpenAIProvider


def get_ai_provider() -> AIProvider:
    """
    Returns the active AI provider based on configuration.
    Respects AI_PROVIDER explicit choice, else defaults based on available API keys.
    """
    provider_name = (settings.AI_PROVIDER or "").lower().strip()
    
    if provider_name == "gemini":
        return GeminiProvider()
    if provider_name == "openai":
        return OpenAIProvider()
    
    if settings.OPENAI_API_KEY:
        return OpenAIProvider()
    return GeminiProvider()

