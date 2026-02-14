"""
Main orchestration module for Pflug Law Lead Qualifier.
Coordinates all components and runs the main processing loop.
"""

import logging
import signal
import sys
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

from .config import AppConfig, load_config
from .airtable_client import AirtableClient, Lead, QualificationUpdate
from .clio_client import ClioClient, MatterCreateRequest
from .qualifier import LeadQualifier, QualificationResult, QualificationTier, qualify_lead_fallback
from .email_handler import EmailHandler

logger = logging.getLogger(__name__)


@dataclass
class ProcessedLead:
    """Record of a processed lead for dashboard display."""
    record_id: str
    name: str
    timestamp: datetime
    tier: str
    score: int
    status: str
    injury_type: str
    county: Optional[str]
    clio_matter_url: Optional[str] = None
    error: Optional[str] = None


class ProcessingHistory:
    """Thread-safe history of processed leads."""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._history: list[ProcessedLead] = []
        self._lock = threading.Lock()

    def add(self, lead: ProcessedLead) -> None:
        with self._lock:
            self._history.insert(0, lead)
            if len(self._history) > self.max_size:
                self._history = self._history[:self.max_size]

    def get_recent(self, limit: int = 20) -> list[ProcessedLead]:
        with self._lock:
            return self._history[:limit].copy()

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._history)
            accepted = sum(1 for l in self._history if l.tier == "tier1")
            review = sum(1 for l in self._history if l.tier == "tier2")
            declined = sum(1 for l in self._history if l.tier == "tier3")
            errors = sum(1 for l in self._history if l.error)

            return {
                "total_processed": total,
                "auto_accepted": accepted,
                "needs_review": review,
                "auto_declined": declined,
                "errors": errors,
            }

    def to_json(self) -> str:
        with self._lock:
            return json.dumps([
                {
                    "record_id": l.record_id,
                    "name": l.name,
                    "timestamp": l.timestamp.isoformat(),
                    "tier": l.tier,
                    "score": l.score,
                    "status": l.status,
                    "injury_type": l.injury_type,
                    "county": l.county,
                    "clio_matter_url": l.clio_matter_url,
                    "error": l.error,
                }
                for l in self._history
            ])


# Global history for dashboard access
processing_history = ProcessingHistory()


class LeadProcessor:
    """Main lead processing orchestrator."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.airtable = AirtableClient(config.airtable)
        self.clio = ClioClient(config.clio)
        self.qualifier = LeadQualifier(config.qualification, config.claude)
        self.email = EmailHandler(config.email)
        self._running = False
        self._shutdown_event = threading.Event()

    def test_connections(self) -> dict[str, bool]:
        """Test all API connections."""
        results = {}

        logger.info("Testing Airtable connection...")
        results["airtable"] = self.airtable.test_connection()

        if self.config.clio_enabled:
            logger.info("Testing Clio connection...")
            results["clio"] = self.clio.test_connection()
        else:
            logger.info("Clio: SKIPPED (disabled in starter mode)")
            results["clio"] = None

        if self.config.email_enabled:
            logger.info("Testing Gmail connection...")
            results["gmail"] = self.email.test_connection()
        else:
            logger.info("Gmail: SKIPPED (disabled in starter mode)")
            results["gmail"] = None

        logger.info("Testing Claude API...")
        results["claude"] = self.qualifier.claude_client is not None

        return results

    def process_lead(self, lead: Lead) -> ProcessedLead:
        """Process a single lead through qualification."""
        logger.info(f"Processing lead: {lead.name} ({lead.record_id})")

        try:
            # Qualify the lead
            try:
                result = self.qualifier.qualify_lead(lead)
            except Exception as e:
                logger.warning(f"AI qualification failed, using fallback: {e}")
                result = qualify_lead_fallback(lead, self.config.qualification)

            # Handle based on tier
            clio_url = None

            if result.tier == QualificationTier.TIER_1_AUTO_ACCEPT:
                clio_url = self._handle_tier1(lead, result)
            elif result.tier == QualificationTier.TIER_2_REVIEW:
                self._handle_tier2(lead, result)
            else:
                self._handle_tier3(lead, result)

            # Record success
            processed = ProcessedLead(
                record_id=lead.record_id,
                name=lead.name,
                timestamp=datetime.now(),
                tier=result.tier.value,
                score=result.total_score,
                status=self._tier_to_status(result.tier),
                injury_type=result.injury_type,
                county=result.county,
                clio_matter_url=clio_url,
            )
            processing_history.add(processed)

            logger.info(f"Processed lead {lead.name}: {result.tier.value} (Score: {result.total_score})")
            return processed

        except Exception as e:
            logger.error(f"Error processing lead {lead.name}: {e}", exc_info=True)

            # Mark for review and notify
            self._handle_error(lead, str(e))

            processed = ProcessedLead(
                record_id=lead.record_id,
                name=lead.name,
                timestamp=datetime.now(),
                tier="error",
                score=0,
                status="In Review",
                injury_type="Unknown",
                county=None,
                error=str(e),
            )
            processing_history.add(processed)
            return processed

    def _tier_to_status(self, tier: QualificationTier) -> str:
        """Convert tier to Airtable status."""
        if tier == QualificationTier.TIER_1_AUTO_ACCEPT:
            return "Accepted"
        elif tier == QualificationTier.TIER_2_REVIEW:
            return "In Review"
        else:
            return "Declined"

    def _handle_tier1(self, lead: Lead, result: QualificationResult) -> Optional[str]:
        """Handle Tier 1 (Auto-Accept) lead."""
        logger.info(f"Auto-accepting lead: {lead.name}")

        # Update Airtable
        update = QualificationUpdate(
            status="Accepted",
            qualification_score=result.total_score,
            qualification_notes=result.qualification_notes,
            auto_qualified=True,
            county=result.county,
            estimated_case_value=result.estimated_case_value,
        )

        if not self.airtable.update_lead(lead.record_id, update):
            logger.error(f"Failed to update Airtable for {lead.name}")
            if self.config.email_enabled:
                self.email.send_error_notification(
                    f"Failed to update Airtable for auto-accepted lead",
                    lead
                )

        # Only create Clio matter in Pro mode
        clio_url = None
        if self.config.clio_enabled:
            try:
                matter_request = MatterCreateRequest(
                    client_name=lead.name,
                    matter_description=f"{result.injury_type} - {lead.accident_location or 'Unknown Location'}",
                    injury_type=result.injury_type,
                    accident_location=lead.accident_location or "Unknown",
                    accident_date=lead.accident_date,
                    lead_source=lead.lead_source,
                    phone=lead.phone,
                    email=lead.email,
                )
                matter = self.clio.create_matter(matter_request)
                if matter:
                    clio_url = matter.web_url
                    logger.info(f"Created Clio matter: {matter.matter_id}")
                else:
                    logger.error(f"Failed to create Clio matter for {lead.name}")
                    if self.config.email_enabled:
                        self.email.send_error_notification(
                            f"Auto-accepted but failed to create Clio matter. Please create manually.",
                            lead
                        )
            except Exception as e:
                logger.error(f"Clio API error: {e}")
                if self.config.email_enabled:
                    self.email.send_error_notification(
                        f"Clio API error: {e}. Please create matter manually.",
                        lead
                    )
        else:
            logger.info("Clio integration disabled (starter mode) - skipping matter creation")

        # Only send emails in Pro mode
        if self.config.email_enabled:
            self.email.send_auto_accept_notification(lead, result, clio_url)

        return clio_url

    def _handle_tier2(self, lead: Lead, result: QualificationResult) -> None:
        """Handle Tier 2 (Review) lead."""
        logger.info(f"Flagging lead for review: {lead.name}")

        # Update Airtable
        update = QualificationUpdate(
            status="In Review",
            qualification_score=result.total_score,
            qualification_notes=result.qualification_notes,
            auto_qualified=False,
            county=result.county,
            estimated_case_value=result.estimated_case_value,
        )

        if not self.airtable.update_lead(lead.record_id, update):
            logger.error(f"Failed to update Airtable for {lead.name}")

        # Only send emails in Pro mode
        if self.config.email_enabled:
            self.email.send_review_notification(lead, result)

    def _handle_tier3(self, lead: Lead, result: QualificationResult) -> None:
        """Handle Tier 3 (Auto-Decline) lead."""
        logger.info(f"Auto-declining lead: {lead.name}")

        # Update Airtable
        update = QualificationUpdate(
            status="Declined",
            qualification_score=result.total_score,
            qualification_notes=result.qualification_notes,
            auto_qualified=False,
            county=result.county,
        )

        if not self.airtable.update_lead(lead.record_id, update):
            logger.error(f"Failed to update Airtable for {lead.name}")

        # Only send emails in Pro mode
        if self.config.email_enabled:
            # Send referral email to lead
            if lead.email:
                self.email.send_referral_email(lead)

            # Send notification to attorney
            self.email.send_decline_notification(lead, result)

    def _handle_error(self, lead: Lead, error_message: str) -> None:
        """Handle processing error for a lead."""
        logger.error(f"Error processing {lead.name}: {error_message}")

        # Mark for review in Airtable
        self.airtable.mark_for_review(lead.record_id, error_message)

        # Only send emails in Pro mode
        if self.config.email_enabled:
            self.email.send_error_notification(error_message, lead)

    def process_all_new_leads(self) -> int:
        """Process all new leads in Airtable."""
        try:
            leads = self.airtable.get_new_leads()
            logger.info(f"Found {len(leads)} new leads to process")

            processed_count = 0
            for lead in leads:
                if self._shutdown_event.is_set():
                    logger.info("Shutdown requested, stopping processing")
                    break

                self.process_lead(lead)
                processed_count += 1

                # Small delay between leads to avoid rate limiting
                time.sleep(1)

            return processed_count

        except Exception as e:
            logger.error(f"Error fetching leads: {e}", exc_info=True)
            if self.config.email_enabled:
                self.email.send_error_notification(f"Failed to fetch leads from Airtable: {e}")
            return 0

    def run_daemon(self) -> None:
        """Run the main processing loop as a daemon."""
        self._running = True
        logger.info(f"Starting lead processor daemon (poll interval: {self.config.poll_interval_seconds}s)")

        while self._running and not self._shutdown_event.is_set():
            try:
                logger.debug("Checking for new leads...")
                count = self.process_all_new_leads()
                if count > 0:
                    logger.info(f"Processed {count} leads")

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)

            # Wait for next poll interval (interruptible)
            self._shutdown_event.wait(timeout=self.config.poll_interval_seconds)

        logger.info("Lead processor daemon stopped")

    def stop(self) -> None:
        """Stop the daemon gracefully."""
        logger.info("Stopping lead processor...")
        self._running = False
        self._shutdown_event.set()


def setup_logging(log_dir: str, debug: bool = False) -> None:
    """Configure logging."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if debug else logging.INFO

    # File handler
    file_handler = logging.FileHandler(
        log_path / "qualifier.log",
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    """Main entry point."""
    # Load configuration
    config = load_config()

    # Setup logging
    setup_logging(config.log_dir, config.debug_mode)

    logger.info("=" * 60)
    logger.info("Pflug Law Lead Qualifier Starting")
    logger.info("=" * 60)

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        sys.exit(1)

    # Create processor
    processor = LeadProcessor(config)

    # Test connections
    logger.info("Testing API connections...")
    connection_results = processor.test_connections()

    for service, success in connection_results.items():
        status = "OK" if success else "FAILED"
        logger.info(f"  {service}: {status}")

    if not connection_results.get("airtable"):
        logger.error("Airtable connection failed - cannot continue")
        sys.exit(1)

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        processor.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run daemon
    try:
        processor.run_daemon()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        processor.stop()

    logger.info("Pflug Law Lead Qualifier Stopped")


if __name__ == "__main__":
    main()
