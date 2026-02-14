"""
Pflug Law Lead Qualifier - Two-tier AI-powered lead qualification system.

Uses ChatGPT-4 for initial scoring (Tier-1) and Claude Sonnet for deep analysis (Tier-2).
"""

__version__ = "2.0.0"

from .config import (
    AppConfig,
    AirtableConfig,
    ClioConfig,
    OpenAIConfig,
    ClaudeConfig,
    GoogleDriveConfig,
    ScoringThresholds,
    load_config,
)
from .airtable_client import Lead, AirtableClient, TwoTierScoringUpdate
from .chatgpt_scorer import ChatGPTScorer, ChatGPTScoringResult, Recommendation
from .claude_analyzer import ClaudeAnalyzer, ClaudeAnalysisResult
from .qualifier import TwoTierQualifier, TwoTierResult
from .scoring_log import ScoringLogger

__all__ = [
    # Config
    "AppConfig",
    "AirtableConfig",
    "ClioConfig",
    "OpenAIConfig",
    "ClaudeConfig",
    "GoogleDriveConfig",
    "ScoringThresholds",
    "load_config",
    # Clients
    "Lead",
    "AirtableClient",
    "TwoTierScoringUpdate",
    # Scoring
    "ChatGPTScorer",
    "ChatGPTScoringResult",
    "Recommendation",
    "ClaudeAnalyzer",
    "ClaudeAnalysisResult",
    "TwoTierQualifier",
    "TwoTierResult",
    "ScoringLogger",
]
