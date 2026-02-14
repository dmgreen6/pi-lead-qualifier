"""
Configuration management for Pflug Law Lead Qualifier.
Loads settings from environment variables and provides defaults.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path


class OperationMode(Enum):
    """Operation mode for the qualifier."""
    STARTER = "starter"
    PRO = "pro"


@dataclass
class AirtableConfig:
    """Airtable API configuration."""
    api_key: str = ""
    base_id: str = ""
    table_id: str = ""
    scoring_log_table_id: str = ""  # Will be set after creating the table

    @classmethod
    def from_env(cls) -> "AirtableConfig":
        return cls(
            api_key=os.getenv("AIRTABLE_API_KEY", ""),
            base_id=os.getenv("AIRTABLE_BASE_ID", ""),
            table_id=os.getenv("AIRTABLE_TABLE_ID", ""),
            scoring_log_table_id=os.getenv("AIRTABLE_SCORING_LOG_TABLE_ID", ""),
        )


@dataclass
class ClioConfig:
    """Clio API configuration."""
    client_id: str = ""
    client_secret: str = ""
    access_token: str = ""
    refresh_token: str = ""
    api_base_url: str = "https://app.clio.com/api/v4"
    responsible_attorney_name: str = ""
    default_matter_group_id: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ClioConfig":
        return cls(
            client_id=os.getenv("CLIO_CLIENT_ID", ""),
            client_secret=os.getenv("CLIO_CLIENT_SECRET", ""),
            access_token=os.getenv("CLIO_ACCESS_TOKEN", ""),
            refresh_token=os.getenv("CLIO_REFRESH_TOKEN", ""),
            api_base_url=os.getenv("CLIO_API_BASE_URL", "https://app.clio.com/api/v4"),
            responsible_attorney_name=os.getenv("CLIO_RESPONSIBLE_ATTORNEY", ""),
            default_matter_group_id=os.getenv("CLIO_MATTER_GROUP_ID"),
        )


@dataclass
class OpenAIConfig:
    """OpenAI ChatGPT API configuration for Tier-1 scoring."""
    api_key: str = ""
    model: str = "gpt-4-turbo-preview"
    max_tokens: int = 1024

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "1024")),
        )


@dataclass
class ClaudeConfig:
    """Anthropic Claude API configuration for Tier-2 deep analysis."""
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 2048

    @classmethod
    def from_env(cls) -> "ClaudeConfig":
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "2048")),
        )


@dataclass
class GoogleDriveConfig:
    """Google Drive API configuration for case comparison search."""
    credentials_file: str = "google_drive_credentials.json"
    folder_id: str = ""  # Empty = search all files

    @classmethod
    def from_env(cls) -> "GoogleDriveConfig":
        return cls(
            credentials_file=os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE", "google_drive_credentials.json"),
            folder_id=os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""),
        )


@dataclass
class ScoringThresholds:
    """Two-tier AI scoring thresholds."""
    fast_track: int = 75      # Score >= 75: Auto-accept
    claude_review: int = 50   # Score 50-74: Claude deep analysis
    need_info: int = 25       # Score 25-49 with gaps: Need more info
    # Score < 25 or < 50 without gaps: Decline

    @classmethod
    def from_env(cls) -> "ScoringThresholds":
        return cls(
            fast_track=int(os.getenv("FAST_TRACK_THRESHOLD", "75")),
            claude_review=int(os.getenv("CLAUDE_REVIEW_THRESHOLD", "50")),
            need_info=int(os.getenv("NEED_INFO_THRESHOLD", "25")),
        )


@dataclass
class EmailConfig:
    """Email configuration for Gmail API."""
    sender_email: str = ""
    intake_email: str = ""
    notification_email: str = ""
    credentials_file: str = "gmail_credentials.json"
    token_file: str = "gmail_token.json"

    @classmethod
    def from_env(cls) -> "EmailConfig":
        return cls(
            sender_email=os.getenv("GMAIL_SENDER_EMAIL", ""),
            intake_email=os.getenv("GMAIL_INTAKE_EMAIL", ""),
            notification_email=os.getenv("GMAIL_NOTIFICATION_EMAIL", ""),
            credentials_file=os.getenv("GMAIL_CREDENTIALS_FILE", "gmail_credentials.json"),
            token_file=os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json"),
        )


@dataclass
class QualificationConfig:
    """Lead qualification scoring configuration."""
    # Point values
    medical_treatment_points: int = 3
    clear_liability_points: int = 3
    identified_insurance_points: int = 2
    sol_buffer_points: int = 1
    serious_injury_points: int = 2
    tri_county_bonus: int = 5

    # Tier thresholds
    tier1_threshold: int = 11  # Auto-accept
    tier2_threshold: int = 7   # Review needed
    # Below tier2 = auto-decline

    # SOL settings (configurable per state)
    sol_years: int = 3
    min_sol_months_remaining: int = 18

    # State configuration
    state: str = "SC"

    # Preferred counties (configurable - bonus points for leads in these)
    preferred_counties: list = field(default_factory=list)

    # All accepted counties (configurable - for in-state verification)
    accepted_counties: list = field(default_factory=list)

    # Keywords for safety rules
    disputed_liability_keywords: list = field(default_factory=lambda: [
        "disputed", "my client may be at fault", "unclear", "comparative",
        "contributory", "both parties", "shared fault", "partial fault"
    ])

    insufficient_treatment_keywords: list = field(default_factory=lambda: [
        "none yet", "no treatment", "hasn't seen doctor", "refused treatment",
        "self-treating", "home remedies only"
    ])

    # Serious injury indicators
    serious_injury_keywords: list = field(default_factory=lambda: [
        "fracture", "broken", "surgery", "surgical", "operation", "permanent",
        "disability", "amputation", "traumatic brain", "tbi", "spinal cord",
        "paralysis", "herniated", "torn", "rupture", "internal bleeding"
    ])

    # Clear liability indicators
    clear_liability_keywords: list = field(default_factory=lambda: [
        "rear-end", "rear end", "rearend", "ran red light", "ran stop sign",
        "ran the light", "ran the sign", "speeding", "dui", "dwi", "drunk",
        "intoxicated", "bac", "failed sobriety", "citation issued",
        "ticket issued", "at fault", "100% fault", "admitted fault"
    ])

    # Medical treatment indicators
    valid_treatment_keywords: list = field(default_factory=lambda: [
        "emergency room", "er visit", "emergency department", "ed visit",
        "hospital", "orthopedic", "orthopaedic", "surgeon", "surgery",
        "operation", "physical therapy", "pt", "chiropractor", "mri",
        "ct scan", "x-ray", "xray", "specialist", "neurologist", "pain management"
    ])

    @classmethod
    def from_env(cls) -> "QualificationConfig":
        # Parse comma-separated county lists from environment
        preferred = os.getenv("PREFERRED_COUNTIES", "")
        accepted = os.getenv("ACCEPTED_COUNTIES", "")

        preferred_list = [c.strip().lower() for c in preferred.split(",") if c.strip()]
        accepted_list = [c.strip().lower() for c in accepted.split(",") if c.strip()]

        return cls(
            medical_treatment_points=int(os.getenv("POINTS_MEDICAL_TREATMENT", "3")),
            clear_liability_points=int(os.getenv("POINTS_CLEAR_LIABILITY", "3")),
            identified_insurance_points=int(os.getenv("POINTS_INSURANCE", "2")),
            sol_buffer_points=int(os.getenv("POINTS_SOL_BUFFER", "1")),
            serious_injury_points=int(os.getenv("POINTS_SERIOUS_INJURY", "2")),
            tri_county_bonus=int(os.getenv("POINTS_TRI_COUNTY", "5")),
            tier1_threshold=int(os.getenv("TIER1_THRESHOLD", "11")),
            tier2_threshold=int(os.getenv("TIER2_THRESHOLD", "7")),
            sol_years=int(os.getenv("SOL_YEARS", "3")),
            min_sol_months_remaining=int(os.getenv("MIN_SOL_MONTHS", "18")),
            state=os.getenv("STATE", ""),
            preferred_counties=preferred_list,
            accepted_counties=accepted_list,
        )


@dataclass
class AppConfig:
    """Main application configuration."""
    airtable: AirtableConfig
    clio: ClioConfig
    openai: OpenAIConfig
    claude: ClaudeConfig
    google_drive: GoogleDriveConfig
    email: EmailConfig
    qualification: QualificationConfig
    scoring_thresholds: ScoringThresholds

    # Application settings
    poll_interval_seconds: int = 300  # 5 minutes
    max_retries: int = 3
    retry_delay_seconds: int = 30
    log_dir: str = "/var/log/pi-qualifier"
    dashboard_port: int = 8080
    dashboard_host: str = "127.0.0.1"
    debug_mode: bool = False

    # Operation mode
    mode: OperationMode = OperationMode.STARTER
    clio_enabled: bool = False
    email_enabled: bool = False

    @classmethod
    def from_env(cls) -> "AppConfig":
        # Determine operation mode
        mode_str = os.getenv("OPERATION_MODE", "starter").lower()
        mode = OperationMode.PRO if mode_str == "pro" else OperationMode.STARTER

        # Feature flags based on mode
        clio_enabled = mode == OperationMode.PRO
        email_enabled = mode == OperationMode.PRO

        return cls(
            airtable=AirtableConfig.from_env(),
            clio=ClioConfig.from_env(),
            openai=OpenAIConfig.from_env(),
            claude=ClaudeConfig.from_env(),
            google_drive=GoogleDriveConfig.from_env(),
            email=EmailConfig.from_env(),
            qualification=QualificationConfig.from_env(),
            scoring_thresholds=ScoringThresholds.from_env(),
            poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_delay_seconds=int(os.getenv("RETRY_DELAY_SECONDS", "30")),
            log_dir=os.getenv("LOG_DIR", "/var/log/pi-qualifier"),
            dashboard_port=int(os.getenv("DASHBOARD_PORT", "8080")),
            dashboard_host=os.getenv("DASHBOARD_HOST", "127.0.0.1"),
            debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
            mode=mode,
            clio_enabled=clio_enabled,
            email_enabled=email_enabled,
        )

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.airtable.api_key:
            errors.append("AIRTABLE_API_KEY is required")
        if not self.openai.api_key:
            errors.append("OPENAI_API_KEY is required for Tier-1 scoring")
        if not self.claude.api_key:
            errors.append("ANTHROPIC_API_KEY is required for Tier-2 analysis")

        return errors


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    # Try to load .env file if it exists
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"\''))

    return AppConfig.from_env()
