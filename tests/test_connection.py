#!/usr/bin/env python3
"""
Connection test script for Pflug Law Lead Qualifier.
Tests all API connections before starting the service.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.airtable_client import AirtableClient
from src.clio_client import ClioClient
from src.email_handler import EmailHandler


def test_all_connections():
    """Test all API connections and report results."""
    print("=" * 60)
    print("  Pflug Law Lead Qualifier - Connection Test")
    print("=" * 60)
    print()

    config = load_config()
    all_passed = True

    # Validate configuration
    print("Checking configuration...")
    errors = config.validate()
    if errors:
        print("  Configuration errors:")
        for error in errors:
            print(f"    - {error}")
        all_passed = False
    else:
        print("  Configuration: OK")
    print()

    # Test Airtable
    print("Testing Airtable connection...")
    try:
        airtable = AirtableClient(config.airtable)
        if airtable.test_connection():
            print("  Airtable: OK")

            # Try to fetch leads
            leads = airtable.get_new_leads()
            print(f"  Found {len(leads)} new leads in queue")
        else:
            print("  Airtable: FAILED")
            all_passed = False
    except Exception as e:
        print(f"  Airtable: ERROR - {e}")
        all_passed = False
    print()

    # Test Clio
    print("Testing Clio connection...")
    try:
        clio = ClioClient(config.clio)
        if clio.test_connection():
            print("  Clio: OK")
        else:
            print("  Clio: FAILED")
            all_passed = False
    except Exception as e:
        print(f"  Clio: ERROR - {e}")
        all_passed = False
    print()

    # Test Gmail
    print("Testing Gmail connection...")
    try:
        email = EmailHandler(config.email)
        if email.test_connection():
            print("  Gmail: OK")
        else:
            print("  Gmail: FAILED (credentials may need setup)")
            print("  Run Gmail OAuth flow to authorize the application")
            all_passed = False
    except Exception as e:
        print(f"  Gmail: ERROR - {e}")
        all_passed = False
    print()

    # Test Claude API
    print("Testing Claude API...")
    try:
        import anthropic
        if config.claude.api_key:
            client = anthropic.Anthropic(api_key=config.claude.api_key)
            # Simple test call
            response = client.messages.create(
                model=config.claude.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Say 'test'"}]
            )
            if response.content:
                print("  Claude API: OK")
            else:
                print("  Claude API: FAILED")
                all_passed = False
        else:
            print("  Claude API: SKIPPED (no API key)")
    except Exception as e:
        print(f"  Claude API: ERROR - {e}")
        all_passed = False
    print()

    # Summary
    print("=" * 60)
    if all_passed:
        print("  All connections successful!")
        print("  You can start the service with:")
        print("    systemctl start pflug-qualifier")
        return 0
    else:
        print("  Some connections failed.")
        print("  Please fix the issues above before starting the service.")
        return 1


if __name__ == "__main__":
    sys.exit(test_all_connections())
