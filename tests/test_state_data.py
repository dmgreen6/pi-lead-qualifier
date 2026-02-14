"""Tests for state data loading."""
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.state_data import load_state, get_all_states, StateData


def test_load_sc_state():
    """SC state data loads correctly."""
    state = load_state("SC")
    assert state.name == "South Carolina"
    assert state.abbreviation == "SC"
    assert state.sol_years == 3
    assert "Charleston" in state.counties
    assert len(state.counties) == 46


def test_load_state_case_insensitive():
    """State loading works with lowercase."""
    state = load_state("sc")
    assert state.abbreviation == "SC"


def test_load_invalid_state():
    """Loading invalid state raises error."""
    with pytest.raises(FileNotFoundError):
        load_state("XX")


def test_get_all_states():
    """Returns list of all available states."""
    states = get_all_states()
    assert "SC" in states
    assert isinstance(states, list)


def test_state_data_default_counties():
    """Default preferred counties are available."""
    state = load_state("SC")
    assert len(state.default_preferred_counties) > 0
    assert "Charleston" in state.default_preferred_counties


def test_both_states_available():
    """Both SC and WA states have data files."""
    states = get_all_states()
    assert len(states) == 2
    assert "SC" in states
    assert "WA" in states


def test_load_wa_state():
    """WA state data loads correctly."""
    state = load_state("WA")
    assert state.name == "Washington"
    assert state.abbreviation == "WA"
    assert state.sol_years == 3
    assert "King" in state.counties
    assert len(state.counties) == 39
