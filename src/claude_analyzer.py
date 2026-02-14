"""
Claude Sonnet Tier-2 Deep Analysis Engine.
Performs comprehensive case analysis when ChatGPT flags CLAUDE-REVIEW.
Includes Google Drive case comparison search.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import anthropic

from .config import ClaudeConfig
from .airtable_client import Lead
from .chatgpt_scorer import ChatGPTScoringResult
from .google_drive_search import GoogleDriveSearcher, CaseMatch

logger = logging.getLogger(__name__)


@dataclass
class ClaudeAnalysisResult:
    """Result from Claude Tier-2 deep analysis."""
    deep_analysis: str
    case_comparisons: str
    carrier_strategy: str
    missing_gaps: list[str]
    recommended_questions: list[str]
    final_recommendation: str  # "Accept", "Decline", "Need More Info"
    confidence: int  # 0-100
    estimated_value_range: Optional[str] = None
    negotiation_notes: Optional[str] = None
    raw_response: Optional[str] = None


# Insurance carrier intelligence database
CARRIER_INTELLIGENCE = {
    "state farm": {
        "tendency": "moderate",
        "notes": "Generally reasonable but slow. Expect 60-day response times. Often settles at 70-80% of demand.",
        "litigation_likelihood": "low"
    },
    "geico": {
        "tendency": "aggressive",
        "notes": "Known for lowball offers. Initial offers typically 40-50% of demand. Be prepared to litigate.",
        "litigation_likelihood": "high"
    },
    "allstate": {
        "tendency": "aggressive",
        "notes": "Boxing gloves mentality. Low initial offers. Recommend strong demand with litigation threat.",
        "litigation_likelihood": "high"
    },
    "usaa": {
        "tendency": "fair",
        "notes": "Generally fair and professional. Often settles reasonably. Good faith negotiators.",
        "litigation_likelihood": "low"
    },
    "progressive": {
        "tendency": "moderate",
        "notes": "Varies by adjuster. Document everything. Mid-range settlement tendency.",
        "litigation_likelihood": "moderate"
    },
    "nationwide": {
        "tendency": "moderate",
        "notes": "Professional but firm. Expect negotiations. Usually settles before trial.",
        "litigation_likelihood": "moderate"
    },
    "liberty mutual": {
        "tendency": "aggressive",
        "notes": "Corporate defense mindset. Low offers. May require litigation to get fair value.",
        "litigation_likelihood": "high"
    },
    "farmers": {
        "tendency": "moderate",
        "notes": "Reasonable in clear liability cases. Can be difficult in disputed liability.",
        "litigation_likelihood": "moderate"
    },
}


CLAUDE_ANALYSIS_PROMPT = """You are a senior personal injury attorney analyzing a case that was flagged for deep review.
The case has already been scored by an initial AI system. Your job is to provide deeper analysis.

INITIAL CHATGPT SCORING:
- Score: {gpt_score}/100
- Recommendation: {gpt_recommendation}
- Initial Analysis: {gpt_analysis}
- Red Flags Identified: {gpt_red_flags}

LEAD INFORMATION:
{lead_data}

SIMILAR PRIOR CASES FROM FIRM FILES:
{case_comparisons}

INSURANCE CARRIER INTELLIGENCE:
{carrier_intel}

Provide a comprehensive analysis addressing:

1. DEEP CASE ANALYSIS
   - Assess the true merit of this case beyond the initial scoring
   - Identify any factors the initial scoring may have missed
   - Consider venue-specific factors (South Carolina law, local jury tendencies)

2. CASE COMPARISONS
   - How does this compare to similar cases in the firm's history?
   - What settlement range is realistic based on comparables?
   - What factors differentiate this case (better or worse)?

3. INSURANCE CARRIER STRATEGY
   - Based on the carrier's known patterns, what approach is recommended?
   - Timeline expectations for this carrier
   - Litigation probability assessment

4. INFORMATION GAPS
   - What critical information is missing?
   - What documents should be requested immediately?
   - What questions should be asked in the intake call?

5. FINAL RECOMMENDATION
   - Accept: Case has sufficient merit to pursue
   - Decline: Case does not meet firm criteria
   - Need More Info: Cannot make decision without additional information

Respond with JSON (no markdown):
{{
    "deep_analysis": "<comprehensive 3-4 paragraph analysis>",
    "case_comparisons": "<summary of how this compares to similar cases>",
    "carrier_strategy": "<recommended approach for this insurance carrier>",
    "missing_gaps": ["<list of missing critical information>"],
    "recommended_questions": ["<specific questions for intake call>"],
    "final_recommendation": "<Accept|Decline|Need More Info>",
    "confidence": <0-100>,
    "estimated_value_range": "<e.g., $25,000 - $50,000>",
    "negotiation_notes": "<specific negotiation strategy recommendations>"
}}"""


class ClaudeAnalyzer:
    """Tier-2 deep analysis using Claude Sonnet."""

    def __init__(self, config: ClaudeConfig, drive_searcher: Optional[GoogleDriveSearcher] = None):
        self.config = config
        self.drive_searcher = drive_searcher
        self._client: Optional[anthropic.Anthropic] = None

    @property
    def client(self) -> anthropic.Anthropic:
        """Lazy-load Anthropic client."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.config.api_key)
        return self._client

    def analyze_lead(
        self,
        lead: Lead,
        gpt_result: ChatGPTScoringResult
    ) -> ClaudeAnalysisResult:
        """Perform deep analysis on a lead flagged for Claude review."""
        logger.info(f"Claude Tier-2 analyzing lead: {lead.name} (ID: {lead.record_id})")

        # Search for similar cases in Google Drive
        case_comparisons = self._search_similar_cases(lead)

        # Get carrier intelligence
        carrier_intel = self._get_carrier_intelligence(lead.insurance_carrier)

        # Format the prompt
        prompt = CLAUDE_ANALYSIS_PROMPT.format(
            gpt_score=gpt_result.score,
            gpt_recommendation=gpt_result.recommendation.value,
            gpt_analysis=gpt_result.analysis,
            gpt_red_flags=", ".join(gpt_result.red_flags) if gpt_result.red_flags else "None",
            lead_data=self._format_lead_data(lead),
            case_comparisons=case_comparisons,
            carrier_intel=carrier_intel
        )

        try:
            message = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            raw_response = message.content[0].text
            result = self._parse_response(raw_response)
            result.raw_response = raw_response

            logger.info(f"Claude analysis complete for {lead.name}: {result.final_recommendation}")
            return result

        except Exception as e:
            logger.error(f"Claude analysis failed for {lead.name}: {e}")
            return ClaudeAnalysisResult(
                deep_analysis=f"Claude analysis failed: {str(e)}",
                case_comparisons="Unable to retrieve case comparisons due to API error.",
                carrier_strategy="Manual review required.",
                missing_gaps=["Unable to complete analysis"],
                recommended_questions=[],
                final_recommendation="Need More Info",
                confidence=0,
                raw_response=None
            )

    def _search_similar_cases(self, lead: Lead) -> str:
        """Search Google Drive for similar prior cases."""
        if not self.drive_searcher:
            return "Google Drive search not configured. No case comparisons available."

        try:
            # Build search keywords from lead
            keywords = []

            # Add injury type keywords
            if lead.injury_description:
                injury_lower = lead.injury_description.lower()
                if any(kw in injury_lower for kw in ["fracture", "broken"]):
                    keywords.append("fracture")
                if any(kw in injury_lower for kw in ["surgery", "surgical"]):
                    keywords.append("surgery")
                if any(kw in injury_lower for kw in ["herniated", "disc", "bulging"]):
                    keywords.append("herniated disc")
                if any(kw in injury_lower for kw in ["tbi", "concussion", "brain"]):
                    keywords.append("TBI")

            # Add incident type
            if lead.liability_notes:
                liability_lower = lead.liability_notes.lower()
                if "rear" in liability_lower and "end" in liability_lower:
                    keywords.append("rear-end")
                if any(kw in liability_lower for kw in ["slip", "fall", "premises"]):
                    keywords.append("premises liability")

            # Add insurance carrier
            if lead.insurance_carrier:
                keywords.append(lead.insurance_carrier)

            # Add location
            if lead.accident_location:
                keywords.append(lead.accident_location)

            if not keywords:
                keywords = ["settlement", "personal injury"]

            # Search Drive
            matches = self.drive_searcher.search(keywords, max_results=5)

            if not matches:
                return "No similar cases found in firm files."

            # Format matches
            formatted = []
            for match in matches:
                formatted.append(f"- {match.file_name}: {match.snippet}")

            return "\n".join(formatted)

        except Exception as e:
            logger.error(f"Google Drive search failed: {e}")
            return f"Drive search error: {str(e)}"

    def _get_carrier_intelligence(self, carrier: Optional[str]) -> str:
        """Get intelligence about the insurance carrier."""
        if not carrier:
            return "Insurance carrier not identified. Cannot provide carrier-specific strategy."

        carrier_lower = carrier.lower().strip()

        # Look for matches in our database
        for known_carrier, intel in CARRIER_INTELLIGENCE.items():
            if known_carrier in carrier_lower or carrier_lower in known_carrier:
                return f"""
Carrier: {carrier}
Settlement Tendency: {intel['tendency']}
Litigation Likelihood: {intel['litigation_likelihood']}
Notes: {intel['notes']}
"""

        return f"Carrier '{carrier}' not in intelligence database. Use standard negotiation approach."

    def _format_lead_data(self, lead: Lead) -> str:
        """Format lead data for Claude prompt."""
        days_since = None
        if lead.accident_date:
            days_since = (datetime.now() - lead.accident_date).days

        return f"""
Name: {lead.name or 'Not provided'}
Phone: {lead.phone or 'Not provided'}
Email: {lead.email or 'Not provided'}

Accident Date: {lead.accident_date.strftime('%Y-%m-%d') if lead.accident_date else 'Not provided'}
Days Since Incident: {days_since if days_since else 'Cannot calculate'}
Accident Location: {lead.accident_location or 'Not provided'}

Injury Description: {lead.injury_description or 'Not provided'}
Medical Treatment: {lead.medical_treatment or 'Not provided'}

Liability Notes: {lead.liability_notes or 'Not provided'}
Insurance Carrier: {lead.insurance_carrier or 'Not provided'}

Lead Source: {lead.lead_source or 'Not provided'}
"""

    def _parse_response(self, raw_response: str) -> ClaudeAnalysisResult:
        """Parse Claude JSON response."""
        try:
            # Clean up response
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            return ClaudeAnalysisResult(
                deep_analysis=data.get("deep_analysis", "No analysis provided"),
                case_comparisons=data.get("case_comparisons", "No comparisons available"),
                carrier_strategy=data.get("carrier_strategy", "Standard approach recommended"),
                missing_gaps=data.get("missing_gaps", []),
                recommended_questions=data.get("recommended_questions", []),
                final_recommendation=data.get("final_recommendation", "Need More Info"),
                confidence=int(data.get("confidence", 50)),
                estimated_value_range=data.get("estimated_value_range"),
                negotiation_notes=data.get("negotiation_notes"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            logger.debug(f"Raw response: {raw_response}")

            # Try to extract what we can from non-JSON response
            return ClaudeAnalysisResult(
                deep_analysis=raw_response[:2000] if raw_response else "Parse error",
                case_comparisons="Unable to parse structured response",
                carrier_strategy="Manual review required",
                missing_gaps=["Response parsing failed"],
                recommended_questions=[],
                final_recommendation="Need More Info",
                confidence=0,
            )
