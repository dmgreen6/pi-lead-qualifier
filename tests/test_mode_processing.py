"""Tests for mode-aware lead processing."""
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AppConfig, OperationMode


def test_starter_mode_config_flags(monkeypatch):
    """Starter mode sets correct config flags."""
    monkeypatch.setenv("OPERATION_MODE", "starter")
    config = AppConfig.from_env()

    assert config.mode == OperationMode.STARTER
    assert config.clio_enabled is False
    assert config.email_enabled is False


def test_pro_mode_config_flags(monkeypatch):
    """Pro mode enables all integrations."""
    monkeypatch.setenv("OPERATION_MODE", "pro")
    config = AppConfig.from_env()

    assert config.mode == OperationMode.PRO
    assert config.clio_enabled is True
    assert config.email_enabled is True
