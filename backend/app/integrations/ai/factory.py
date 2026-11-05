import time
import structlog
from app.core.config import settings
from app.integrations.ai.base import AIProvider
from app.integrations.ai.gemini import GeminiProvider
from app.integrations.ai.openai_provider import OpenAIProvider

logger = structlog.get_logger(__name__)

_TRANSIENT_CODES = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "rate limit", "overloaded")


def _is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(code.lower() in msg for code in _TRANSIENT_CODES)


class _FallbackAIProvider(AIProvider):
    """
    Wraps a primary provider and transparently retries extraction on a
    secondary provider if the primary call raises (bad/expired key, rate
    limit, outage). Any other attribute/method access goes straight to the
    primary provider, since extract_structured_data is the only method
    guaranteed by the shared AIProvider interface.

    If both providers return transient 503/429 errors, retries up to 3 times
    with 15-second backoff before giving up.
    """

    _MAX_RETRIES = 3
    _RETRY_DELAY = 15  # seconds

    def __init__(self, primary: AIProvider, secondary: AIProvider | None):
        self._primary = primary
        self._secondary = secondary

    def extract_structured_data(self, *args, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                return self._primary.extract_structured_data(*args, **kwargs)
            except Exception as primary_exc:
                if self._secondary is None:
                    if _is_transient(primary_exc) and attempt < self._MAX_RETRIES:
                        logger.warning(
                            "Primary AI provider transient error, retrying",
                            attempt=attempt,
                            delay=self._RETRY_DELAY,
                            error=str(primary_exc),
                        )
                        time.sleep(self._RETRY_DELAY)
                        last_exc = primary_exc
                        continue
                    raise

                logger.warning(
                    "Primary AI provider extraction failed, retrying with fallback provider",
                    primary=type(self._primary).__name__,
                    fallback=type(self._secondary).__name__,
                    attempt=attempt,
                    error=str(primary_exc),
                )
                try:
                    return self._secondary.extract_structured_data(*args, **kwargs)
                except Exception as secondary_exc:
                    last_exc = secondary_exc
                    if _is_transient(secondary_exc) and attempt < self._MAX_RETRIES:
                        logger.warning(
                            "Fallback AI provider transient error, will retry both",
                            attempt=attempt,
                            delay=self._RETRY_DELAY,
                            error=str(secondary_exc),
                        )
                        time.sleep(self._RETRY_DELAY)
                        continue
                    raise

        raise last_exc  # type: ignore[misc]

    def __getattr__(self, name):
        return getattr(self._primary, name)


def get_ai_provider() -> AIProvider:
    """
    Returns the active AI provider. OpenAI primary when key is present, with
    Gemini as live fallback when GEMINI_API_KEY is also set.
    """
    has_openai = bool((settings.OPENAI_API_KEY or "").strip())
    has_gemini = bool((settings.GEMINI_API_KEY or "").strip())

    if has_openai:
        primary: AIProvider = OpenAIProvider()
        secondary: AIProvider | None = GeminiProvider() if has_gemini else None
    else:
        primary = GeminiProvider()
        secondary = None

    return _FallbackAIProvider(primary, secondary)

