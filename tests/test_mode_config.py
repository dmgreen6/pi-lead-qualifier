"""Tests for mode-aware configuration."""
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AppConfig, OperationMode


def test_default_mode_is_starter(monkeypatch):
    """Default operation mode is starter."""
    monkeypatch.delenv("OPERATION_MODE", raising=False)
    config = AppConfig.from_env()
    assert config.mode == OperationMode.STARTER


def test_pro_mode_from_env(monkeypatch):
    """Pro mode can be set via environment."""
    monkeypatch.setenv("OPERATION_MODE", "pro")
    config = AppConfig.from_env()
    assert config.mode == OperationMode.PRO


def test_starter_mode_disables_clio(monkeypatch):
    """Starter mode has Clio disabled."""
    monkeypatch.setenv("OPERATION_MODE", "starter")
    config = AppConfig.from_env()
    assert config.clio_enabled is False


def test_starter_mode_disables_email(monkeypatch):
    """Starter mode has email disabled."""
    monkeypatch.setenv("OPERATION_MODE", "starter")
    config = AppConfig.from_env()
    assert config.email_enabled is False


def test_pro_mode_enables_integrations(monkeypatch):
    """Pro mode enables Clio and email."""
    monkeypatch.setenv("OPERATION_MODE", "pro")
    config = AppConfig.from_env()
    assert config.clio_enabled is True
    assert config.email_enabled is True
