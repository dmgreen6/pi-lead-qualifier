"""API key validation helpers for setup wizard."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    """Result of API key validation."""
    valid: bool
    message: str
    details: Optional[dict] = None


def validate_airtable_key(api_key: str, base_id: str = "", table_id: str = "") -> ValidationResult:
    """Validate Airtable API key format and optionally test connection.

    Args:
        api_key: Airtable personal access token (pat_...)
        base_id: Optional base ID to test
        table_id: Optional table ID to test

    Returns:
        ValidationResult with status and message
    """
    if not api_key or not api_key.strip():
        return ValidationResult(
            valid=False,
            message="API key is required. Get yours at airtable.com/create/tokens"
        )

    # Check format - should start with pat_ or key
    if not (api_key.startswith("pat_") or api_key.startswith("key")):
        return ValidationResult(
            valid=False,
            message="Invalid key format. Airtable keys start with 'pat_' or 'key'"
        )

    return ValidationResult(
        valid=True,
        message="API key format looks valid. Connection will be tested on first run."
    )


def validate_anthropic_key(api_key: str) -> ValidationResult:
    """Validate Anthropic (Claude) API key format.

    Args:
        api_key: Anthropic API key (sk-ant-...)

    Returns:
        ValidationResult with status and message
    """
    if not api_key or not api_key.strip():
        return ValidationResult(
            valid=False,
            message="API key is required. Get yours at console.anthropic.com"
        )

    # Anthropic keys start with sk-ant-
    if not api_key.startswith("sk-ant-"):
        return ValidationResult(
            valid=False,
            message="Invalid key format. Anthropic keys start with 'sk-ant-'"
        )

    return ValidationResult(
        valid=True,
        message="API key format is valid."
    )


def validate_openai_key(api_key: str) -> ValidationResult:
    """Validate OpenAI API key format.

    Args:
        api_key: OpenAI API key (sk-...)

    Returns:
        ValidationResult with status and message
    """
    if not api_key or not api_key.strip():
        return ValidationResult(
            valid=False,
            message="API key is required. Get yours at platform.openai.com"
        )

    # OpenAI keys start with sk- (but not sk-ant-)
    if not api_key.startswith("sk-") or api_key.startswith("sk-ant-"):
        return ValidationResult(
            valid=False,
            message="Invalid key format. OpenAI keys start with 'sk-' (not 'sk-ant-')"
        )

    return ValidationResult(
        valid=True,
        message="API key format is valid."
    )


def validate_clio_credentials(client_id: str, client_secret: str) -> ValidationResult:
    """Validate Clio OAuth credentials format.

    Args:
        client_id: Clio application client ID
        client_secret: Clio application client secret

    Returns:
        ValidationResult with status and message
    """
    if not client_id or not client_secret:
        return ValidationResult(
            valid=False,
            message="Both Client ID and Client Secret are required."
        )

    # Basic format check
    if len(client_id) < 10 or len(client_secret) < 10:
        return ValidationResult(
            valid=False,
            message="Credentials appear too short. Check your Clio developer settings."
        )

    return ValidationResult(
        valid=True,
        message="Credentials format is valid. OAuth flow will verify on connection."
    )
