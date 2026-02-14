"""State data loading for PI Lead Qualifier."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class StateData:
    """State-specific configuration data."""
    name: str
    abbreviation: str
    sol_years: int
    sol_notes: str
    counties: list[str]
    major_metros: dict[str, list[str]]
    default_preferred_counties: list[str]


def _get_data_dir() -> Path:
    """Get the data/states directory path."""
    return Path(__file__).parent.parent / "data" / "states"


def load_state(abbreviation: str) -> StateData:
    """Load state data from JSON file.

    Args:
        abbreviation: Two-letter state code (e.g., "SC", "CA")

    Returns:
        StateData object with state configuration

    Raises:
        FileNotFoundError: If state file doesn't exist
    """
    abbr = abbreviation.upper()
    state_file = _get_data_dir() / f"{abbr}.json"

    if not state_file.exists():
        raise FileNotFoundError(f"State data not found: {abbr}")

    with open(state_file) as f:
        data = json.load(f)

    return StateData(
        name=data["name"],
        abbreviation=data["abbreviation"],
        sol_years=data["sol_years"],
        sol_notes=data["sol_notes"],
        counties=data["counties"],
        major_metros=data.get("major_metros", {}),
        default_preferred_counties=data.get("default_preferred_counties", []),
    )


def get_all_states() -> list[str]:
    """Get list of all available state abbreviations."""
    data_dir = _get_data_dir()
    if not data_dir.exists():
        return []
    return sorted([f.stem for f in data_dir.glob("*.json")])
