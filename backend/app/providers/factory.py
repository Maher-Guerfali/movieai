from app.core.config import settings
from app.providers.base import LLMProvider, MockProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.openai_provider import OpenAIProvider


def get_provider(prefer: str | None = None) -> LLMProvider:
    """Return the active LLM provider.

    Selection order:
    1. If USE_MOCK_AI is on, always use the deterministic MockProvider.
    2. Use the preferred / default provider when its key is configured.
    3. Fall back to any other provider that has a key.
    4. Fall back to the MockProvider so the app never crashes on a missing key.
    """
    if settings.use_mock_ai:
        return MockProvider()

    name = (prefer or settings.default_llm_provider or "openai").lower()

    if name == "openai" and settings.openai_api_key:
        return OpenAIProvider()
    if name in {"google", "gemini"} and settings.google_api_key:
        return GeminiProvider()

    if settings.openai_api_key:
        return OpenAIProvider()
    if settings.google_api_key:
        return GeminiProvider()

    return MockProvider()
