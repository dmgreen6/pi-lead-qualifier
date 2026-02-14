#!/usr/bin/env python3
"""
Local development runner for Pflug Law Lead Qualifier.
Runs both the main processor and dashboard in separate threads.
"""

import os
import sys
import threading
import logging
from pathlib import Path

# Ensure we're in the right directory
os.chdir(Path(__file__).parent)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Check for .env file - if not found, launch setup wizard
if not Path(".env").exists():
    print("No configuration found. Please run the setup wizard first.")
    print("Starting wizard at http://localhost:8080")
    from setup.app import app as setup_app
    setup_app.run(port=8080)
    sys.exit(0)

from src.config import load_config, AppConfig
from src.main import LeadProcessor, setup_logging, processing_history
from src.dashboard import app


def run_dashboard(config: AppConfig):
    """Run the Flask dashboard."""
    app.run(
        host=config.dashboard_host,
        port=config.dashboard_port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


def main():
    """Main entry point for local development."""
    # Load configuration
    config = load_config()

    # Override log directory for local development
    config.log_dir = str(Path(__file__).parent / "logs")

    # Setup logging
    setup_logging(config.log_dir, debug=True)

    logger = logging.getLogger(__name__)
    logger.info("Starting Pflug Lead Qualifier in local development mode")

    # Validate configuration
    errors = config.validate()
    if errors:
        logger.error("Configuration errors found:")
        for error in errors:
            logger.error(f"  - {error}")
        print("\nPlease copy .env.template to .env and fill in your API keys.")
        sys.exit(1)

    # Create processor
    processor = LeadProcessor(config)

    # Test connections
    print("\nTesting API connections...")
    results = processor.test_connections()

    for service, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {service}: {status}")

    if not results.get("airtable"):
        print("\nAirtable connection failed - cannot continue")
        sys.exit(1)

    print()

    # Start dashboard in background thread
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        args=(config,),
        daemon=True,
    )
    dashboard_thread.start()

    print(f"Dashboard running at http://{config.dashboard_host}:{config.dashboard_port}")
    print("Press Ctrl+C to stop\n")

    # Run processor in main thread
    try:
        processor.run_daemon()
    except KeyboardInterrupt:
        print("\nStopping...")
        processor.stop()


if __name__ == "__main__":
    main()
