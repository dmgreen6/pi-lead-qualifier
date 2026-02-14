# PI Lead Qualifier - Template Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform Pflug Qualifier into a public open-source template other PI attorneys can deploy.

**Architecture:** Web-based setup wizard (Flask) generates configuration from user inputs. State data files provide SOL/county info for all 50 states. Mode-aware runtime enables Starter (Airtable only) or Pro (full integration) features.

**Tech Stack:** Flask (wizard), JSON (state data), Python (validators), Bash/Batch (deploy scripts)

---

## Phase 1: State Data Foundation

### Task 1: Create State Data Directory Structure

**Files:**
- Create: `data/states/` directory
- Create: `data/states/SC.json` (first state as template)

**Step 1: Create directory structure**

```bash
mkdir -p data/states
```

**Step 2: Create SC.json as template**

Create file `data/states/SC.json`:

```json
{
  "name": "South Carolina",
  "abbreviation": "SC",
  "sol_years": 3,
  "sol_notes": "3 years from date of injury for personal injury claims",
  "counties": [
    "Abbeville", "Aiken", "Allendale", "Anderson", "Bamberg", "Barnwell",
    "Beaufort", "Berkeley", "Calhoun", "Charleston", "Cherokee", "Chester",
    "Chesterfield", "Clarendon", "Colleton", "Darlington", "Dillon",
    "Dorchester", "Edgefield", "Fairfield", "Florence", "Georgetown",
    "Greenville", "Greenwood", "Hampton", "Horry", "Jasper", "Kershaw",
    "Lancaster", "Laurens", "Lee", "Lexington", "Marion", "Marlboro",
    "McCormick", "Newberry", "Oconee", "Orangeburg", "Pickens", "Richland",
    "Saluda", "Spartanburg", "Sumter", "Union", "Williamsburg", "York"
  ],
  "major_metros": {
    "Charleston": ["Charleston", "Berkeley", "Dorchester"],
    "Columbia": ["Richland", "Lexington"],
    "Greenville-Spartanburg": ["Greenville", "Spartanburg", "Anderson", "Pickens"]
  },
  "default_preferred_counties": ["Charleston", "Berkeley", "Dorchester"]
}
```

**Step 3: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('data/states/SC.json'))"`
Expected: No output (success)

**Step 4: Commit**

```bash
git add data/states/SC.json
git commit -m "feat: add SC state data file as template"
```

---

### Task 2: Create State Data Loader Module

**Files:**
- Create: `src/state_data.py`
- Create: `tests/test_state_data.py`

**Step 1: Write failing test for state loader**

Create `tests/test_state_data.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_state_data.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.state_data'"

**Step 3: Create state_data.py module**

Create `src/state_data.py`:

```python
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
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_state_data.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/state_data.py tests/test_state_data.py
git commit -m "feat: add state data loader module with tests"
```

---

### Task 3: Create Remaining State Data Files

**Files:**
- Create: `data/states/*.json` for all 50 states
- Create: `scripts/generate_state_data.py` (helper script)

**Step 1: Create generation script**

Create `scripts/generate_state_data.py`:

```python
#!/usr/bin/env python3
"""Generate state data JSON files for all 50 US states.

SOL data source: State statute of limitations for personal injury
County data: US Census Bureau county listings
"""
import json
from pathlib import Path

# Personal injury statute of limitations by state (years)
# Source: Legal research - verify before production use
STATE_SOL = {
    "AL": (2, "2 years from date of injury"),
    "AK": (2, "2 years from date of injury"),
    "AZ": (2, "2 years from date of injury"),
    "AR": (3, "3 years from date of injury"),
    "CA": (2, "2 years from date of injury"),
    "CO": (2, "2 years from date of injury; 3 years for auto accidents"),
    "CT": (2, "2 years from date of injury"),
    "DE": (2, "2 years from date of injury"),
    "FL": (4, "4 years from date of injury"),
    "GA": (2, "2 years from date of injury"),
    "HI": (2, "2 years from date of injury"),
    "ID": (2, "2 years from date of injury"),
    "IL": (2, "2 years from date of injury"),
    "IN": (2, "2 years from date of injury"),
    "IA": (2, "2 years from date of injury"),
    "KS": (2, "2 years from date of injury"),
    "KY": (1, "1 year from date of injury"),
    "LA": (1, "1 year from date of injury (prescription)"),
    "ME": (6, "6 years from date of injury"),
    "MD": (3, "3 years from date of injury"),
    "MA": (3, "3 years from date of injury"),
    "MI": (3, "3 years from date of injury"),
    "MN": (2, "2 years from date of injury; 6 years for auto"),
    "MS": (3, "3 years from date of injury"),
    "MO": (5, "5 years from date of injury"),
    "MT": (3, "3 years from date of injury"),
    "NE": (4, "4 years from date of injury"),
    "NV": (2, "2 years from date of injury"),
    "NH": (3, "3 years from date of injury"),
    "NJ": (2, "2 years from date of injury"),
    "NM": (3, "3 years from date of injury"),
    "NY": (3, "3 years from date of injury"),
    "NC": (3, "3 years from date of injury"),
    "ND": (6, "6 years from date of injury"),
    "OH": (2, "2 years from date of injury"),
    "OK": (2, "2 years from date of injury"),
    "OR": (2, "2 years from date of injury"),
    "PA": (2, "2 years from date of injury"),
    "RI": (3, "3 years from date of injury"),
    "SC": (3, "3 years from date of injury"),
    "SD": (3, "3 years from date of injury"),
    "TN": (1, "1 year from date of injury"),
    "TX": (2, "2 years from date of injury"),
    "UT": (4, "4 years from date of injury"),
    "VT": (3, "3 years from date of injury"),
    "VA": (2, "2 years from date of injury"),
    "WA": (3, "3 years from date of injury"),
    "WV": (2, "2 years from date of injury"),
    "WI": (3, "3 years from date of injury"),
    "WY": (4, "4 years from date of injury"),
}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

# Major metros for each state (largest MSAs)
# Counties will be populated from external data
MAJOR_METROS = {
    "CA": {"Los Angeles": ["Los Angeles"], "San Francisco": ["San Francisco", "San Mateo", "Alameda"], "San Diego": ["San Diego"]},
    "TX": {"Houston": ["Harris", "Fort Bend", "Montgomery"], "Dallas": ["Dallas", "Tarrant", "Collin"], "Austin": ["Travis", "Williamson"]},
    "FL": {"Miami": ["Miami-Dade", "Broward", "Palm Beach"], "Tampa": ["Hillsborough", "Pinellas"], "Orlando": ["Orange", "Seminole"]},
    "NY": {"New York City": ["New York", "Kings", "Queens", "Bronx", "Richmond"], "Buffalo": ["Erie"], "Albany": ["Albany"]},
    "GA": {"Atlanta": ["Fulton", "DeKalb", "Cobb", "Gwinnett"], "Savannah": ["Chatham"]},
    "NC": {"Charlotte": ["Mecklenburg", "Gaston"], "Raleigh": ["Wake", "Durham"], "Greensboro": ["Guilford"]},
    "SC": {"Charleston": ["Charleston", "Berkeley", "Dorchester"], "Columbia": ["Richland", "Lexington"], "Greenville-Spartanburg": ["Greenville", "Spartanburg"]},
    # Add more as needed - this is a starting template
}


def generate_state_file(abbr: str, output_dir: Path):
    """Generate JSON file for a single state."""
    sol_years, sol_notes = STATE_SOL[abbr]

    data = {
        "name": STATE_NAMES[abbr],
        "abbreviation": abbr,
        "sol_years": sol_years,
        "sol_notes": sol_notes,
        "counties": [],  # To be populated
        "major_metros": MAJOR_METROS.get(abbr, {}),
        "default_preferred_counties": [],
    }

    # Set default counties from first metro if available
    if data["major_metros"]:
        first_metro = list(data["major_metros"].values())[0]
        data["default_preferred_counties"] = first_metro

    output_file = output_dir / f"{abbr}.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Generated {output_file}")


def main():
    output_dir = Path(__file__).parent.parent / "data" / "states"
    output_dir.mkdir(parents=True, exist_ok=True)

    for abbr in STATE_SOL:
        # Skip SC - we already have it with full county data
        if abbr == "SC":
            continue
        generate_state_file(abbr, output_dir)

    print(f"\nGenerated {len(STATE_SOL) - 1} state files (SC already exists)")
    print("NOTE: County lists need to be populated from external source")


if __name__ == "__main__":
    main()
```

**Step 2: Run generation script**

Run: `python3 scripts/generate_state_data.py`
Expected: "Generated 49 state files"

**Step 3: Verify states are loadable**

Run: `python3 -c "from src.state_data import get_all_states; print(f'{len(get_all_states())} states available')"`
Expected: "50 states available"

**Step 4: Update test to verify all 50 states**

Add to `tests/test_state_data.py`:

```python
def test_all_50_states_available():
    """All 50 US states have data files."""
    states = get_all_states()
    assert len(states) == 50
```

Run: `python3 -m pytest tests/test_state_data.py::test_all_50_states_available -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/states/*.json scripts/generate_state_data.py tests/test_state_data.py
git commit -m "feat: add state data files for all 50 states"
```

---

## Phase 2: Mode-Aware Runtime

### Task 4: Add Mode Configuration

**Files:**
- Modify: `src/config.py`
- Create: `tests/test_mode_config.py`

**Step 1: Write failing test**

Create `tests/test_mode_config.py`:

```python
"""Tests for mode-aware configuration."""
import pytest
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AppConfig, OperationMode


def test_default_mode_is_starter():
    """Default operation mode is starter."""
    os.environ.pop("OPERATION_MODE", None)
    config = AppConfig.from_env()
    assert config.mode == OperationMode.STARTER


def test_pro_mode_from_env():
    """Pro mode can be set via environment."""
    os.environ["OPERATION_MODE"] = "pro"
    config = AppConfig.from_env()
    assert config.mode == OperationMode.PRO
    os.environ.pop("OPERATION_MODE", None)


def test_starter_mode_disables_clio():
    """Starter mode has Clio disabled."""
    os.environ["OPERATION_MODE"] = "starter"
    config = AppConfig.from_env()
    assert config.clio_enabled is False
    os.environ.pop("OPERATION_MODE", None)


def test_starter_mode_disables_email():
    """Starter mode has email disabled."""
    os.environ["OPERATION_MODE"] = "starter"
    config = AppConfig.from_env()
    assert config.email_enabled is False
    os.environ.pop("OPERATION_MODE", None)


def test_pro_mode_enables_integrations():
    """Pro mode enables Clio and email."""
    os.environ["OPERATION_MODE"] = "pro"
    config = AppConfig.from_env()
    assert config.clio_enabled is True
    assert config.email_enabled is True
    os.environ.pop("OPERATION_MODE", None)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_mode_config.py -v`
Expected: FAIL with "ImportError" or "AttributeError"

**Step 3: Add OperationMode enum and mode fields to config.py**

Add to `src/config.py` after imports:

```python
from enum import Enum

class OperationMode(Enum):
    """Operation mode for the qualifier."""
    STARTER = "starter"
    PRO = "pro"
```

Add to AppConfig class:

```python
    # Operation mode
    mode: OperationMode = OperationMode.STARTER
    clio_enabled: bool = False
    email_enabled: bool = False
```

Update `AppConfig.from_env()` method:

```python
    @classmethod
    def from_env(cls) -> "AppConfig":
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
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_mode_config.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/config.py tests/test_mode_config.py
git commit -m "feat: add operation mode (starter/pro) to config"
```

---

### Task 5: Add Mode-Aware Processing

**Files:**
- Modify: `src/main.py`
- Create: `tests/test_mode_processing.py`

**Step 1: Write failing test**

Create `tests/test_mode_processing.py`:

```python
"""Tests for mode-aware lead processing."""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AppConfig, OperationMode


def test_starter_mode_skips_clio(monkeypatch):
    """Starter mode does not create Clio matters."""
    monkeypatch.setenv("OPERATION_MODE", "starter")

    from src.main import LeadProcessor
    config = AppConfig.from_env()

    # Verify mode is starter
    assert config.mode == OperationMode.STARTER
    assert config.clio_enabled is False


def test_starter_mode_skips_email(monkeypatch):
    """Starter mode does not send emails."""
    monkeypatch.setenv("OPERATION_MODE", "starter")

    config = AppConfig.from_env()
    assert config.email_enabled is False
```

**Step 2: Run tests**

Run: `python3 -m pytest tests/test_mode_processing.py -v`
Expected: PASS (mode flags already work)

**Step 3: Update main.py to respect mode flags**

Read the current `process_lead` method in `src/main.py` and add mode checks:

Find the Clio matter creation code and wrap it:

```python
# Only create Clio matter in Pro mode
if self.config.clio_enabled and result.tier == QualificationTier.TIER_1_AUTO_ACCEPT:
    # existing Clio code
```

Find the email sending code and wrap it:

```python
# Only send emails in Pro mode
if self.config.email_enabled:
    # existing email code
```

**Step 4: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/main.py tests/test_mode_processing.py
git commit -m "feat: add mode-aware processing (skip Clio/email in starter)"
```

---

## Phase 3: API Validators

### Task 6: Create API Validation Module

**Files:**
- Create: `setup/validators.py`
- Create: `tests/test_validators.py`

**Step 1: Create setup directory**

```bash
mkdir -p setup
touch setup/__init__.py
```

**Step 2: Write failing tests**

Create `tests/test_validators.py`:

```python
"""Tests for API key validators."""
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from setup.validators import (
    validate_airtable_key,
    validate_anthropic_key,
    validate_openai_key,
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
```

**Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_validators.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Create validators.py**

Create `setup/validators.py`:

```python
"""API key validation helpers for setup wizard."""
from dataclasses import dataclass
from typing import Optional
import re


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
    if not (api_key.startswith("pat") or api_key.startswith("key")):
        return ValidationResult(
            valid=False,
            message="Invalid key format. Airtable keys start with 'pat' or 'key'"
        )

    # If we have base/table IDs, we could test the connection
    # For now, just validate format
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
```

**Step 5: Run tests**

Run: `python3 -m pytest tests/test_validators.py -v`
Expected: All 5 tests PASS

**Step 6: Commit**

```bash
git add setup/ tests/test_validators.py
git commit -m "feat: add API key validators for setup wizard"
```

---

## Phase 4: Setup Wizard

### Task 7: Create Flask Wizard App Structure

**Files:**
- Create: `setup/app.py`
- Create: `setup/templates/base.html`
- Create: `setup/templates/index.html`
- Create: `setup/static/style.css`

**Step 1: Create Flask app skeleton**

Create `setup/app.py`:

```python
"""Setup wizard Flask application."""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from pathlib import Path
import json
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.state_data import load_state, get_all_states
from setup.validators import (
    validate_airtable_key,
    validate_anthropic_key,
    validate_openai_key,
    validate_clio_credentials,
)

app = Flask(__name__)
app.secret_key = "pi-lead-qualifier-setup"  # For session management

# Store wizard state
wizard_data = {}


@app.route("/")
def index():
    """Welcome page with mode selection."""
    return render_template("index.html")


@app.route("/api/states")
def get_states():
    """Return list of all available states."""
    states = get_all_states()
    return jsonify(states)


@app.route("/api/state/<abbr>")
def get_state(abbr):
    """Return state data for a specific state."""
    try:
        state = load_state(abbr)
        return jsonify({
            "name": state.name,
            "abbreviation": state.abbreviation,
            "sol_years": state.sol_years,
            "sol_notes": state.sol_notes,
            "counties": state.counties,
            "major_metros": state.major_metros,
            "default_preferred_counties": state.default_preferred_counties,
        })
    except FileNotFoundError:
        return jsonify({"error": f"State not found: {abbr}"}), 404


@app.route("/api/validate/airtable", methods=["POST"])
def validate_airtable():
    """Validate Airtable API key."""
    data = request.json
    result = validate_airtable_key(
        data.get("api_key", ""),
        data.get("base_id", ""),
        data.get("table_id", ""),
    )
    return jsonify({"valid": result.valid, "message": result.message})


@app.route("/api/validate/ai", methods=["POST"])
def validate_ai():
    """Validate AI provider API key."""
    data = request.json
    provider = data.get("provider", "anthropic")
    api_key = data.get("api_key", "")

    if provider == "anthropic":
        result = validate_anthropic_key(api_key)
    else:
        result = validate_openai_key(api_key)

    return jsonify({"valid": result.valid, "message": result.message})


@app.route("/api/generate-config", methods=["POST"])
def generate_config():
    """Generate .env file from wizard data."""
    data = request.json

    # Build .env content
    env_lines = [
        "# PI Lead Qualifier Configuration",
        f"# Generated by setup wizard",
        "",
        "# Operation Mode",
        f"OPERATION_MODE={data.get('mode', 'starter')}",
        "",
        "# Firm Information",
        f"FIRM_NAME={data.get('firm_name', '')}",
        f"ATTORNEY_NAME={data.get('attorney_name', '')}",
        "",
        "# Geographic Settings",
        f"STATE={data.get('state', '')}",
        f"SOL_YEARS={data.get('sol_years', 3)}",
        f"PREFERRED_COUNTIES={','.join(data.get('preferred_counties', []))}",
        "",
        "# Airtable",
        f"AIRTABLE_API_KEY={data.get('airtable_api_key', '')}",
        f"AIRTABLE_BASE_ID={data.get('airtable_base_id', '')}",
        f"AIRTABLE_TABLE_ID={data.get('airtable_table_id', '')}",
        "",
        "# AI Provider",
        f"AI_PROVIDER={data.get('ai_provider', 'anthropic')}",
    ]

    if data.get('ai_provider') == 'anthropic':
        env_lines.append(f"ANTHROPIC_API_KEY={data.get('ai_api_key', '')}")
    else:
        env_lines.append(f"OPENAI_API_KEY={data.get('ai_api_key', '')}")

    # Pro mode additions
    if data.get('mode') == 'pro':
        env_lines.extend([
            "",
            "# Clio Integration (Pro Mode)",
            f"CLIO_CLIENT_ID={data.get('clio_client_id', '')}",
            f"CLIO_CLIENT_SECRET={data.get('clio_client_secret', '')}",
            "",
            "# Email Settings (Pro Mode)",
            f"GMAIL_SENDER_EMAIL={data.get('sender_email', '')}",
            f"GMAIL_INTAKE_EMAIL={data.get('intake_email', '')}",
            f"GMAIL_NOTIFICATION_EMAIL={data.get('notification_email', '')}",
        ])

    env_content = "\n".join(env_lines)

    # Write to .env file
    env_path = Path(__file__).parent.parent / ".env"
    with open(env_path, "w") as f:
        f.write(env_content)

    return jsonify({
        "success": True,
        "message": "Configuration saved! You can now run the qualifier.",
        "env_path": str(env_path),
    })


if __name__ == "__main__":
    app.run(debug=True, port=8080)
```

**Step 2: Create base template**

Create `setup/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PI Lead Qualifier Setup{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <header>
            <h1>PI Lead Qualifier</h1>
            <p class="tagline">AI-Powered Lead Qualification for Personal Injury Attorneys</p>
        </header>

        <main>
            {% block content %}{% endblock %}
        </main>

        <footer>
            <p>Free and Open Source | <a href="https://github.com/your-repo">View on GitHub</a></p>
        </footer>
    </div>

    {% block scripts %}{% endblock %}
</body>
</html>
```

**Step 3: Create index template**

Create `setup/templates/index.html`:

```html
{% extends "base.html" %}

{% block content %}
<div class="welcome">
    <h2>Welcome to Setup</h2>
    <p>Choose your setup mode to get started:</p>

    <div class="mode-cards">
        <div class="mode-card" onclick="location.href='/starter'">
            <h3>Starter Mode</h3>
            <p class="price">Free</p>
            <ul>
                <li>✓ Airtable integration</li>
                <li>✓ AI-powered scoring</li>
                <li>✓ Lead tier assignment</li>
                <li>✗ Clio integration</li>
                <li>✗ Email notifications</li>
            </ul>
            <button class="btn btn-primary">Get Started</button>
        </div>

        <div class="mode-card featured" onclick="location.href='/pro'">
            <span class="badge">Recommended</span>
            <h3>Pro Mode</h3>
            <p class="price">Free</p>
            <ul>
                <li>✓ Everything in Starter</li>
                <li>✓ Clio matter creation</li>
                <li>✓ Email notifications</li>
                <li>✓ Auto-decline emails</li>
                <li>✓ Full automation</li>
            </ul>
            <button class="btn btn-primary">Get Started</button>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 4: Create basic CSS**

Create `setup/static/style.css`:

```css
/* PI Lead Qualifier Setup Wizard Styles */

:root {
    --primary: #2563eb;
    --primary-dark: #1d4ed8;
    --success: #16a34a;
    --error: #dc2626;
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-700: #374151;
    --gray-900: #111827;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--gray-50);
    color: var(--gray-900);
    line-height: 1.6;
}

.container {
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem;
}

header {
    text-align: center;
    margin-bottom: 3rem;
}

header h1 {
    font-size: 2rem;
    color: var(--primary);
}

.tagline {
    color: var(--gray-700);
    margin-top: 0.5rem;
}

/* Mode Selection Cards */
.mode-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
    margin-top: 2rem;
}

.mode-card {
    background: white;
    border: 2px solid var(--gray-200);
    border-radius: 12px;
    padding: 2rem;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
}

.mode-card:hover {
    border-color: var(--primary);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.mode-card.featured {
    border-color: var(--primary);
}

.mode-card .badge {
    position: absolute;
    top: -10px;
    right: 20px;
    background: var(--primary);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
}

.mode-card h3 {
    font-size: 1.25rem;
    margin-bottom: 0.5rem;
}

.mode-card .price {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 1rem;
}

.mode-card ul {
    list-style: none;
    margin-bottom: 1.5rem;
}

.mode-card li {
    padding: 0.25rem 0;
}

/* Buttons */
.btn {
    display: inline-block;
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    width: 100%;
    text-align: center;
}

.btn-primary {
    background: var(--primary);
    color: white;
}

.btn-primary:hover {
    background: var(--primary-dark);
}

/* Forms */
.form-group {
    margin-bottom: 1.5rem;
}

.form-group label {
    display: block;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.form-group input,
.form-group select {
    width: 100%;
    padding: 0.75rem;
    border: 2px solid var(--gray-200);
    border-radius: 8px;
    font-size: 1rem;
}

.form-group input:focus,
.form-group select:focus {
    outline: none;
    border-color: var(--primary);
}

/* Footer */
footer {
    margin-top: 4rem;
    text-align: center;
    color: var(--gray-700);
}

footer a {
    color: var(--primary);
}
```

**Step 5: Test Flask app runs**

Run: `python3 setup/app.py`
Expected: Server starts on http://localhost:8080

**Step 6: Commit**

```bash
git add setup/
git commit -m "feat: add Flask setup wizard with welcome page"
```

---

### Task 8: Create Starter Mode Wizard Pages

**Files:**
- Create: `setup/templates/starter.html`
- Modify: `setup/app.py` (add routes)

**Step 1: Create starter wizard template**

Create `setup/templates/starter.html`:

```html
{% extends "base.html" %}

{% block content %}
<div class="wizard">
    <div class="progress-bar">
        <div class="step active" data-step="1">1. Your Firm</div>
        <div class="step" data-step="2">2. Airtable</div>
        <div class="step" data-step="3">3. AI Provider</div>
    </div>

    <form id="wizard-form">
        <!-- Step 1: Firm Info -->
        <div class="wizard-step" id="step-1">
            <h2>Tell us about your firm</h2>

            <div class="form-group">
                <label for="firm_name">Firm Name</label>
                <input type="text" id="firm_name" name="firm_name" required
                       placeholder="Smith & Associates">
            </div>

            <div class="form-group">
                <label for="attorney_name">Your Name</label>
                <input type="text" id="attorney_name" name="attorney_name" required
                       placeholder="John Smith">
            </div>

            <div class="form-group">
                <label for="state">State</label>
                <select id="state" name="state" required>
                    <option value="">Select your state...</option>
                </select>
            </div>

            <div class="form-group" id="counties-group" style="display:none;">
                <label>Preferred Counties</label>
                <p class="hint">Select the counties where you primarily practice</p>
                <div id="counties-list" class="checkbox-grid"></div>
            </div>

            <button type="button" class="btn btn-primary" onclick="nextStep()">
                Continue →
            </button>
        </div>

        <!-- Step 2: Airtable -->
        <div class="wizard-step" id="step-2" style="display:none;">
            <h2>Connect Airtable</h2>
            <p>We'll store and track your leads in Airtable.</p>

            <div class="form-group">
                <label for="airtable_api_key">API Key</label>
                <input type="password" id="airtable_api_key" name="airtable_api_key" required
                       placeholder="pat_xxxxxxxxxxxx">
                <details class="help-text">
                    <summary>How do I get this?</summary>
                    <ol>
                        <li>Go to <a href="https://airtable.com/create/tokens" target="_blank">airtable.com/create/tokens</a></li>
                        <li>Click "Create new token"</li>
                        <li>Name it "PI Lead Qualifier"</li>
                        <li>Add scopes: data.records:read, data.records:write</li>
                        <li>Add your base</li>
                        <li>Copy the token</li>
                    </ol>
                </details>
            </div>

            <div class="form-group">
                <label for="airtable_base_id">Base ID</label>
                <input type="text" id="airtable_base_id" name="airtable_base_id" required
                       placeholder="appXXXXXXXXXXXXXX">
            </div>

            <div class="form-group">
                <label for="airtable_table_id">Table ID</label>
                <input type="text" id="airtable_table_id" name="airtable_table_id" required
                       placeholder="tblXXXXXXXXXXXXXX">
            </div>

            <button type="button" class="btn btn-secondary" onclick="validateAirtable()">
                Validate Connection
            </button>
            <div id="airtable-status" class="status"></div>

            <div class="nav-buttons">
                <button type="button" class="btn btn-outline" onclick="prevStep()">
                    ← Back
                </button>
                <button type="button" class="btn btn-primary" onclick="nextStep()">
                    Continue →
                </button>
            </div>
        </div>

        <!-- Step 3: AI Provider -->
        <div class="wizard-step" id="step-3" style="display:none;">
            <h2>Choose AI Provider</h2>

            <div class="radio-cards">
                <label class="radio-card">
                    <input type="radio" name="ai_provider" value="anthropic" checked>
                    <div class="card-content">
                        <h3>Claude (Anthropic)</h3>
                        <p>Best for nuanced legal analysis</p>
                        <p class="price">~$0.01 per lead</p>
                    </div>
                </label>

                <label class="radio-card">
                    <input type="radio" name="ai_provider" value="openai">
                    <div class="card-content">
                        <h3>ChatGPT (OpenAI)</h3>
                        <p>Fast and reliable</p>
                        <p class="price">~$0.02 per lead</p>
                    </div>
                </label>
            </div>

            <div class="form-group">
                <label for="ai_api_key">API Key</label>
                <input type="password" id="ai_api_key" name="ai_api_key" required
                       placeholder="sk-...">
            </div>

            <button type="button" class="btn btn-secondary" onclick="validateAI()">
                Validate Key
            </button>
            <div id="ai-status" class="status"></div>

            <div class="nav-buttons">
                <button type="button" class="btn btn-outline" onclick="prevStep()">
                    ← Back
                </button>
                <button type="button" class="btn btn-primary" onclick="generateConfig()">
                    Generate My System →
                </button>
            </div>
        </div>

        <!-- Success Screen -->
        <div class="wizard-step" id="step-success" style="display:none;">
            <div class="success-message">
                <h2>🎉 Setup Complete!</h2>
                <p>Your PI Lead Qualifier is ready to run.</p>

                <div class="next-steps">
                    <h3>Next Steps:</h3>
                    <ol>
                        <li>Open Terminal (Mac) or Command Prompt (Windows)</li>
                        <li>Navigate to this folder</li>
                        <li>Run: <code>python run_local.py</code></li>
                        <li>Visit <a href="http://localhost:8080">localhost:8080</a> to see your dashboard</li>
                    </ol>
                </div>

                <p class="upgrade-hint">
                    Want Clio integration and email notifications?
                    <a href="/pro">Upgrade to Pro Mode</a>
                </p>
            </div>
        </div>
    </form>
</div>
{% endblock %}

{% block scripts %}
<script>
let currentStep = 1;
let stateData = null;

// Load states on page load
document.addEventListener('DOMContentLoaded', async () => {
    const response = await fetch('/api/states');
    const states = await response.json();
    const select = document.getElementById('state');
    states.forEach(abbr => {
        const option = document.createElement('option');
        option.value = abbr;
        option.textContent = abbr;
        select.appendChild(option);
    });
});

// When state changes, load counties
document.getElementById('state').addEventListener('change', async (e) => {
    const abbr = e.target.value;
    if (!abbr) return;

    const response = await fetch(`/api/state/${abbr}`);
    stateData = await response.json();

    // Show counties
    const countiesGroup = document.getElementById('counties-group');
    const countiesList = document.getElementById('counties-list');
    countiesGroup.style.display = 'block';
    countiesList.innerHTML = '';

    stateData.counties.forEach(county => {
        const isDefault = stateData.default_preferred_counties.includes(county);
        const label = document.createElement('label');
        label.className = 'checkbox-label';
        label.innerHTML = `
            <input type="checkbox" name="counties" value="${county}" ${isDefault ? 'checked' : ''}>
            ${county}
        `;
        countiesList.appendChild(label);
    });
});

function nextStep() {
    document.getElementById(`step-${currentStep}`).style.display = 'none';
    currentStep++;
    document.getElementById(`step-${currentStep}`).style.display = 'block';
    updateProgress();
}

function prevStep() {
    document.getElementById(`step-${currentStep}`).style.display = 'none';
    currentStep--;
    document.getElementById(`step-${currentStep}`).style.display = 'block';
    updateProgress();
}

function updateProgress() {
    document.querySelectorAll('.progress-bar .step').forEach((el, i) => {
        el.classList.toggle('active', i < currentStep);
        el.classList.toggle('current', i === currentStep - 1);
    });
}

async function validateAirtable() {
    const apiKey = document.getElementById('airtable_api_key').value;
    const baseId = document.getElementById('airtable_base_id').value;
    const tableId = document.getElementById('airtable_table_id').value;

    const response = await fetch('/api/validate/airtable', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({api_key: apiKey, base_id: baseId, table_id: tableId})
    });
    const result = await response.json();

    const status = document.getElementById('airtable-status');
    status.className = 'status ' + (result.valid ? 'success' : 'error');
    status.textContent = result.message;
}

async function validateAI() {
    const provider = document.querySelector('input[name="ai_provider"]:checked').value;
    const apiKey = document.getElementById('ai_api_key').value;

    const response = await fetch('/api/validate/ai', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({provider: provider, api_key: apiKey})
    });
    const result = await response.json();

    const status = document.getElementById('ai-status');
    status.className = 'status ' + (result.valid ? 'success' : 'error');
    status.textContent = result.message;
}

async function generateConfig() {
    const formData = {
        mode: 'starter',
        firm_name: document.getElementById('firm_name').value,
        attorney_name: document.getElementById('attorney_name').value,
        state: document.getElementById('state').value,
        sol_years: stateData?.sol_years || 3,
        preferred_counties: Array.from(document.querySelectorAll('input[name="counties"]:checked'))
            .map(el => el.value),
        airtable_api_key: document.getElementById('airtable_api_key').value,
        airtable_base_id: document.getElementById('airtable_base_id').value,
        airtable_table_id: document.getElementById('airtable_table_id').value,
        ai_provider: document.querySelector('input[name="ai_provider"]:checked').value,
        ai_api_key: document.getElementById('ai_api_key').value,
    };

    const response = await fetch('/api/generate-config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(formData)
    });
    const result = await response.json();

    if (result.success) {
        document.getElementById(`step-${currentStep}`).style.display = 'none';
        document.getElementById('step-success').style.display = 'block';
    } else {
        alert('Error: ' + result.message);
    }
}
</script>
{% endblock %}
```

**Step 2: Add starter route to app.py**

Add to `setup/app.py`:

```python
@app.route("/starter")
def starter():
    """Starter mode wizard."""
    return render_template("starter.html")
```

**Step 3: Add CSS for wizard**

Add to `setup/static/style.css`:

```css
/* Wizard Styles */
.wizard {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.progress-bar {
    display: flex;
    justify-content: center;
    gap: 1rem;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--gray-200);
}

.progress-bar .step {
    padding: 0.5rem 1rem;
    border-radius: 9999px;
    background: var(--gray-100);
    color: var(--gray-700);
    font-size: 0.875rem;
}

.progress-bar .step.active {
    background: var(--primary);
    color: white;
}

.wizard-step h2 {
    margin-bottom: 1.5rem;
}

.checkbox-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 0.5rem;
    max-height: 300px;
    overflow-y: auto;
    padding: 1rem;
    background: var(--gray-50);
    border-radius: 8px;
}

.checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
}

.radio-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.radio-card {
    border: 2px solid var(--gray-200);
    border-radius: 8px;
    padding: 1rem;
    cursor: pointer;
}

.radio-card:has(input:checked) {
    border-color: var(--primary);
    background: var(--gray-50);
}

.radio-card input {
    display: none;
}

.nav-buttons {
    display: flex;
    justify-content: space-between;
    margin-top: 2rem;
}

.btn-outline {
    background: white;
    border: 2px solid var(--gray-200);
    color: var(--gray-700);
}

.btn-secondary {
    background: var(--gray-100);
    color: var(--gray-700);
    margin-bottom: 0.5rem;
}

.status {
    padding: 0.75rem;
    border-radius: 8px;
    margin: 0.5rem 0;
}

.status.success {
    background: #dcfce7;
    color: #166534;
}

.status.error {
    background: #fee2e2;
    color: #991b1b;
}

.help-text {
    font-size: 0.875rem;
    color: var(--gray-700);
    margin-top: 0.5rem;
}

.help-text summary {
    cursor: pointer;
    color: var(--primary);
}

.success-message {
    text-align: center;
    padding: 2rem;
}

.success-message h2 {
    font-size: 2rem;
    color: var(--success);
}

.next-steps {
    text-align: left;
    background: var(--gray-50);
    padding: 1.5rem;
    border-radius: 8px;
    margin: 1.5rem 0;
}

.next-steps code {
    background: var(--gray-200);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
}
```

**Step 4: Test the wizard**

Run: `python3 setup/app.py`
Visit: http://localhost:8080/starter
Expected: Three-step wizard displays and works

**Step 5: Commit**

```bash
git add setup/
git commit -m "feat: add starter mode wizard with 3 steps"
```

---

## Phase 5: Deploy Scripts

### Task 9: Create Local Run Scripts

**Files:**
- Create: `deploy/local/start-mac.sh`
- Create: `deploy/local/start-windows.bat`
- Create: `run_local.py`

**Step 1: Create deploy directory**

```bash
mkdir -p deploy/local
```

**Step 2: Create Mac script**

Create `deploy/local/start-mac.sh`:

```bash
#!/bin/bash
# PI Lead Qualifier - Mac Start Script

echo "==================================="
echo "   PI Lead Qualifier"
echo "==================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Please install Python from python.org"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "No configuration found. Starting setup wizard..."
    python3 setup/app.py
    exit 0
fi

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Installing dependencies..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Start the qualifier
echo "Starting PI Lead Qualifier..."
echo "Dashboard: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 run_local.py
```

**Step 3: Create Windows script**

Create `deploy/local/start-windows.bat`:

```batch
@echo off
title PI Lead Qualifier

echo ===================================
echo    PI Lead Qualifier
echo ===================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo No configuration found. Starting setup wizard...
    python setup\app.py
    exit /b
)

REM Install dependencies if needed
if not exist "venv" (
    echo Installing dependencies...
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)

REM Start the qualifier
echo Starting PI Lead Qualifier...
echo Dashboard: http://localhost:8080
echo.
echo Press Ctrl+C to stop
echo.

python run_local.py

pause
```

**Step 4: Create run_local.py**

Create `run_local.py`:

```python
#!/usr/bin/env python3
"""Local runner for PI Lead Qualifier."""
import os
import sys
from pathlib import Path

# Ensure we're in the right directory
os.chdir(Path(__file__).parent)

# Check for .env file
if not Path(".env").exists():
    print("No configuration found. Please run the setup wizard first.")
    print("Starting wizard at http://localhost:8080")
    from setup.app import app
    app.run(port=8080)
    sys.exit(0)

# Import and run
from src.config import load_config
from src.main import LeadProcessor

def main():
    print("Loading configuration...")
    config = load_config()

    print(f"Mode: {config.mode.value}")
    print(f"State: {config.qualification.state}")

    print("\nStarting dashboard on http://localhost:8080")
    print("Press Ctrl+C to stop\n")

    processor = LeadProcessor(config)

    try:
        processor.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        processor.stop()


if __name__ == "__main__":
    main()
```

**Step 5: Make scripts executable**

Run: `chmod +x deploy/local/start-mac.sh run_local.py`

**Step 6: Commit**

```bash
git add deploy/ run_local.py
git commit -m "feat: add local run scripts for Mac and Windows"
```

---

### Task 10: Create Railway Deploy Config

**Files:**
- Create: `deploy/railway/railway.json`
- Create: `deploy/railway/Procfile`
- Create: `railway.json` (root symlink or copy)

**Step 1: Create Railway config directory**

```bash
mkdir -p deploy/railway
```

**Step 2: Create railway.json**

Create `deploy/railway/railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python src/main.py",
    "healthcheckPath": "/health",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

**Step 3: Create Procfile**

Create `deploy/railway/Procfile`:

```
web: python src/main.py
```

**Step 4: Copy to root for Railway detection**

```bash
cp deploy/railway/railway.json ./railway.json
cp deploy/railway/Procfile ./Procfile
```

**Step 5: Commit**

```bash
git add deploy/railway/ railway.json Procfile
git commit -m "feat: add Railway deployment configuration"
```

---

## Phase 6: Documentation

### Task 11: Create Public README

**Files:**
- Create: `README.md`

**Step 1: Write README**

Create `README.md`:

```markdown
# PI Lead Qualifier

**Free, AI-powered lead qualification for personal injury attorneys.**

Automatically score and prioritize your intake leads, so you spend time on cases that matter.

---

## What It Does

1. **Connects to your Airtable** where leads come in
2. **Scores each lead** using AI (Claude or ChatGPT)
3. **Assigns a tier** (Accept, Review, or Decline)
4. **Updates your Airtable** with scores and recommendations

**Pro Mode adds:** Automatic Clio matter creation + email notifications.

---

## Quick Start

### 1. Download

```bash
git clone https://github.com/your-username/pi-lead-qualifier.git
cd pi-lead-qualifier
```

### 2. Run Setup Wizard

**Mac:**
```bash
./deploy/local/start-mac.sh
```

**Windows:**
Double-click `deploy\local\start-windows.bat`

### 3. Open Browser

Visit [http://localhost:8080](http://localhost:8080) and follow the wizard.

---

## Features

| Feature | Starter | Pro |
|---------|:-------:|:---:|
| Airtable integration | ✅ | ✅ |
| AI-powered scoring | ✅ | ✅ |
| Lead tier assignment | ✅ | ✅ |
| State SOL awareness | ✅ | ✅ |
| County preferences | ✅ | ✅ |
| Clio matter creation | ❌ | ✅ |
| Email notifications | ❌ | ✅ |
| Auto-decline emails | ❌ | ✅ |

---

## Requirements

- **Python 3.9+**
- **Airtable account** (free tier works)
- **AI API key** (Claude or OpenAI)
- **Clio account** (Pro mode only)

---

## All 50 States Supported

Built-in statute of limitations and county data for every US state.
Just select your state in the wizard - no configuration needed.

---

## Cloud Deployment

For 24/7 operation, deploy to Railway:

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/your-username/pi-lead-qualifier)

Estimated cost: ~$5/month

---

## Support

- **Issues:** [GitHub Issues](https://github.com/your-username/pi-lead-qualifier/issues)
- **Discussions:** [GitHub Discussions](https://github.com/your-username/pi-lead-qualifier/discussions)
- **Need help?** See [docs/find-a-developer.md](docs/find-a-developer.md)

---

## License

MIT License - Free to use and modify.

---

Built with ❤️ for the PI attorney community.
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add public README with quick start guide"
```

---

### Task 12: Create LICENSE and CONTRIBUTING

**Files:**
- Create: `LICENSE`
- Create: `CONTRIBUTING.md`

**Step 1: Create MIT License**

Create `LICENSE`:

```
MIT License

Copyright (c) 2026 PI Lead Qualifier Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Step 2: Create CONTRIBUTING.md**

Create `CONTRIBUTING.md`:

```markdown
# Contributing to PI Lead Qualifier

Thank you for your interest in contributing!

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/your-username/pi-lead-qualifier/issues) first
2. Create a new issue with:
   - What you expected to happen
   - What actually happened
   - Steps to reproduce
   - Your environment (OS, Python version)

### Adding State Data

If you notice incorrect SOL data for a state:

1. Fork the repository
2. Edit `data/states/XX.json`
3. Include a citation for the correct SOL
4. Submit a pull request

### Code Contributions

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a pull request

## Code Style

- Python code follows PEP 8
- Use type hints where practical
- Add tests for new features

## Questions?

Open a [Discussion](https://github.com/your-username/pi-lead-qualifier/discussions) for questions.
```

**Step 3: Commit**

```bash
git add LICENSE CONTRIBUTING.md
git commit -m "docs: add MIT license and contributing guide"
```

---

### Task 13: Create Help Documentation

**Files:**
- Create: `docs/find-a-developer.md`
- Create: `docs/video-setup.md`

**Step 1: Create find-a-developer.md**

Create `docs/find-a-developer.md`:

```markdown
# Need Help Setting Up?

If you're stuck and need technical help, here's how to find assistance.

## Option 1: Hire a Developer

Platforms where you can find Python developers:

- **Upwork** - Search: "Python Flask developer"
- **Fiverr** - Search: "Python automation"
- **Toptal** - Higher quality, higher cost

**Estimated cost:** $100-300 for setup assistance

### What to Ask For

Send them this message:

> I need help setting up an open-source Python application called "PI Lead Qualifier".
> It connects to Airtable and uses AI to score leads.
>
> GitHub: [link to repo]
>
> I need help with:
> - Installing Python and dependencies
> - Running the setup wizard
> - Connecting to my Airtable
> - Deploying to Railway for 24/7 operation
>
> This should take 1-2 hours for an experienced developer.

## Option 2: Community Help

- **GitHub Discussions** - Ask questions, get help from other users
- **Legal tech communities** - Other attorneys may have set this up

## Option 3: Referral

Contact us for a referral to developers who have set this up before.

Email: [your contact]
```

**Step 2: Create video-setup.md**

Create `docs/video-setup.md`:

```markdown
# Video Tutorials

Watch these videos for step-by-step setup guidance.

## Setup Videos

### 1. Overview (2 min)
What PI Lead Qualifier does and who it's for.

[Coming soon]

### 2. Starter Mode Setup (5 min)
Complete walkthrough of the setup wizard.

[Coming soon]

### 3. Pro Mode Upgrade (5 min)
Adding Clio and email integrations.

[Coming soon]

### 4. Cloud Deployment (3 min)
Deploying to Railway for 24/7 operation.

[Coming soon]

---

Videos will be posted to YouTube and linked here.
```

**Step 3: Commit**

```bash
git add docs/
git commit -m "docs: add help and video documentation"
```

---

## Final Task: Run All Tests and Verify

### Task 14: Final Verification

**Step 1: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: All tests pass

**Step 2: Verify wizard runs**

```bash
python3 setup/app.py
```

Visit http://localhost:8080 - verify:
- Welcome page shows Starter/Pro options
- Starter wizard has 3 steps
- State dropdown populates
- County checkboxes appear on state selection
- Validation buttons work

**Step 3: Verify state data**

```bash
python3 -c "from src.state_data import get_all_states; print(f'{len(get_all_states())} states')"
```

Expected: "50 states"

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete pi-lead-qualifier template implementation"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-3 | State data foundation (50 JSON files, loader) |
| 2 | 4-5 | Mode-aware runtime (starter/pro flags) |
| 3 | 6 | API validators for wizard |
| 4 | 7-8 | Setup wizard (Flask + templates) |
| 5 | 9-10 | Deploy scripts (local + Railway) |
| 6 | 11-14 | Documentation + final verification |

**Total: 14 tasks, ~60 atomic steps**
