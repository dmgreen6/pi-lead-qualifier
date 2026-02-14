#!/usr/bin/env python3
"""
Test script for two-tier AI lead scoring system.
Tests 3 sample scenarios as specified:
1. High-value MVA (clear liability, $50K+ medical bills, known insurance)
2. Moderate slip-fall (premise liability, ongoing treatment, no insurance info)
3. Decline scenario (minor injury, no treatment, 2+ years post-incident)
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.airtable_client import Lead
from src.qualifier import TwoTierQualifier


def create_test_lead(
    name: str,
    accident_date: datetime,
    accident_location: str,
    injury_description: str,
    medical_treatment: str,
    liability_notes: str,
    insurance_carrier: str,
) -> Lead:
    """Create a test lead with specified parameters."""
    return Lead(
        record_id=f"test_{name.lower().replace(' ', '_')}",
        name=name,
        phone="843-555-1234",
        email=f"{name.lower().replace(' ', '.')}@example.com",
        accident_date=accident_date,
        accident_location=accident_location,
        injury_description=injury_description,
        medical_treatment=medical_treatment,
        insurance_carrier=insurance_carrier,
        liability_notes=liability_notes,
        status="New",
        lead_source="Test Scenario",
        created_time=datetime.now(),
    )


def print_separator():
    print("\n" + "=" * 80 + "\n")


def print_result(lead: Lead, result):
    """Print detailed results for a test scenario."""
    print(f"LEAD: {lead.name}")
    print(f"Accident: {lead.accident_date.strftime('%Y-%m-%d') if lead.accident_date else 'N/A'}")
    print(f"Location: {lead.accident_location}")
    print(f"Injuries: {lead.injury_description}")
    print(f"Treatment: {lead.medical_treatment}")
    print(f"Liability: {lead.liability_notes}")
    print(f"Insurance: {lead.insurance_carrier}")

    print_separator()

    print("CHATGPT TIER-1 ANALYSIS:")
    print(f"  Score: {result.chatgpt_score}/100")
    print(f"  Recommendation: {result.chatgpt_recommendation}")
    print(f"  Confidence: {result.chatgpt_confidence}%")
    print(f"  Analysis: {result.chatgpt_analysis}")
    if result.chatgpt_red_flags:
        print(f"  Red Flags:")
        for flag in result.chatgpt_red_flags:
            print(f"    - {flag}")

    if result.claude_triggered:
        print_separator()
        print("CLAUDE TIER-2 DEEP ANALYSIS:")
        print(f"  Triggered: Yes")
        print(f"  Recommendation: {result.claude_recommendation}")
        print(f"  Confidence: {result.claude_confidence}%")
        print(f"\n  Deep Analysis:\n  {result.claude_analysis}")
        print(f"\n  Case Comparisons:\n  {result.claude_case_comparisons}")
        print(f"\n  Carrier Strategy:\n  {result.claude_carrier_strategy}")

    print_separator()
    print(f"FINAL DECISION: {result.final_decision}")
    print(f"FINAL CONFIDENCE: {result.final_confidence}%")


def run_tests():
    """Run the 3 test scenarios."""
    print("=" * 80)
    print("TWO-TIER AI LEAD SCORING TEST")
    print("=" * 80)

    # Load configuration
    config = load_config()

    # Validate API keys
    if not config.openai.api_key:
        print("ERROR: OPENAI_API_KEY not set in .env")
        return False
    if not config.claude.api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        return False

    print(f"OpenAI Model: {config.openai.model}")
    print(f"Claude Model: {config.claude.model}")
    print(f"Thresholds: FAST-TRACK >= {config.scoring_thresholds.fast_track}, "
          f"CLAUDE-REVIEW >= {config.scoring_thresholds.claude_review}")

    # Initialize qualifier
    qualifier = TwoTierQualifier(
        openai_config=config.openai,
        claude_config=config.claude,
        drive_config=config.google_drive,
        thresholds=config.scoring_thresholds,
    )

    # =========================================================================
    # SCENARIO 1: High-value MVA
    # Expected: FAST-TRACK or high score leading to Accept
    # =========================================================================
    print_separator()
    print("SCENARIO 1: HIGH-VALUE MVA")
    print("Expected outcome: FAST-TRACK (Auto-Accept)")
    print_separator()

    lead1 = create_test_lead(
        name="John Smith",
        accident_date=datetime.now() - timedelta(days=45),
        accident_location="Highway 17, Charleston County, SC",
        injury_description="Multiple fractures to left leg and ankle requiring surgery. "
                         "Herniated disc at L4-L5. Ongoing physical therapy. "
                         "Currently unable to work. Total medical bills exceeding $75,000.",
        medical_treatment="Emergency room visit immediately after accident. "
                         "Surgery for leg fractures at MUSC. Orthopedic follow-up every 2 weeks. "
                         "Physical therapy 3x per week. Pain management specialist.",
        liability_notes="Client was rear-ended while stopped at a red light. "
                       "Other driver received citation for following too closely. "
                       "Police report confirms 100% fault on other driver. "
                       "Multiple witnesses provided statements.",
        insurance_carrier="GEICO",
    )

    try:
        result1 = qualifier.qualify_lead(lead1)
        print_result(lead1, result1)
    except Exception as e:
        print(f"ERROR in Scenario 1: {e}")
        import traceback
        traceback.print_exc()

    # =========================================================================
    # SCENARIO 2: Moderate Slip-Fall
    # Expected: CLAUDE-REVIEW (needs deeper analysis)
    # =========================================================================
    print_separator()
    print("\n" + "=" * 80)
    print("SCENARIO 2: MODERATE SLIP-FALL")
    print("Expected outcome: CLAUDE-REVIEW (needs analysis)")
    print_separator()

    lead2 = create_test_lead(
        name="Mary Johnson",
        accident_date=datetime.now() - timedelta(days=90),
        accident_location="Walmart Supercenter, North Charleston, Berkeley County, SC",
        injury_description="Fell on wet floor without warning signs. "
                         "Injured lower back and right hip. Persistent pain. "
                         "Cannot stand for long periods.",
        medical_treatment="ER visit same day. X-rays showed no fractures. "
                         "Currently seeing chiropractor 2x per week. "
                         "MRI scheduled for next week to check for soft tissue damage.",
        liability_notes="Slipped on freshly mopped floor. No wet floor signs were posted. "
                       "Manager filled out incident report. "
                       "Another customer witnessed the fall.",
        insurance_carrier="Unknown - need to identify Walmart's carrier",
    )

    try:
        result2 = qualifier.qualify_lead(lead2)
        print_result(lead2, result2)
    except Exception as e:
        print(f"ERROR in Scenario 2: {e}")
        import traceback
        traceback.print_exc()

    # =========================================================================
    # SCENARIO 3: Decline Scenario
    # Expected: DECLINE (low score)
    # =========================================================================
    print_separator()
    print("\n" + "=" * 80)
    print("SCENARIO 3: DECLINE SCENARIO")
    print("Expected outcome: DECLINE")
    print_separator()

    lead3 = create_test_lead(
        name="Bob Wilson",
        accident_date=datetime.now() - timedelta(days=800),  # Over 2 years ago
        accident_location="Parking lot, Columbia, SC",
        injury_description="Minor bruising to arm. Slight neck stiffness that "
                         "went away after a few days.",
        medical_treatment="None. Did not see a doctor.",
        liability_notes="Fender bender in parking lot. Both drivers thought they had "
                       "the right of way. No police report filed. No witnesses.",
        insurance_carrier="Unknown",
    )

    try:
        result3 = qualifier.qualify_lead(lead3)
        print_result(lead3, result3)
    except Exception as e:
        print(f"ERROR in Scenario 3: {e}")
        import traceback
        traceback.print_exc()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"\nScenario 1 (High-value MVA): {result1.final_decision} "
          f"(Score: {result1.chatgpt_score}, Claude: {'Yes' if result1.claude_triggered else 'No'})")
    print(f"Scenario 2 (Moderate Slip-Fall): {result2.final_decision} "
          f"(Score: {result2.chatgpt_score}, Claude: {'Yes' if result2.claude_triggered else 'No'})")
    print(f"Scenario 3 (Decline): {result3.final_decision} "
          f"(Score: {result3.chatgpt_score}, Claude: {'Yes' if result3.claude_triggered else 'No'})")

    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
