"""
Airtable API client for Pflug Law Lead Qualifier.
Handles reading leads and updating qualification results.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import AirtableConfig

logger = logging.getLogger(__name__)


@dataclass
class Lead:
    """Represents a lead from Airtable Intake Tracker."""
    record_id: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    capture_date: Optional[datetime]
    days_since_capture: Optional[int]
    lead_source: Optional[str]
    lead_summary: Optional[str]  # Lead Information Summary - contains case details
    sentiment_analysis: Optional[str]
    status: str
    created_time: Optional[datetime]

    # These may be extracted from lead_summary or added as separate fields
    accident_date: Optional[datetime] = None
    accident_location: Optional[str] = None
    injury_description: Optional[str] = None
    medical_treatment: Optional[str] = None
    insurance_carrier: Optional[str] = None
    liability_notes: Optional[str] = None

    @classmethod
    def from_airtable_record(cls, record: dict) -> "Lead":
        """Create a Lead from an Airtable API record."""
        fields = record.get("fields", {})

        # Parse capture date
        capture_date = None
        if fields.get("Capture Date"):
            try:
                capture_date = datetime.fromisoformat(fields["Capture Date"])
            except (ValueError, TypeError):
                logger.warning(f"Could not parse capture date: {fields.get('Capture Date')}")

        # Parse created time
        created_time = None
        if record.get("createdTime"):
            try:
                created_time = datetime.fromisoformat(record["createdTime"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Get days since capture
        days_since = None
        if fields.get("Days Since Capture"):
            try:
                days_since = int(fields["Days Since Capture"])
            except (ValueError, TypeError):
                pass

        # Lead Information Summary contains the case details from Smith.ai
        lead_summary = fields.get("Lead Information Summary", "")

        return cls(
            record_id=record["id"],
            name=fields.get("Lead Name", "Unknown"),
            phone=fields.get("Phone Number"),
            email=fields.get("Email Address"),
            capture_date=capture_date,
            days_since_capture=days_since,
            lead_source=fields.get("Lead Source"),
            lead_summary=lead_summary,
            sentiment_analysis=fields.get("Lead Sentiment Analysis"),
            status=fields.get("Case Status", "New Lead"),
            created_time=created_time,
            # Extract from summary or use dedicated fields if they exist
            accident_date=capture_date,  # Use capture date as proxy if no accident date field
            accident_location=fields.get("Accident Location"),
            injury_description=lead_summary,  # Summary contains injury info
            medical_treatment=fields.get("Medical Treatment"),
            insurance_carrier=fields.get("Insurance Carrier"),
            liability_notes=fields.get("Liability Notes"),
        )


@dataclass
class QualificationUpdate:
    """Data structure for updating lead qualification in Airtable (legacy)."""
    status: str  # "Accepted", "In Review", "Declined"
    qualification_score: int
    qualification_notes: str
    auto_qualified: bool = False
    county: Optional[str] = None
    estimated_case_value: Optional[float] = None


@dataclass
class TwoTierScoringUpdate:
    """Data structure for updating two-tier AI scoring fields in Airtable."""
    # ChatGPT Tier-1 fields
    chatgpt_score: int
    chatgpt_analysis: str
    chatgpt_red_flags: str
    chatgpt_recommendation: str  # FAST-TRACK, CLAUDE-REVIEW, DECLINE, NEED-INFO

    # Claude Tier-2 fields (optional, only if triggered)
    claude_analysis: Optional[str] = None
    claude_case_comparisons: Optional[str] = None
    claude_carrier_strategy: Optional[str] = None

    # Final decision fields
    final_ai_decision: Optional[str] = None  # Accept, Decline, Need More Info
    ai_confidence_level: Optional[int] = None

    # Status update
    status: Optional[str] = None  # Accepted, In Review, Declined, Need More Info


class AirtableClient:
    """Client for interacting with Airtable API."""

    def __init__(self, config: AirtableConfig):
        self.config = config
        self.base_url = f"https://api.airtable.com/v0/{config.base_id}/{config.table_id}"

        # Set up session with retry logic
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _headers(self) -> dict:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def get_new_leads(self) -> list[Lead]:
        """Fetch all leads with Case Status = 'New Lead'."""
        leads = []
        offset = None

        while True:
            params = {
                "filterByFormula": "{Case Status} = 'New Lead'",
                "sort[0][field]": "Capture Date",
                "sort[0][direction]": "asc",
            }
            if offset:
                params["offset"] = offset

            try:
                response = self.session.get(
                    self.base_url,
                    headers=self._headers(),
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                for record in data.get("records", []):
                    try:
                        lead = Lead.from_airtable_record(record)
                        leads.append(lead)
                    except Exception as e:
                        logger.error(f"Error parsing lead record {record.get('id')}: {e}")

                offset = data.get("offset")
                if not offset:
                    break

            except requests.RequestException as e:
                logger.error(f"Error fetching leads from Airtable: {e}")
                raise

        logger.info(f"Retrieved {len(leads)} new leads from Airtable")
        return leads

    def get_lead_by_id(self, record_id: str) -> Optional[Lead]:
        """Fetch a specific lead by record ID."""
        try:
            response = self.session.get(
                f"{self.base_url}/{record_id}",
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            return Lead.from_airtable_record(response.json())
        except requests.RequestException as e:
            logger.error(f"Error fetching lead {record_id}: {e}")
            return None

    def update_lead(self, record_id: str, update: QualificationUpdate) -> bool:
        """Update a lead with qualification results."""
        fields = {
            "Status": update.status,
            "Qualification Score": update.qualification_score,
            "Qualification Notes": update.qualification_notes,
            "Auto-Qualified": update.auto_qualified,
        }

        if update.county:
            fields["County"] = update.county

        if update.estimated_case_value is not None:
            fields["Estimated Case Value"] = update.estimated_case_value

        payload = {"fields": fields}

        try:
            response = self.session.patch(
                f"{self.base_url}/{record_id}",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            logger.info(f"Updated lead {record_id} with status: {update.status}")
            return True
        except requests.RequestException as e:
            logger.error(f"Error updating lead {record_id}: {e}")
            return False

    def mark_for_review(self, record_id: str, reason: str) -> bool:
        """Mark a lead for manual review due to processing errors."""
        update = QualificationUpdate(
            status="In Review",
            qualification_score=0,
            qualification_notes=f"Requires manual review - processing error: {reason}",
            auto_qualified=False,
        )
        return self.update_lead(record_id, update)

    def update_two_tier_scoring(self, record_id: str, update: TwoTierScoringUpdate) -> bool:
        """Update a lead with two-tier AI scoring results."""
        fields = {
            # ChatGPT Tier-1 fields
            "ChatGPT_Score": update.chatgpt_score,
            "ChatGPT_Analysis": update.chatgpt_analysis,
            "ChatGPT_Red_Flags": update.chatgpt_red_flags,
            "ChatGPT_Recommendation": update.chatgpt_recommendation,
            "AI_Processed_At": datetime.now().isoformat(),
        }

        # Claude Tier-2 fields (if triggered)
        if update.claude_analysis is not None:
            fields["Claude_Analysis"] = update.claude_analysis
        if update.claude_case_comparisons is not None:
            fields["Claude_Case_Comparisons"] = update.claude_case_comparisons
        if update.claude_carrier_strategy is not None:
            fields["Claude_Carrier_Strategy"] = update.claude_carrier_strategy

        # Final decision fields
        if update.final_ai_decision is not None:
            fields["Final_AI_Decision"] = update.final_ai_decision
        if update.ai_confidence_level is not None:
            fields["AI_Confidence_Level"] = update.ai_confidence_level

        # Status update
        if update.status is not None:
            fields["Status"] = update.status

        payload = {"fields": fields}

        try:
            response = self.session.patch(
                f"{self.base_url}/{record_id}",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            logger.info(f"Updated lead {record_id} with two-tier scoring: {update.final_ai_decision}")
            return True
        except requests.RequestException as e:
            logger.error(f"Error updating lead {record_id} with two-tier scoring: {e}")
            return False

    def test_connection(self) -> bool:
        """Test the Airtable connection."""
        try:
            response = self.session.get(
                self.base_url,
                headers=self._headers(),
                params={"maxRecords": 1},
                timeout=10,
            )
            response.raise_for_status()
            logger.info("Airtable connection test successful")
            return True
        except requests.RequestException as e:
            logger.error(f"Airtable connection test failed: {e}")
            return False

    def get_recent_leads(self, limit: int = 20) -> list[Lead]:
        """Get recent leads for dashboard display (all statuses)."""
        leads = []

        params = {
            "maxRecords": limit,
            "sort[0][field]": "Created Time",
            "sort[0][direction]": "desc",
        }

        try:
            response = self.session.get(
                self.base_url,
                headers=self._headers(),
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            for record in data.get("records", []):
                try:
                    lead = Lead.from_airtable_record(record)
                    leads.append(lead)
                except Exception as e:
                    logger.error(f"Error parsing lead record: {e}")

        except requests.RequestException as e:
            logger.error(f"Error fetching recent leads: {e}")

        return leads
