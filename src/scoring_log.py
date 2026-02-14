"""
Scoring Log Module.
Logs all AI scoring decisions to Airtable for accuracy tracking and analysis.
"""

import logging
from datetime import datetime
from typing import Optional

from pyairtable import Api

from .config import AirtableConfig
from .airtable_client import Lead
from .chatgpt_scorer import ChatGPTScoringResult, Recommendation
from .claude_analyzer import ClaudeAnalysisResult

logger = logging.getLogger(__name__)


class ScoringLogger:
    """Logs AI scoring decisions to Airtable Scoring_Log table."""

    def __init__(self, config: AirtableConfig):
        self.config = config
        self._api: Optional[Api] = None
        self._table = None

    @property
    def api(self) -> Api:
        """Lazy-load Airtable API client."""
        if self._api is None:
            self._api = Api(self.config.api_key)
        return self._api

    @property
    def table(self):
        """Get the Scoring_Log table."""
        if self._table is None:
            if not self.config.scoring_log_table_id:
                logger.warning("Scoring_Log table ID not configured")
                return None
            self._table = self.api.table(
                self.config.base_id,
                self.config.scoring_log_table_id
            )
        return self._table

    def log_scoring(
        self,
        lead: Lead,
        gpt_result: ChatGPTScoringResult,
        claude_result: Optional[ClaudeAnalysisResult],
        final_decision: str
    ) -> Optional[str]:
        """
        Log a scoring decision to the Scoring_Log table.

        Returns the record ID if successful, None otherwise.
        """
        if not self.table:
            logger.warning("Cannot log scoring - table not configured")
            return None

        try:
            # Build the log record
            record = {
                "Lead_Name": lead.name or "Unknown",
                "Timestamp": datetime.now().isoformat(),
                "ChatGPT_Score": gpt_result.score,
                "ChatGPT_Recommendation": gpt_result.recommendation.value,
                "ChatGPT_Confidence": gpt_result.confidence,
                "Claude_Triggered": claude_result is not None,
                "Final_Decision": final_decision,
                "Processing_Details": self._build_processing_details(gpt_result, claude_result),
            }

            # Add link to lead record if available
            if lead.record_id:
                record["Lead_Record"] = [lead.record_id]

            # Add Claude-specific fields if available
            if claude_result:
                record["Claude_Confidence"] = claude_result.confidence
                record["Claude_Recommendation"] = claude_result.final_recommendation
                if claude_result.estimated_value_range:
                    record["Estimated_Value"] = claude_result.estimated_value_range

            # Create the record
            created = self.table.create(record)
            record_id = created.get('id')

            logger.info(f"Logged scoring decision for {lead.name}: {final_decision} (Record: {record_id})")
            return record_id

        except Exception as e:
            logger.error(f"Failed to log scoring decision: {e}")
            return None

    def _build_processing_details(
        self,
        gpt_result: ChatGPTScoringResult,
        claude_result: Optional[ClaudeAnalysisResult]
    ) -> str:
        """Build a detailed processing summary for the log."""
        details = []

        # ChatGPT details
        details.append("=== CHATGPT TIER-1 ===")
        details.append(f"Score: {gpt_result.score}/100")
        details.append(f"Recommendation: {gpt_result.recommendation.value}")
        details.append(f"Confidence: {gpt_result.confidence}%")
        details.append("")
        details.append("Component Scores:")
        details.append(f"  - Incident Type: {gpt_result.incident_type_score}/25")
        details.append(f"  - Injury Severity: {gpt_result.injury_severity_score}/25")
        details.append(f"  - Liability: {gpt_result.liability_score}/20")
        details.append(f"  - Insurance: {gpt_result.insurance_score}/15")
        details.append(f"  - SOL: {gpt_result.sol_score}/10")
        details.append(f"  - Geographic: {gpt_result.geographic_score}/5")
        details.append("")
        details.append(f"Analysis: {gpt_result.analysis}")

        if gpt_result.red_flags:
            details.append("")
            details.append("Red Flags:")
            for flag in gpt_result.red_flags:
                details.append(f"  - {flag}")

        # Claude details if triggered
        if claude_result:
            details.append("")
            details.append("=== CLAUDE TIER-2 ===")
            details.append(f"Final Recommendation: {claude_result.final_recommendation}")
            details.append(f"Confidence: {claude_result.confidence}%")
            if claude_result.estimated_value_range:
                details.append(f"Estimated Value: {claude_result.estimated_value_range}")
            details.append("")
            details.append("Deep Analysis (excerpt):")
            # Truncate long analysis
            analysis_excerpt = claude_result.deep_analysis[:1000]
            if len(claude_result.deep_analysis) > 1000:
                analysis_excerpt += "..."
            details.append(analysis_excerpt)

            if claude_result.missing_gaps:
                details.append("")
                details.append("Information Gaps:")
                for gap in claude_result.missing_gaps:
                    details.append(f"  - {gap}")

        return "\n".join(details)

    def get_recent_logs(self, limit: int = 20) -> list[dict]:
        """Get recent scoring log entries for dashboard display."""
        if not self.table:
            return []

        try:
            records = self.table.all(
                sort=["-Timestamp"],
                max_records=limit
            )
            return [r['fields'] for r in records]
        except Exception as e:
            logger.error(f"Failed to get recent logs: {e}")
            return []

    def get_accuracy_stats(self) -> dict:
        """
        Calculate accuracy statistics from logged decisions.
        Compares Final_Decision with Actual_Outcome (manually filled).
        """
        if not self.table:
            return {"error": "Table not configured"}

        try:
            # Get all records with actual outcomes
            records = self.table.all(
                formula="{Actual_Outcome} != ''"
            )

            if not records:
                return {
                    "total_evaluated": 0,
                    "message": "No records with actual outcomes yet"
                }

            total = len(records)
            correct_predictions = 0
            fast_track_accuracy = {"correct": 0, "total": 0}
            decline_accuracy = {"correct": 0, "total": 0}

            for record in records:
                fields = record['fields']
                decision = fields.get('Final_Decision', '')
                outcome = fields.get('Actual_Outcome', '')

                # Map outcomes to decisions for comparison
                # Actual outcomes: Signed, Declined, No Response
                # Decisions: Accept, Decline, Need More Info

                if decision == 'Accept':
                    fast_track_accuracy['total'] += 1
                    if outcome == 'Signed':
                        correct_predictions += 1
                        fast_track_accuracy['correct'] += 1

                elif decision == 'Decline':
                    decline_accuracy['total'] += 1
                    if outcome in ['Declined', 'No Response']:
                        correct_predictions += 1
                        decline_accuracy['correct'] += 1

            return {
                "total_evaluated": total,
                "overall_accuracy": round(correct_predictions / total * 100, 1) if total > 0 else 0,
                "fast_track_accuracy": round(
                    fast_track_accuracy['correct'] / fast_track_accuracy['total'] * 100, 1
                ) if fast_track_accuracy['total'] > 0 else 0,
                "decline_accuracy": round(
                    decline_accuracy['correct'] / decline_accuracy['total'] * 100, 1
                ) if decline_accuracy['total'] > 0 else 0,
            }

        except Exception as e:
            logger.error(f"Failed to calculate accuracy stats: {e}")
            return {"error": str(e)}
