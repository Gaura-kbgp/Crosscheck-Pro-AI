import structlog
from app.core.config import settings
from app.integrations.ai.base import AIProvider
from app.integrations.ai.gemini import GeminiProvider
from app.integrations.ai.openai_provider import OpenAIProvider

logger = structlog.get_logger(__name__)


class _FallbackAIProvider(AIProvider):
    """
    Wraps a primary provider and transparently retries extraction on a
    secondary provider if the primary call raises (bad/expired key, rate
    limit, outage). Any other attribute/method access goes straight to the
    primary provider, since extract_structured_data is the only method
    guaranteed by the shared AIProvider interface.
    """

    def __init__(self, primary: AIProvider, secondary: AIProvider | None):
        self._primary = primary
        self._secondary = secondary

    def extract_structured_data(self, *args, **kwargs):
        try:
            return self._primary.extract_structured_data(*args, **kwargs)
        except Exception as e:
            if self._secondary is None:
                raise
            logger.warning(
                "Primary AI provider extraction failed, retrying with fallback provider",
                primary=type(self._primary).__name__,
                fallback=type(self._secondary).__name__,
                error=str(e),
            )
            return self._secondary.extract_structured_data(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._primary, name)


def get_ai_provider() -> AIProvider:
    """
    Returns the active AI provider based on configuration.
    Respects AI_PROVIDER explicit choice, else defaults based on available API keys.
    If a Gemini key is configured and it isn't already the primary, extraction
    calls automatically fall back to Gemini when the primary provider fails.
    """
    provider_name = (settings.AI_PROVIDER or "").lower().strip()

    if provider_name == "gemini":
        primary: AIProvider = GeminiProvider()
    elif provider_name == "openai":
        primary = OpenAIProvider()
    elif settings.OPENAI_API_KEY:
        primary = OpenAIProvider()
    else:
        primary = GeminiProvider()

    secondary: AIProvider | None = None
    if not isinstance(primary, GeminiProvider) and settings.GEMINI_API_KEY:
        secondary = GeminiProvider()

    if secondary is None:
        return primary
    return _FallbackAIProvider(primary, secondary)

