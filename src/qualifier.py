"""
Lead qualification engine for Pflug Law.
Implements scoring logic and AI analysis for lead qualification.

Supports two modes:
1. Legacy mode: Point-based scoring with optional Claude analysis
2. Two-tier mode: ChatGPT Tier-1 scoring + Claude Tier-2 deep analysis
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import anthropic

from .config import QualificationConfig, ClaudeConfig, OpenAIConfig, GoogleDriveConfig, ScoringThresholds
from .airtable_client import Lead, TwoTierScoringUpdate

logger = logging.getLogger(__name__)


class QualificationTier(Enum):
    """Lead qualification tiers."""
    TIER_1_AUTO_ACCEPT = "tier1"
    TIER_2_REVIEW = "tier2"
    TIER_3_AUTO_DECLINE = "tier3"


@dataclass
class SafetyFlag:
    """Represents a safety concern that requires manual review."""
    flag_type: str
    description: str
    severity: str  # "block", "review", "info"


@dataclass
class QualificationResult:
    """Complete qualification result for a lead."""
    tier: QualificationTier
    total_score: int

    # Component scores
    medical_treatment_met: bool
    medical_treatment_points: int
    liability_met: bool
    liability_points: int
    insurance_identified: bool
    insurance_points: int
    sol_adequate: bool
    sol_points: int
    serious_injury: bool
    serious_injury_points: int
    geographic_bonus: int

    # Extracted data
    county: Optional[str]
    is_tri_county: bool
    is_in_sc: bool
    months_until_sol: Optional[int]
    estimated_case_value: Optional[float]
    injury_type: str

    # Analysis
    qualification_notes: str
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)
    recommended_questions: list[str] = field(default_factory=list)

    # Safety flags
    safety_flags: list[SafetyFlag] = field(default_factory=list)

    # AI analysis
    ai_analysis: Optional[str] = None


class LeadQualifier:
    """Lead qualification engine with Claude AI integration."""

    def __init__(self, qual_config: QualificationConfig, claude_config: ClaudeConfig):
        self.config = qual_config
        self.claude_config = claude_config
        self._claude_client: Optional[anthropic.Anthropic] = None

    @property
    def claude_client(self) -> Optional[anthropic.Anthropic]:
        """Lazy-load Claude client."""
        if self._claude_client is None and self.claude_config.api_key:
            self._claude_client = anthropic.Anthropic(api_key=self.claude_config.api_key)
        return self._claude_client

    def qualify_lead(self, lead: Lead) -> QualificationResult:
        """Perform complete qualification analysis on a lead."""
        logger.info(f"Qualifying lead: {lead.name} (ID: {lead.record_id})")

        # Extract and analyze components
        county, is_tri_county, is_in_sc = self._analyze_geography(lead.accident_location)
        months_until_sol = self._calculate_sol_remaining(lead.accident_date)
        safety_flags = self._check_safety_rules(lead)

        # Perform scoring analysis
        medical_met, medical_points, medical_details = self._analyze_medical_treatment(lead)
        liability_met, liability_points, liability_details = self._analyze_liability(lead)
        insurance_met, insurance_points = self._analyze_insurance(lead)
        sol_adequate, sol_points = self._analyze_sol(months_until_sol)
        serious, serious_points, injury_type = self._analyze_injury_severity(lead)

        # Calculate geographic bonus
        if not is_in_sc:
            geographic_bonus = 0  # Will be auto-declined anyway
        elif is_tri_county:
            geographic_bonus = self.config.tri_county_bonus
        else:
            geographic_bonus = 0

        # Calculate total score
        total_score = (
            medical_points +
            liability_points +
            insurance_points +
            sol_points +
            serious_points +
            geographic_bonus
        )

        # Determine tier (considering safety flags)
        tier = self._determine_tier(total_score, safety_flags, is_in_sc, sol_adequate)

        # Build analysis lists
        strengths, concerns, missing_info, questions = self._build_analysis_lists(
            lead, medical_met, liability_met, insurance_met, sol_adequate, serious,
            is_tri_county, county, medical_details, liability_details
        )

        # Estimate case value
        estimated_value = self._estimate_case_value(serious, medical_met, liability_met, is_tri_county)

        # Get AI analysis if available
        ai_analysis = None
        if self.claude_client and tier != QualificationTier.TIER_3_AUTO_DECLINE:
            ai_analysis = self._get_ai_analysis(lead, total_score, tier, safety_flags)

        # Generate qualification notes
        notes = self._generate_qualification_notes(
            lead, tier, total_score, strengths, concerns, missing_info,
            questions, safety_flags, ai_analysis
        )

        return QualificationResult(
            tier=tier,
            total_score=total_score,
            medical_treatment_met=medical_met,
            medical_treatment_points=medical_points,
            liability_met=liability_met,
            liability_points=liability_points,
            insurance_identified=insurance_met,
            insurance_points=insurance_points,
            sol_adequate=sol_adequate,
            sol_points=sol_points,
            serious_injury=serious,
            serious_injury_points=serious_points,
            geographic_bonus=geographic_bonus,
            county=county,
            is_tri_county=is_tri_county,
            is_in_sc=is_in_sc,
            months_until_sol=months_until_sol,
            estimated_case_value=estimated_value,
            injury_type=injury_type,
            qualification_notes=notes,
            strengths=strengths,
            concerns=concerns,
            missing_info=missing_info,
            recommended_questions=questions,
            safety_flags=safety_flags,
            ai_analysis=ai_analysis,
        )

    def _analyze_geography(self, location: Optional[str]) -> tuple[Optional[str], bool, bool]:
        """Extract county and determine geographic eligibility."""
        if not location:
            return None, False, False

        location_lower = location.lower()

        # Try to extract county from common patterns
        county = None

        # Pattern: "County Name County" or "County Name, SC"
        county_pattern = r'\b([a-z]+)\s*county\b'
        match = re.search(county_pattern, location_lower)
        if match:
            county = match.group(1)

        # If no explicit county, try to match city to county
        city_to_county = {
            "charleston": "charleston",
            "north charleston": "charleston",
            "mount pleasant": "charleston",
            "mt pleasant": "charleston",
            "summerville": "dorchester",
            "goose creek": "berkeley",
            "moncks corner": "berkeley",
            "columbia": "richland",
            "greenville": "greenville",
            "spartanburg": "spartanburg",
            "myrtle beach": "horry",
            "florence": "florence",
            "rock hill": "york",
            "anderson": "anderson",
            "hilton head": "beaufort",
        }

        if not county:
            for city, county_name in city_to_county.items():
                if city in location_lower:
                    county = county_name
                    break

        # Check if in SC
        is_in_sc = False
        if county and county in self.config.accepted_counties:
            is_in_sc = True
        elif any(sc_ind in location_lower for sc_ind in [", sc", "south carolina", ", s.c."]):
            is_in_sc = True

        # Check if tri-county (preferred counties)
        is_tri_county = county in self.config.preferred_counties if county else False

        return county, is_tri_county, is_in_sc

    def _calculate_sol_remaining(self, accident_date: Optional[datetime]) -> Optional[int]:
        """Calculate months remaining until statute of limitations expires."""
        if not accident_date:
            return None

        # SOL expiration date
        sol_expiration = accident_date + timedelta(days=self.config.sol_years * 365)
        today = datetime.now()

        if today >= sol_expiration:
            return 0  # Already expired

        # Calculate months remaining
        months = (sol_expiration.year - today.year) * 12 + (sol_expiration.month - today.month)
        return max(0, months)

    def _check_safety_rules(self, lead: Lead) -> list[SafetyFlag]:
        """Check for safety conditions that require special handling."""
        flags = []

        # Combine all text fields for analysis
        all_text = " ".join(filter(None, [
            lead.injury_description,
            lead.medical_treatment,
            lead.liability_notes,
        ])).lower()

        # Check for disputed liability
        for keyword in self.config.disputed_liability_keywords:
            if keyword.lower() in all_text:
                flags.append(SafetyFlag(
                    flag_type="disputed_liability",
                    description=f"Liability may be disputed: found '{keyword}'",
                    severity="review"
                ))
                break

        # Check for insufficient medical treatment
        med_text = (lead.medical_treatment or "").lower()
        if not med_text or med_text.strip() in ["", "none", "n/a"]:
            flags.append(SafetyFlag(
                flag_type="no_medical_treatment",
                description="No medical treatment information provided",
                severity="review"
            ))
        else:
            for keyword in self.config.insufficient_treatment_keywords:
                if keyword.lower() in med_text:
                    flags.append(SafetyFlag(
                        flag_type="insufficient_treatment",
                        description=f"Medical treatment may be insufficient: '{keyword}'",
                        severity="review"
                    ))
                    break

        # Check for minor plaintiff
        minor_indicators = ["minor", "child", "age 17", "age 16", "age 15",
                          "year old", "years old", "minor child", "juvenile"]
        for indicator in minor_indicators:
            if indicator in all_text:
                flags.append(SafetyFlag(
                    flag_type="minor_plaintiff",
                    description="Plaintiff may be a minor - requires special handling",
                    severity="review"
                ))
                break

        # Check for multiple parties
        multi_party_indicators = ["multiple vehicles", "multi-vehicle", "chain reaction",
                                  "three car", "four car", "several parties", "multiple parties"]
        for indicator in multi_party_indicators:
            if indicator in all_text:
                flags.append(SafetyFlag(
                    flag_type="multiple_parties",
                    description="Multiple parties involved - requires review",
                    severity="review"
                ))
                break

        # Check for commercial vehicle
        commercial_indicators = ["commercial", "truck", "18-wheeler", "semi", "tractor-trailer",
                                "delivery van", "box truck", "company vehicle", "fleet"]
        for indicator in commercial_indicators:
            if indicator in all_text:
                flags.append(SafetyFlag(
                    flag_type="commercial_vehicle",
                    description="Commercial vehicle involved - potential higher value case",
                    severity="review"
                ))
                break

        return flags

    def _analyze_medical_treatment(self, lead: Lead) -> tuple[bool, int, str]:
        """Analyze medical treatment to determine if threshold is met."""
        med_text = (lead.medical_treatment or "").lower()
        injury_text = (lead.injury_description or "").lower()
        combined = f"{med_text} {injury_text}"

        details = []
        has_er = any(kw in combined for kw in ["emergency room", "er visit", "emergency department", "ed visit", "hospital"])
        has_ortho = any(kw in combined for kw in ["orthopedic", "orthopaedic", "orthopedist"])
        has_surgery = any(kw in combined for kw in ["surgery", "surgical", "operation"])
        has_followup = any(kw in combined for kw in ["physical therapy", "pt", "chiropractor", "follow-up", "followup", "specialist"])

        if has_er:
            details.append("ER visit documented")
        if has_ortho:
            details.append("Orthopedic care")
        if has_surgery:
            details.append("Surgical intervention")
        if has_followup:
            details.append("Follow-up care documented")

        # Threshold: (ER + ortho/followup) OR surgery
        treatment_met = (has_er and (has_ortho or has_followup)) or has_surgery

        points = self.config.medical_treatment_points if treatment_met else 0
        detail_str = "; ".join(details) if details else "No qualifying treatment documented"

        return treatment_met, points, detail_str

    def _analyze_liability(self, lead: Lead) -> tuple[bool, int, str]:
        """Analyze liability notes to determine if clear liability exists."""
        liability_text = (lead.liability_notes or "").lower()

        if not liability_text.strip():
            return False, 0, "No liability information provided"

        details = []
        clear_liability = False

        # Check for clear liability indicators
        for keyword in self.config.clear_liability_keywords:
            if keyword.lower() in liability_text:
                clear_liability = True
                details.append(f"Clear liability indicator: {keyword}")
                break

        # Check for rear-end specifically (very strong)
        if "rear" in liability_text and "end" in liability_text:
            clear_liability = True
            if "Rear-end collision" not in details:
                details.append("Rear-end collision (presumed liability)")

        # Check for DUI/DWI
        if any(dui in liability_text for dui in ["dui", "dwi", "drunk", "intoxicated", "bac"]):
            clear_liability = True
            details.append("DUI/DWI involved")

        # Check for citation/ticket
        if any(cit in liability_text for cit in ["citation", "ticket", "cited", "ticketed"]):
            clear_liability = True
            details.append("Citation issued to defendant")

        points = self.config.clear_liability_points if clear_liability else 0
        detail_str = "; ".join(details) if details else "Liability unclear or not documented"

        return clear_liability, points, detail_str

    def _analyze_insurance(self, lead: Lead) -> tuple[bool, int]:
        """Check if defendant's insurance carrier is identified."""
        carrier = (lead.insurance_carrier or "").strip().lower()

        if not carrier or carrier in ["", "unknown", "n/a", "none", "tbd"]:
            return False, 0

        if carrier in ["uninsured", "uninsured motorist", "um", "no insurance"]:
            return False, 0  # UM-only cases need review

        return True, self.config.identified_insurance_points

    def _analyze_sol(self, months_remaining: Optional[int]) -> tuple[bool, int]:
        """Check if sufficient time remains on statute of limitations."""
        if months_remaining is None:
            return False, 0  # Can't determine, needs review

        if months_remaining < self.config.min_sol_months_remaining:
            return False, 0  # SOL concern

        # Bonus point if > 24 months
        if months_remaining > 24:
            return True, self.config.sol_buffer_points

        return True, 0

    def _analyze_injury_severity(self, lead: Lead) -> tuple[bool, int, str]:
        """Analyze injury description to determine severity and type."""
        injury_text = (lead.injury_description or "").lower()
        med_text = (lead.medical_treatment or "").lower()
        combined = f"{injury_text} {med_text}"

        # Determine injury type for display
        injury_type = "Soft tissue injuries"  # Default

        injury_type_map = [
            (["fracture", "broken", "break"], "Fracture injuries"),
            (["surgery", "surgical"], "Surgical case"),
            (["traumatic brain", "tbi", "concussion", "head injury"], "Head/Brain injury"),
            (["spinal", "spine", "back injury", "neck injury", "herniated"], "Spinal injuries"),
            (["torn", "rupture", "acl", "mcl", "rotator cuff"], "Torn ligament/tendon"),
            (["whiplash", "strain", "sprain"], "Whiplash/soft tissue"),
        ]

        for keywords, injury_desc in injury_type_map:
            if any(kw in combined for kw in keywords):
                injury_type = injury_desc
                break

        # Check for serious injury indicators
        is_serious = any(kw in combined for kw in self.config.serious_injury_keywords)
        points = self.config.serious_injury_points if is_serious else 0

        return is_serious, points, injury_type

    def _determine_tier(self, score: int, safety_flags: list[SafetyFlag],
                        is_in_sc: bool, sol_adequate: bool) -> QualificationTier:
        """Determine qualification tier based on score and flags."""
        # Auto-decline conditions
        if not is_in_sc:
            return QualificationTier.TIER_3_AUTO_DECLINE

        if not sol_adequate:
            return QualificationTier.TIER_3_AUTO_DECLINE

        # Check for blocking safety flags
        review_flags = [f for f in safety_flags if f.severity in ["block", "review"]]

        # If any review flags, can't auto-accept
        if review_flags and score >= self.config.tier1_threshold:
            return QualificationTier.TIER_2_REVIEW

        # Standard tier determination
        if score >= self.config.tier1_threshold:
            return QualificationTier.TIER_1_AUTO_ACCEPT
        elif score >= self.config.tier2_threshold:
            return QualificationTier.TIER_2_REVIEW
        else:
            return QualificationTier.TIER_3_AUTO_DECLINE

    def _build_analysis_lists(self, lead: Lead, medical_met: bool, liability_met: bool,
                              insurance_met: bool, sol_adequate: bool, serious: bool,
                              is_tri_county: bool, county: Optional[str],
                              medical_details: str, liability_details: str
                              ) -> tuple[list[str], list[str], list[str], list[str]]:
        """Build lists of strengths, concerns, missing info, and questions."""
        strengths = []
        concerns = []
        missing_info = []
        questions = []

        # Strengths
        if medical_met:
            strengths.append(f"Medical treatment threshold met: {medical_details}")
        if liability_met:
            strengths.append(f"Clear liability established: {liability_details}")
        if insurance_met:
            strengths.append(f"Insurance carrier identified: {lead.insurance_carrier}")
        if sol_adequate:
            strengths.append("Statute of limitations adequate")
        if serious:
            strengths.append("Serious injury documented")
        if is_tri_county:
            strengths.append(f"Tri-county area ({county.title() if county else 'Unknown'} County)")

        # Concerns
        if not medical_met:
            concerns.append("Medical treatment may not meet threshold")
        if not liability_met:
            concerns.append("Liability not clearly established")
        if not insurance_met:
            concerns.append("Insurance carrier not identified or UM-only")
        if not sol_adequate:
            concerns.append("Statute of limitations concern")

        # Missing info
        if not lead.accident_date:
            missing_info.append("Accident date not provided")
        if not lead.accident_location:
            missing_info.append("Accident location not provided")
        if not lead.injury_description:
            missing_info.append("Injury description not provided")
        if not lead.medical_treatment:
            missing_info.append("Medical treatment details not provided")
        if not lead.liability_notes:
            missing_info.append("Liability notes not provided")

        # Recommended questions
        if not medical_met:
            questions.append("What medical treatment have you received so far?")
            questions.append("Have you seen an orthopedic specialist or had any imaging (X-ray, MRI)?")
        if not liability_met:
            questions.append("How did the accident occur? Who was at fault?")
            questions.append("Was a police report filed? Were any citations issued?")
        if not insurance_met:
            questions.append("Do you know the at-fault driver's insurance company?")
        if not lead.accident_date:
            questions.append("When did the accident occur?")

        return strengths, concerns, missing_info, questions

    def _estimate_case_value(self, serious: bool, medical_met: bool,
                             liability_met: bool, is_tri_county: bool) -> Optional[float]:
        """Estimate potential case value (rough estimate for prioritization)."""
        if not (medical_met and liability_met):
            return None

        # Very rough estimates for internal prioritization only
        base_value = 25000.0

        if serious:
            base_value = 75000.0

        if is_tri_county:
            base_value *= 1.2  # Charleston area tends to have higher verdicts

        return base_value

    def _get_ai_analysis(self, lead: Lead, score: int, tier: QualificationTier,
                         safety_flags: list[SafetyFlag]) -> Optional[str]:
        """Get Claude AI analysis of the lead."""
        if not self.claude_client:
            return None

        try:
            prompt = f"""Analyze this personal injury lead for a South Carolina law firm. Provide a brief, professional assessment.

Lead Information:
- Name: {lead.name}
- Accident Date: {lead.accident_date.strftime('%Y-%m-%d') if lead.accident_date else 'Not provided'}
- Location: {lead.accident_location or 'Not provided'}
- Injuries: {lead.injury_description or 'Not provided'}
- Medical Treatment: {lead.medical_treatment or 'Not provided'}
- Liability Notes: {lead.liability_notes or 'Not provided'}
- Insurance Carrier: {lead.insurance_carrier or 'Not provided'}

Current Score: {score} points
Qualification Tier: {tier.value}
Safety Flags: {', '.join(f.description for f in safety_flags) if safety_flags else 'None'}

Provide a 2-3 sentence assessment focusing on:
1. Overall case quality and potential
2. Any red flags or concerns not captured in the scoring
3. Recommended next steps for intake

Keep the response concise and actionable for an attorney."""

            message = self.claude_client.messages.create(
                model=self.claude_config.model,
                max_tokens=self.claude_config.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )

            return message.content[0].text

        except Exception as e:
            logger.error(f"Claude AI analysis failed: {e}")
            return None

    def _generate_qualification_notes(self, lead: Lead, tier: QualificationTier,
                                       score: int, strengths: list[str],
                                       concerns: list[str], missing_info: list[str],
                                       questions: list[str], safety_flags: list[SafetyFlag],
                                       ai_analysis: Optional[str]) -> str:
        """Generate comprehensive qualification notes."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if tier == QualificationTier.TIER_1_AUTO_ACCEPT:
            notes = f"Auto-qualified {timestamp}.\n\n"
            notes += f"Score: {score} points\n\n"
            notes += "CRITERIA MET:\n"
            for s in strengths:
                notes += f"  - {s}\n"
            if ai_analysis:
                notes += f"\nAI ASSESSMENT:\n{ai_analysis}\n"
            notes += "\nRecommended intake call within 24 hours."

        elif tier == QualificationTier.TIER_2_REVIEW:
            notes = f"Flagged for review {timestamp}.\n\n"
            notes += f"Score: {score} points\n\n"

            if strengths:
                notes += "STRENGTHS:\n"
                for s in strengths:
                    notes += f"  + {s}\n"
                notes += "\n"

            if concerns:
                notes += "CONCERNS:\n"
                for c in concerns:
                    notes += f"  - {c}\n"
                notes += "\n"

            if safety_flags:
                notes += "SAFETY FLAGS:\n"
                for f in safety_flags:
                    notes += f"  ! {f.description}\n"
                notes += "\n"

            if missing_info:
                notes += "MISSING INFORMATION:\n"
                for m in missing_info:
                    notes += f"  ? {m}\n"
                notes += "\n"

            if questions:
                notes += "RECOMMENDED QUESTIONS:\n"
                for i, q in enumerate(questions, 1):
                    notes += f"  {i}. {q}\n"
                notes += "\n"

            if ai_analysis:
                notes += f"AI ASSESSMENT:\n{ai_analysis}\n"

        else:  # TIER_3_AUTO_DECLINE
            notes = f"Auto-declined {timestamp}.\n\n"
            notes += f"Score: {score} points\n\n"
            notes += "REASONS FOR DECLINE:\n"
            for c in concerns:
                notes += f"  - {c}\n"
            if safety_flags:
                for f in safety_flags:
                    notes += f"  - {f.description}\n"

        return notes


def qualify_lead_fallback(lead: Lead, config: QualificationConfig) -> QualificationResult:
    """Fallback keyword-based qualification when Claude API is unavailable."""
    logger.warning("Using fallback qualification (no AI analysis)")

    # Create qualifier without Claude
    qualifier = LeadQualifier(config, ClaudeConfig())
    result = qualifier.qualify_lead(lead)
    result.ai_analysis = "AI analysis unavailable - using keyword-based scoring only"

    return result


# =============================================================================
# TWO-TIER QUALIFICATION SYSTEM
# =============================================================================

@dataclass
class TwoTierResult:
    """Complete result from two-tier AI qualification."""
    # ChatGPT Tier-1 results
    chatgpt_score: int
    chatgpt_recommendation: str
    chatgpt_analysis: str
    chatgpt_red_flags: list[str]
    chatgpt_confidence: int

    # Claude Tier-2 results (if triggered)
    claude_triggered: bool
    claude_analysis: Optional[str] = None
    claude_case_comparisons: Optional[str] = None
    claude_carrier_strategy: Optional[str] = None
    claude_recommendation: Optional[str] = None
    claude_confidence: Optional[int] = None

    # Final decision
    final_decision: str = ""  # Accept, Decline, Need More Info
    final_confidence: int = 0

    def to_airtable_update(self, status: str) -> TwoTierScoringUpdate:
        """Convert to Airtable update format."""
        return TwoTierScoringUpdate(
            chatgpt_score=self.chatgpt_score,
            chatgpt_analysis=self.chatgpt_analysis,
            chatgpt_red_flags="\n".join(self.chatgpt_red_flags) if self.chatgpt_red_flags else "",
            chatgpt_recommendation=self.chatgpt_recommendation,
            claude_analysis=self.claude_analysis,
            claude_case_comparisons=self.claude_case_comparisons,
            claude_carrier_strategy=self.claude_carrier_strategy,
            final_ai_decision=self.final_decision,
            ai_confidence_level=self.final_confidence,
            status=status,
        )


class TwoTierQualifier:
    """
    Two-tier lead qualification using ChatGPT (Tier-1) and Claude (Tier-2).

    Flow:
    1. ChatGPT analyzes lead and scores 0-100
    2. Based on score and recommendation:
       - FAST-TRACK (75+): Auto-accept, skip Claude
       - CLAUDE-REVIEW (50-74): Escalate to Claude for deep analysis
       - DECLINE (<50): Auto-decline, skip Claude
       - NEED-INFO: Flag for follow-up
    3. If Claude triggered, perform deep analysis with case comparisons
    4. Return combined result
    """

    def __init__(
        self,
        openai_config: OpenAIConfig,
        claude_config: ClaudeConfig,
        drive_config: GoogleDriveConfig,
        thresholds: ScoringThresholds,
    ):
        self.openai_config = openai_config
        self.claude_config = claude_config
        self.drive_config = drive_config
        self.thresholds = thresholds

        # Lazy-loaded components
        self._chatgpt_scorer = None
        self._claude_analyzer = None

    @property
    def chatgpt_scorer(self):
        """Lazy-load ChatGPT scorer."""
        if self._chatgpt_scorer is None:
            from .chatgpt_scorer import ChatGPTScorer
            self._chatgpt_scorer = ChatGPTScorer(self.openai_config, self.thresholds)
        return self._chatgpt_scorer

    @property
    def claude_analyzer(self):
        """Lazy-load Claude analyzer with Drive search."""
        if self._claude_analyzer is None:
            from .claude_analyzer import ClaudeAnalyzer
            from .google_drive_search import create_drive_searcher

            drive_searcher = create_drive_searcher(self.drive_config)
            self._claude_analyzer = ClaudeAnalyzer(self.claude_config, drive_searcher)
        return self._claude_analyzer

    def qualify_lead(self, lead: Lead) -> TwoTierResult:
        """
        Perform two-tier qualification on a lead.

        Returns TwoTierResult with all scoring details.
        """
        logger.info(f"Starting two-tier qualification for: {lead.name}")

        # Step 1: ChatGPT Tier-1 scoring
        from .chatgpt_scorer import Recommendation
        gpt_result = self.chatgpt_scorer.score_lead(lead)

        # Initialize result with Tier-1 data
        result = TwoTierResult(
            chatgpt_score=gpt_result.score,
            chatgpt_recommendation=gpt_result.recommendation.value,
            chatgpt_analysis=gpt_result.analysis,
            chatgpt_red_flags=gpt_result.red_flags,
            chatgpt_confidence=gpt_result.confidence,
            claude_triggered=False,
        )

        # Step 2: Route based on recommendation
        if gpt_result.recommendation == Recommendation.FAST_TRACK:
            logger.info(f"FAST-TRACK: {lead.name} scored {gpt_result.score}/100")
            result.final_decision = "Accept"
            result.final_confidence = gpt_result.confidence

        elif gpt_result.recommendation == Recommendation.CLAUDE_REVIEW:
            logger.info(f"CLAUDE-REVIEW: {lead.name} scored {gpt_result.score}/100 - escalating to Tier-2")
            result.claude_triggered = True

            # Step 3: Claude Tier-2 deep analysis
            claude_result = self.claude_analyzer.analyze_lead(lead, gpt_result)

            result.claude_analysis = claude_result.deep_analysis
            result.claude_case_comparisons = claude_result.case_comparisons
            result.claude_carrier_strategy = claude_result.carrier_strategy
            result.claude_recommendation = claude_result.final_recommendation
            result.claude_confidence = claude_result.confidence

            # Final decision from Claude
            result.final_decision = claude_result.final_recommendation
            result.final_confidence = claude_result.confidence

        elif gpt_result.recommendation == Recommendation.NEED_INFO:
            logger.info(f"NEED-INFO: {lead.name} scored {gpt_result.score}/100 - missing critical data")
            result.final_decision = "Need More Info"
            result.final_confidence = gpt_result.confidence

        else:  # DECLINE
            logger.info(f"DECLINE: {lead.name} scored {gpt_result.score}/100")
            result.final_decision = "Decline"
            result.final_confidence = gpt_result.confidence

        logger.info(f"Two-tier qualification complete for {lead.name}: {result.final_decision}")
        return result

    def get_status_for_decision(self, decision: str) -> str:
        """Map final decision to Airtable status."""
        status_map = {
            "Accept": "Accepted",
            "Decline": "Declined",
            "Need More Info": "Need More Info",
        }
        return status_map.get(decision, "In Review")
