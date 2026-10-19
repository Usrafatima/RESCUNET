"""
RescuNet Agent configuration.

Loads environment variables from .env and provides configuration
for model providers. Designed so an additional provider can be
added later without rewriting the agent architecture.
"""

import os
from dataclasses import dataclass, field

from pathlib import Path

from dotenv import load_dotenv

# Ensure backend/.env takes precedence over any stale process environment variables
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH, override=True)
else:
    load_dotenv(override=True)


def _get_configured_api_key() -> str:
    """Retrieve the configured API key, checking GOOGLE_API_KEY then GEMINI_API_KEY."""
    return (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()


# Synchronize environment variables so all underlying SDKs (google-genai, strands)
# consistently select the intended API key from backend/.env
_api_key = _get_configured_api_key()
if _api_key:
    os.environ["GOOGLE_API_KEY"] = _api_key
    os.environ["GEMINI_API_KEY"] = _api_key


@dataclass
class AgentConfig:
    """Configuration for the RescuNet agent."""

    # Google Gemini configuration
    google_api_key: str = field(
        default_factory=_get_configured_api_key
    )
    gemini_model_id: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
    )
    gemini_temperature: float = 0.3
    gemini_max_output_tokens: int = 2048

    # Backend URL for tool calls
    backend_url: str = field(
        default_factory=lambda: os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    )

    # Provider selection (supports additional model providers)
    model_provider: str = field(
        default_factory=lambda: os.getenv("MODEL_PROVIDER", "gemini")
    )

    @property
    def has_api_key(self) -> bool:
        """Check if an API key is configured."""
        return bool(self.google_api_key and self.google_api_key != "your-google-api-key-here")


# Singleton config
config = AgentConfig()
