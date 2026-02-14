"""
ChatGPT Tier-1 Lead Scoring Engine.
Uses GPT-4 for initial lead qualification with 0-100 scoring.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from openai import OpenAI

from .config import OpenAIConfig, ScoringThresholds
from .airtable_client import Lead

logger = logging.getLogger(__name__)


class Recommendation(Enum):
    """ChatGPT scoring recommendations."""
    FAST_TRACK = "FAST-TRACK"
    CLAUDE_REVIEW = "CLAUDE-REVIEW"
    DECLINE = "DECLINE"
    NEED_INFO = "NEED-INFO"


@dataclass
class ChatGPTScoringResult:
    """Result from ChatGPT Tier-1 scoring."""
    score: int  # 0-100
    recommendation: Recommendation
    analysis: str
    red_flags: list[str]
    confidence: int  # 0-100

    # Component scores for transparency
    incident_type_score: int
    injury_severity_score: int
    liability_score: int
    insurance_score: int
    sol_score: int
    geographic_score: int

    raw_response: Optional[str] = None


SCORING_PROMPT = """You are a lead qualification specialist for a personal injury law firm in South Carolina.
Analyze the following lead and provide a qualification score from 0-100.

SCORING CRITERIA (100 points total):

1. INCIDENT TYPE (25 points max):
   - Motor Vehicle Accident (MVA): 25 points
   - Commercial vehicle/18-wheeler: 25 points
   - Motorcycle accident: 22 points
   - Premises liability (slip/fall): 15 points
   - Dog bite: 10 points
   - Other/unclear: 5 points

2. INJURY SEVERITY (25 points max):
   - Surgery required/performed: 25 points
   - Permanent injury/disability: 25 points
   - Fracture/broken bone: 20 points
   - Herniated/bulging disc: 18 points
   - TBI/concussion: 18 points
   - Torn ligament/tendon: 15 points
   - Soft tissue only: 5 points
   - Unknown/not specified: 0 points

3. LIABILITY CLARITY (20 points max):
   - Rear-end collision (presumed liability): 20 points
   - DUI/DWI involved: 20 points
   - Citation issued to defendant: 20 points
   - Clear fault documented: 15 points
   - Fault appears clear from description: 12 points
   - Disputed/comparative fault: 5 points
   - Unknown/not documented: 0 points

4. INSURANCE COVERAGE (15 points max):
   - Policy limits known and adequate (>$50K): 15 points
   - Insurance carrier identified: 10 points
   - Unknown carrier: 0 points
   - Uninsured motorist only: 5 points

5. STATUTE OF LIMITATIONS (10 points max):
   - More than 24 months remaining: 10 points
   - 18-24 months remaining: 7 points
   - 12-18 months remaining: 3 points
   - Less than 12 months: 0 points
   - Cannot determine: 0 points

6. GEOGRAPHIC (5 points max):
   - Tri-county area (Charleston, Berkeley, Dorchester): 5 points
   - Other South Carolina county: 3 points
   - Out of state: 0 points

LEAD INFORMATION:
{lead_data}

Respond with a JSON object (no markdown, just pure JSON):
{{
    "score": <0-100>,
    "recommendation": "<FAST-TRACK|CLAUDE-REVIEW|DECLINE|NEED-INFO>",
    "analysis": "<2-3 sentence assessment>",
    "red_flags": ["<list of concerns>"],
    "confidence": <0-100>,
    "component_scores": {{
        "incident_type": <0-25>,
        "injury_severity": <0-25>,
        "liability": <0-20>,
        "insurance": <0-15>,
        "sol": <0-10>,
        "geographic": <0-5>
    }},
    "missing_information": ["<list of critical missing data>"]
}}

RECOMMENDATION LOGIC:
- FAST-TRACK (score >= 75): High-value case with clear merit. Auto-accept.
- CLAUDE-REVIEW (score 50-74): Promising but needs deeper analysis of nuances.
- NEED-INFO (score 25-49 AND missing critical information): Cannot properly assess without more data.
- DECLINE (score < 50 without data gaps, OR score < 25): Low viability case.

Be conservative. Only FAST-TRACK truly excellent cases. When in doubt, recommend CLAUDE-REVIEW."""


class ChatGPTScorer:
    """Tier-1 lead scoring using ChatGPT-4."""

    def __init__(self, config: OpenAIConfig, thresholds: ScoringThresholds):
        self.config = config
        self.thresholds = thresholds
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        """Lazy-load OpenAI client."""
        if self._client is None:
            self._client = OpenAI(api_key=self.config.api_key)
        return self._client

    def score_lead(self, lead: Lead) -> ChatGPTScoringResult:
        """Score a lead using ChatGPT-4."""
        logger.info(f"ChatGPT Tier-1 scoring lead: {lead.name} (ID: {lead.record_id})")

        # Format lead data for the prompt
        lead_data = self._format_lead_data(lead)

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=0.3,  # Lower temperature for more consistent scoring
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert legal intake specialist. Respond only with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": SCORING_PROMPT.format(lead_data=lead_data)
                    }
                ]
            )

            raw_response = response.choices[0].message.content
            result = self._parse_response(raw_response, lead)
            result.raw_response = raw_response

            logger.info(f"ChatGPT scored {lead.name}: {result.score}/100 -> {result.recommendation.value}")
            return result

        except Exception as e:
            logger.error(f"ChatGPT scoring failed for {lead.name}: {e}")
            # Return a conservative result on failure
            return ChatGPTScoringResult(
                score=0,
                recommendation=Recommendation.CLAUDE_REVIEW,
                analysis=f"ChatGPT scoring failed: {str(e)}. Escalating to Claude for manual review.",
                red_flags=["API Error - scoring failed"],
                confidence=0,
                incident_type_score=0,
                injury_severity_score=0,
                liability_score=0,
                insurance_score=0,
                sol_score=0,
                geographic_score=0,
                raw_response=None
            )

    def _format_lead_data(self, lead: Lead) -> str:
        """Format lead data for the ChatGPT prompt."""
        # Calculate days since incident if date is available
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

    def _parse_response(self, raw_response: str, lead: Lead) -> ChatGPTScoringResult:
        """Parse ChatGPT JSON response into structured result."""
        try:
            # Clean up response (remove markdown code blocks if present)
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            # Extract component scores
            components = data.get("component_scores", {})

            # Determine recommendation
            score = int(data.get("score", 0))
            rec_str = data.get("recommendation", "CLAUDE-REVIEW").upper()
            missing_info = data.get("missing_information", [])

            # Apply threshold logic
            recommendation = self._determine_recommendation(score, rec_str, missing_info)

            return ChatGPTScoringResult(
                score=score,
                recommendation=recommendation,
                analysis=data.get("analysis", "No analysis provided"),
                red_flags=data.get("red_flags", []),
                confidence=int(data.get("confidence", 50)),
                incident_type_score=int(components.get("incident_type", 0)),
                injury_severity_score=int(components.get("injury_severity", 0)),
                liability_score=int(components.get("liability", 0)),
                insurance_score=int(components.get("insurance", 0)),
                sol_score=int(components.get("sol", 0)),
                geographic_score=int(components.get("geographic", 0)),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ChatGPT response: {e}")
            logger.debug(f"Raw response: {raw_response}")

            # Return conservative result
            return ChatGPTScoringResult(
                score=0,
                recommendation=Recommendation.CLAUDE_REVIEW,
                analysis="Failed to parse scoring response. Escalating to Claude.",
                red_flags=["Parse error - response was not valid JSON"],
                confidence=0,
                incident_type_score=0,
                injury_severity_score=0,
                liability_score=0,
                insurance_score=0,
                sol_score=0,
                geographic_score=0,
            )

    def _determine_recommendation(
        self,
        score: int,
        gpt_recommendation: str,
        missing_info: list[str]
    ) -> Recommendation:
        """Apply threshold logic to determine final recommendation."""
        # Use configured thresholds
        if score >= self.thresholds.fast_track:
            return Recommendation.FAST_TRACK
        elif score >= self.thresholds.claude_review:
            return Recommendation.CLAUDE_REVIEW
        elif score >= self.thresholds.need_info and len(missing_info) > 0:
            return Recommendation.NEED_INFO
        else:
            # Check if GPT specifically recommended NEED-INFO due to missing data
            if gpt_recommendation == "NEED-INFO" and len(missing_info) > 0:
                return Recommendation.NEED_INFO
            return Recommendation.DECLINE
