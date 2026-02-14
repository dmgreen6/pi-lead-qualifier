"""Tests for API key validators."""
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from setup.validators import (
    validate_airtable_key,
    validate_anthropic_key,
    validate_openai_key,
    validate_clio_credentials,
    ValidationResult,
)


def test_validation_result_success():
    """ValidationResult represents success."""
    result = ValidationResult(valid=True, message="Connected successfully")
    assert result.valid is True
    assert "success" in result.message.lower()


def test_validation_result_failure():
    """ValidationResult represents failure."""
    result = ValidationResult(valid=False, message="Invalid API key")
    assert result.valid is False


def test_airtable_empty_key_fails():
    """Empty Airtable key fails validation."""
    result = validate_airtable_key("")
    assert result.valid is False
    assert "required" in result.message.lower() or "empty" in result.message.lower()


def test_anthropic_invalid_format():
    """Invalid Anthropic key format fails."""
    result = validate_anthropic_key("not-a-real-key")
    assert result.valid is False


def test_openai_invalid_format():
    """Invalid OpenAI key format fails."""
    result = validate_openai_key("not-a-real-key")
    assert result.valid is False


def test_airtable_valid_key():
    """Valid Airtable PAT key is accepted."""
    result = validate_airtable_key("pat_abcdefg123456")
    assert result.valid is True


def test_airtable_invalid_prefix():
    """Airtable key without underscore after 'pat' fails."""
    result = validate_airtable_key("patently_wrong")
    assert result.valid is False


def test_anthropic_valid_key():
    """Valid Anthropic key is accepted."""
    result = validate_anthropic_key("sk-ant-abc123xyz")
    assert result.valid is True


def test_openai_valid_key():
    """Valid OpenAI key is accepted."""
    result = validate_openai_key("sk-proj-abc123xyz")
    assert result.valid is True


def test_clio_empty_credentials_fails():
    """Empty Clio credentials fail."""
    result = validate_clio_credentials("", "")
    assert result.valid is False


def test_clio_valid_credentials():
    """Valid Clio credentials are accepted."""
    result = validate_clio_credentials("client_id_12345", "client_secret_12345")
    assert result.valid is True


def test_clio_short_credentials_fails():
    """Clio credentials that are too short fail."""
    result = validate_clio_credentials("short", "alsoshort")
    assert result.valid is False
