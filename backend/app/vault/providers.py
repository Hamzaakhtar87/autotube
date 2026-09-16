"""The seven BYOK providers and the credential shape each one expects."""
from enum import Enum


class Provider(str, Enum):
    anthropic = "anthropic"
    openai = "openai"
    groq = "groq"
    gemini = "gemini"
    kling = "kling"
    veo = "veo"
    seedance = "seedance"


PROVIDER_LABELS = {
    Provider.anthropic: "Anthropic (Claude)",
    Provider.openai: "OpenAI",
    Provider.groq: "Groq",
    Provider.gemini: "Google Gemini",
    Provider.kling: "Kling",
    Provider.veo: "Google Veo (via Gemini API key)",
    Provider.seedance: "Seedance (BytePlus ModelArk)",
}

# Kling signs a short-lived JWT from an access key + secret key pair; everyone
# else is a single bearer/API key.
SINGLE_KEY_FIELDS = ("api_key",)
KLING_FIELDS = ("access_key", "secret_key")

MAX_CREDENTIAL_LENGTH = 512


def credential_fields(provider: Provider) -> tuple[str, ...]:
    return KLING_FIELDS if provider is Provider.kling else SINGLE_KEY_FIELDS
