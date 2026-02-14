"""
Test suite for Pflug Law Lead Qualifier.
Contains 8 test scenarios covering all qualification paths.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import QualificationConfig, ClaudeConfig
from src.airtable_client import Lead
from src.qualifier import (
    LeadQualifier,
    QualificationResult,
    QualificationTier,
)


@pytest.fixture
def qual_config():
    """Standard qualification config for testing."""
    # SC tri-county area (Charleston metro)
    tri_county = ["charleston", "berkeley", "dorchester"]
    # All SC counties for in-state detection
    sc_counties = [
        "abbeville", "aiken", "allendale", "anderson", "bamberg", "barnwell",
        "beaufort", "berkeley", "calhoun", "charleston", "cherokee", "chester",
        "chesterfield", "clarendon", "colleton", "darlington", "dillon",
        "dorchester", "edgefield", "fairfield", "florence", "georgetown",
        "greenville", "greenwood", "hampton", "horry", "jasper", "kershaw",
        "lancaster", "laurens", "lee", "lexington", "marion", "marlboro",
        "mccormick", "newberry", "oconee", "orangeburg", "pickens", "richland",
        "saluda", "spartanburg", "sumter", "union", "williamsburg", "york"
    ]
    return QualificationConfig(
        preferred_counties=tri_county,
        accepted_counties=sc_counties,
        state="SC"
    )


@pytest.fixture
def claude_config():
    """Claude config without API key for testing."""
    return ClaudeConfig(api_key="")  # No API key = no AI analysis


@pytest.fixture
def qualifier(qual_config, claude_config):
    """Create qualifier instance for testing."""
    return LeadQualifier(qual_config, claude_config)


def create_lead(
    name: str = "Test Lead",
    phone: str = "(843) 555-1234",
    email: str = "test@example.com",
    accident_date: datetime = None,
    accident_location: str = "Charleston, SC",
    injury_description: str = "Back injury",
    medical_treatment: str = "ER visit and orthopedic follow-up",
    insurance_carrier: str = "State Farm",
    liability_notes: str = "Rear-end collision, citation issued to defendant",
    status: str = "New",
    lead_source: str = "Website",
    capture_date: datetime = None,
    days_since_capture: int = 1,
    lead_summary: str = None,
    sentiment_analysis: str = None,
) -> Lead:
    """Helper to create test leads."""
    if accident_date is None:
        accident_date = datetime.now() - timedelta(days=30)
    if capture_date is None:
        capture_date = datetime.now() - timedelta(days=1)
    if lead_summary is None:
        lead_summary = f"Test lead: {injury_description}. Treatment: {medical_treatment}. Location: {accident_location}."

    return Lead(
        record_id="recTEST123",
        name=name,
        phone=phone,
        email=email,
        capture_date=capture_date,
        days_since_capture=days_since_capture,
        lead_source=lead_source,
        lead_summary=lead_summary,
        sentiment_analysis=sentiment_analysis,
        status=status,
        created_time=datetime.now(),
        accident_date=accident_date,
        accident_location=accident_location,
        injury_description=injury_description,
        medical_treatment=medical_treatment,
        insurance_carrier=insurance_carrier,
        liability_notes=liability_notes,
    )


class TestScenario1PerfectTriCounty:
    """
    Scenario 1: Perfect tri-county case (should auto-accept)

    - Clear liability (rear-end collision with citation)
    - Strong medical treatment (ER + orthopedic + surgery)
    - Serious injury (fracture)
    - Charleston County location
    - Insurance carrier identified
    - Well within SOL

    Expected: Tier 1 Auto-Accept with score >= 11
    """

    def test_perfect_tri_county_case(self, qualifier):
        lead = create_lead(
            name="John Smith",
            accident_location="Charleston, SC (Meeting Street)",
            injury_description="Fractured vertebrae, herniated disc at L4-L5. "
                              "Experiencing chronic back pain and numbness in legs. "
                              "Permanent injury expected.",
            medical_treatment="Emergency room visit at MUSC on date of accident. "
                             "Referred to orthopedic surgeon Dr. Jones. "
                             "Scheduled for spinal fusion surgery next month. "
                             "Currently in physical therapy 3x/week.",
            insurance_carrier="State Farm",
            liability_notes="Rear-end collision on I-26. Defendant cited for "
                           "following too closely. Police report confirms defendant "
                           "100% at fault. Witness statement supports our client.",
            accident_date=datetime.now() - timedelta(days=60),
        )

        result = qualifier.qualify_lead(lead)

        assert result.tier == QualificationTier.TIER_1_AUTO_ACCEPT
        assert result.total_score >= 11
        assert result.medical_treatment_met is True
        assert result.liability_met is True
        assert result.insurance_identified is True
        assert result.serious_injury is True
        assert result.is_tri_county is True
        assert result.county == "charleston"
        assert "fracture" in result.injury_type.lower() or "surgical" in result.injury_type.lower()


class TestScenario2GoodNonTriCounty:
    """
    Scenario 2: Good case but outside tri-county (should auto-accept with lower score)

    - Clear liability
    - Good medical treatment
    - Greenville County location (not tri-county but in SC)
    - Insurance identified

    Expected: Tier 1 Auto-Accept but without tri-county bonus
    """

    def test_good_non_tri_county_case(self, qualifier):
        lead = create_lead(
            name="Jane Doe",
            accident_location="Greenville, SC",
            injury_description="Broken arm, torn rotator cuff. Required surgery.",
            medical_treatment="ER visit at Greenville Memorial. Surgery performed "
                             "by orthopedic surgeon. Physical therapy ongoing.",
            insurance_carrier="Allstate",
            liability_notes="Other driver ran red light. Citation issued. "
                           "Defendant admitted fault at scene.",
            accident_date=datetime.now() - timedelta(days=45),
        )

        result = qualifier.qualify_lead(lead)

        assert result.tier == QualificationTier.TIER_1_AUTO_ACCEPT
        assert result.total_score >= 11
        assert result.is_tri_county is False
        assert result.is_in_sc is True
        assert result.county == "greenville"
        assert result.geographic_bonus == 0  # No tri-county bonus


class TestScenario3BorderlineLiability:
    """
    Scenario 3: Borderline liability (should flag for review)

    - Good medical treatment
    - Unclear or disputed liability
    - Insurance identified

    Expected: Tier 2 Review due to liability concerns
    """

    def test_borderline_liability_case(self, qualifier):
        lead = create_lead(
            name="Bob Wilson",
            accident_location="North Charleston, SC",
            injury_description="Whiplash, neck strain, headaches",
            medical_treatment="ER visit, chiropractor treatment, physical therapy",
            insurance_carrier="Progressive",
            liability_notes="T-bone collision at intersection. Both parties claim "
                           "green light. No witnesses. Police report lists fault as "
                           "disputed. Comparative negligence may apply.",
            accident_date=datetime.now() - timedelta(days=30),
        )

        result = qualifier.qualify_lead(lead)

        # Should be flagged for review due to disputed liability
        assert result.tier == QualificationTier.TIER_2_REVIEW
        assert result.liability_met is False or len(result.safety_flags) > 0
        assert any("disputed" in f.description.lower() for f in result.safety_flags)


class TestScenario4InsufficientMedical:
    """
    Scenario 4: Insufficient medical treatment (should flag for review)

    - Clear liability
    - No meaningful medical treatment
    - Insurance identified
    - In tri-county area (gets bonus points)

    Expected: Tier 2 Review - high-scoring case with treatment concern
    needs attorney review rather than auto-decline
    """

    def test_insufficient_medical_case(self, qualifier):
        lead = create_lead(
            name="Alice Brown",
            accident_location="Charleston, SC",
            injury_description="Sore neck and back",
            medical_treatment="None yet. Taking ibuprofen at home.",
            insurance_carrier="GEICO",
            liability_notes="Rear-end collision. Citation issued to other driver.",
            accident_date=datetime.now() - timedelta(days=14),
        )

        result = qualifier.qualify_lead(lead)

        # With tri-county bonus, score is high enough for review
        assert result.tier == QualificationTier.TIER_2_REVIEW
        assert result.medical_treatment_met is False
        assert result.is_tri_county is True
        assert "treatment" in result.qualification_notes.lower()


class TestScenario5SOLExpired:
    """
    Scenario 5: SOL expired or too close (should decline)

    - Good case otherwise
    - Accident occurred more than 2.5 years ago
    - Less than 18 months remaining on SOL

    Expected: Tier 3 Auto-Decline due to SOL concern
    """

    def test_sol_expired_case(self, qualifier):
        # Accident 2.5 years ago = only 6 months left on 3-year SOL
        lead = create_lead(
            name="Charlie Davis",
            accident_location="Charleston, SC",
            injury_description="Serious back injury, herniated disc",
            medical_treatment="ER visit, orthopedic treatment, surgery performed",
            insurance_carrier="Liberty Mutual",
            liability_notes="Clear rear-end collision. Other driver at fault.",
            accident_date=datetime.now() - timedelta(days=912),  # ~2.5 years ago
        )

        result = qualifier.qualify_lead(lead)

        assert result.tier == QualificationTier.TIER_3_AUTO_DECLINE
        assert result.sol_adequate is False
        assert result.months_until_sol is not None
        assert result.months_until_sol < 18


class TestScenario6MissingInformation:
    """
    Scenario 6: Missing some critical information (should flag for review)

    - Has liability info
    - No insurance carrier (missing)
    - Good medical treatment
    - Serious injury documented

    Expected: Tier 2 Review - strong case but missing insurance info
    """

    def test_missing_information_case(self, qualifier):
        lead = create_lead(
            name="David Evans",
            accident_location="Columbia, SC",  # Richland county = NOT tri-county
            injury_description="Fractured ribs from T-bone collision",
            medical_treatment="Emergency room visit, CT scan, orthopedic surgeon",
            insurance_carrier="",  # Unknown - this is what's missing
            liability_notes="T-bone collision at intersection. Other driver ran red light.",
            accident_date=datetime.now() - timedelta(days=21),
        )

        result = qualifier.qualify_lead(lead)

        # Medical (3) + Liability (3) + SOL (1) + Serious (2) = 9 points
        # Missing insurance, should be flagged for review
        assert result.tier == QualificationTier.TIER_2_REVIEW
        assert result.insurance_identified is False
        assert result.liability_met is True
        assert result.medical_treatment_met is True
        assert "insurance" in result.qualification_notes.lower()


class TestScenario7MinorPlaintiff:
    """
    Scenario 7: Minor plaintiff (should flag for review)

    - Good case otherwise
    - Plaintiff is under 18

    Expected: Tier 2 Review due to minor status requiring special handling
    """

    def test_minor_plaintiff_case(self, qualifier):
        lead = create_lead(
            name="Tommy Johnson (Minor)",
            accident_location="Charleston, SC",
            injury_description="16 year old passenger. Broken leg, minor child "
                              "was in back seat when collision occurred.",
            medical_treatment="ER visit at MUSC, orthopedic surgery for fracture, "
                             "physical therapy",
            insurance_carrier="Nationwide",
            liability_notes="Rear-end collision. Other driver cited for DUI. "
                           "Clear liability.",
            accident_date=datetime.now() - timedelta(days=30),
        )

        result = qualifier.qualify_lead(lead)

        # High-scoring case but should be flagged due to minor
        assert result.tier == QualificationTier.TIER_2_REVIEW
        assert any("minor" in f.flag_type.lower() for f in result.safety_flags)


class TestScenario8CommercialVehicle:
    """
    Scenario 8: Commercial vehicle involved (should flag for review)

    - Good case otherwise
    - 18-wheeler / commercial truck involved

    Expected: Tier 2 Review due to commercial vehicle (potential higher value)
    """

    def test_commercial_vehicle_case(self, qualifier):
        lead = create_lead(
            name="Frank Miller",
            accident_location="Berkeley County, SC (I-26)",
            injury_description="Severe back injury, multiple fractures after being "
                              "hit by 18-wheeler truck",
            medical_treatment="Airlifted to trauma center. Multiple surgeries. "
                             "Still in hospital.",
            insurance_carrier="Swift Transportation Insurance",
            liability_notes="Semi-truck rear-ended our client on I-26. "
                           "Trucker cited for distracted driving. DOT logs "
                           "show hours violation.",
            accident_date=datetime.now() - timedelta(days=7),
        )

        result = qualifier.qualify_lead(lead)

        # Would be auto-accept but commercial vehicle flags for review
        assert result.tier == QualificationTier.TIER_2_REVIEW
        assert any("commercial" in f.flag_type.lower() for f in result.safety_flags)
        assert result.total_score >= 11  # Would otherwise qualify


class TestGeographicAnalysis:
    """Test geographic analysis functionality."""

    def test_tri_county_detection(self, qualifier):
        """Test that tri-county areas are correctly identified."""
        test_cases = [
            ("Charleston, SC", "charleston", True),
            ("North Charleston, SC", "charleston", True),
            ("Mount Pleasant, SC", "charleston", True),
            ("Summerville, SC", "dorchester", True),
            ("Goose Creek, SC", "berkeley", True),
            ("Greenville, SC", "greenville", False),
            ("Columbia, SC", "richland", False),
            ("Myrtle Beach, SC", "horry", False),
        ]

        for location, expected_county, expected_tri in test_cases:
            county, is_tri, is_sc = qualifier._analyze_geography(location)
            assert county == expected_county, f"Failed for {location}"
            assert is_tri == expected_tri, f"Tri-county check failed for {location}"
            assert is_sc is True, f"SC check failed for {location}"

    def test_out_of_state_detection(self, qualifier):
        """Test that out-of-state locations are detected."""
        lead = create_lead(
            accident_location="Atlanta, GA",
            injury_description="Fracture requiring surgery",
            medical_treatment="ER visit, orthopedic surgery",
            liability_notes="Clear rear-end collision",
            insurance_carrier="State Farm",
        )

        result = qualifier.qualify_lead(lead)

        assert result.tier == QualificationTier.TIER_3_AUTO_DECLINE
        assert result.is_in_sc is False


class TestScoringCalculations:
    """Test individual scoring component calculations."""

    def test_medical_treatment_scoring(self, qualifier):
        """Test medical treatment threshold logic."""
        # ER + ortho = qualifies
        lead1 = create_lead(
            medical_treatment="ER visit followed by orthopedic consultation"
        )
        result1 = qualifier.qualify_lead(lead1)
        assert result1.medical_treatment_met is True

        # Surgery alone = qualifies
        lead2 = create_lead(
            medical_treatment="Underwent surgery for injuries"
        )
        result2 = qualifier.qualify_lead(lead2)
        assert result2.medical_treatment_met is True

        # Just ER = does not qualify
        lead3 = create_lead(
            medical_treatment="ER visit only"
        )
        result3 = qualifier.qualify_lead(lead3)
        assert result3.medical_treatment_met is False

    def test_liability_scoring(self, qualifier):
        """Test liability analysis logic."""
        # Rear-end = clear liability
        lead1 = create_lead(
            liability_notes="Rear-end collision on highway"
        )
        result1 = qualifier.qualify_lead(lead1)
        assert result1.liability_met is True

        # DUI = clear liability
        lead2 = create_lead(
            liability_notes="Other driver arrested for DUI"
        )
        result2 = qualifier.qualify_lead(lead2)
        assert result2.liability_met is True

        # Disputed = not clear
        lead3 = create_lead(
            liability_notes="Both parties dispute fault"
        )
        result3 = qualifier.qualify_lead(lead3)
        assert result3.liability_met is False

    def test_sol_calculation(self, qualifier):
        """Test statute of limitations calculations."""
        # Recent accident = plenty of time
        lead1 = create_lead(
            accident_date=datetime.now() - timedelta(days=30)
        )
        result1 = qualifier.qualify_lead(lead1)
        assert result1.sol_adequate is True
        assert result1.months_until_sol > 24

        # Old accident = SOL concern
        lead2 = create_lead(
            accident_date=datetime.now() - timedelta(days=900)
        )
        result2 = qualifier.qualify_lead(lead2)
        assert result2.sol_adequate is False


class TestSafetyFlags:
    """Test safety flag detection."""

    def test_disputed_liability_flag(self, qualifier):
        """Test that disputed liability triggers a flag."""
        lead = create_lead(
            liability_notes="Liability is disputed, my client may be at fault"
        )
        result = qualifier.qualify_lead(lead)

        assert any(f.flag_type == "disputed_liability" for f in result.safety_flags)

    def test_no_treatment_flag(self, qualifier):
        """Test that no treatment triggers a flag."""
        lead = create_lead(
            medical_treatment=""
        )
        result = qualifier.qualify_lead(lead)

        assert any(f.flag_type == "no_medical_treatment" for f in result.safety_flags)

    def test_multiple_parties_flag(self, qualifier):
        """Test that multiple parties triggers a flag."""
        lead = create_lead(
            liability_notes="Multi-vehicle chain reaction accident with three cars"
        )
        result = qualifier.qualify_lead(lead)

        assert any(f.flag_type == "multiple_parties" for f in result.safety_flags)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
