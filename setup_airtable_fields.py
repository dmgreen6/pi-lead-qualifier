#!/usr/bin/env python3
"""
Setup script to create new Airtable fields for two-tier AI scoring.
Run this once to add the required fields to your Intake Tracker table
and create the Scoring_Log table.
"""

import os
import sys
import requests
from pathlib import Path

# Load environment variables from .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"\''))

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID")

if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID]):
    print("ERROR: Missing Airtable credentials in .env")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}

# Fields to add to Intake Tracker
INTAKE_TRACKER_FIELDS = [
    {
        "name": "ChatGPT_Score",
        "type": "number",
        "options": {"precision": 0}
    },
    {
        "name": "ChatGPT_Analysis",
        "type": "multilineText"
    },
    {
        "name": "ChatGPT_Red_Flags",
        "type": "multilineText"
    },
    {
        "name": "ChatGPT_Recommendation",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "FAST-TRACK", "color": "greenBright"},
                {"name": "CLAUDE-REVIEW", "color": "yellowBright"},
                {"name": "DECLINE", "color": "redBright"},
                {"name": "NEED-INFO", "color": "orangeBright"},
            ]
        }
    },
    {
        "name": "Claude_Analysis",
        "type": "multilineText"
    },
    {
        "name": "Claude_Case_Comparisons",
        "type": "multilineText"
    },
    {
        "name": "Claude_Carrier_Strategy",
        "type": "multilineText"
    },
    {
        "name": "Final_AI_Decision",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Accept", "color": "greenBright"},
                {"name": "Decline", "color": "redBright"},
                {"name": "Need More Info", "color": "yellowBright"},
            ]
        }
    },
    {
        "name": "AI_Confidence_Level",
        "type": "number",
        "options": {"precision": 0}
    },
    {
        "name": "AI_Processed_At",
        "type": "dateTime",
        "options": {
            "timeZone": "America/New_York",
            "dateFormat": {"name": "local"},
            "timeFormat": {"name": "12hour"}
        }
    },
]

# Scoring_Log table schema
SCORING_LOG_FIELDS = [
    {
        "name": "Lead_Name",
        "type": "singleLineText"
    },
    {
        "name": "Timestamp",
        "type": "dateTime",
        "options": {
            "timeZone": "America/New_York",
            "dateFormat": {"name": "local"},
            "timeFormat": {"name": "12hour"}
        }
    },
    {
        "name": "ChatGPT_Score",
        "type": "number",
        "options": {"precision": 0}
    },
    {
        "name": "ChatGPT_Recommendation",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "FAST-TRACK", "color": "greenBright"},
                {"name": "CLAUDE-REVIEW", "color": "yellowBright"},
                {"name": "DECLINE", "color": "redBright"},
                {"name": "NEED-INFO", "color": "orangeBright"},
            ]
        }
    },
    {
        "name": "ChatGPT_Confidence",
        "type": "number",
        "options": {"precision": 0}
    },
    {
        "name": "Claude_Triggered",
        "type": "checkbox",
        "options": {"icon": "check", "color": "greenBright"}
    },
    {
        "name": "Claude_Confidence",
        "type": "number",
        "options": {"precision": 0}
    },
    {
        "name": "Claude_Recommendation",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Accept", "color": "greenBright"},
                {"name": "Decline", "color": "redBright"},
                {"name": "Need More Info", "color": "yellowBright"},
            ]
        }
    },
    {
        "name": "Final_Decision",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Accept", "color": "greenBright"},
                {"name": "Decline", "color": "redBright"},
                {"name": "Need More Info", "color": "yellowBright"},
            ]
        }
    },
    {
        "name": "Actual_Outcome",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Signed", "color": "greenBright"},
                {"name": "Declined", "color": "redBright"},
                {"name": "No Response", "color": "grayBright"},
            ]
        }
    },
    {
        "name": "Estimated_Value",
        "type": "singleLineText"
    },
    {
        "name": "Case_Value",
        "type": "currency",
        "options": {"precision": 2, "symbol": "$"}
    },
    {
        "name": "Processing_Details",
        "type": "multilineText"
    },
    {
        "name": "Accuracy_Notes",
        "type": "multilineText"
    },
]


def add_field_to_table(table_id: str, field_config: dict) -> bool:
    """Add a single field to a table."""
    url = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables/{table_id}/fields"

    response = requests.post(url, headers=HEADERS, json=field_config)

    if response.status_code == 200:
        print(f"  ✓ Created field: {field_config['name']}")
        return True
    elif response.status_code == 422 and "DUPLICATE_FIELD_NAME" in response.text:
        print(f"  - Field already exists: {field_config['name']}")
        return True
    else:
        print(f"  ✗ Failed to create {field_config['name']}: {response.status_code}")
        print(f"    {response.text}")
        return False


def create_table(table_name: str, fields: list) -> str:
    """Create a new table with specified fields."""
    url = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"

    # Need at least one field to create a table - use first field
    payload = {
        "name": table_name,
        "fields": fields[:1]  # Create with first field
    }

    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code == 200:
        table_id = response.json()["id"]
        print(f"✓ Created table: {table_name} (ID: {table_id})")
        return table_id
    elif response.status_code == 422 and "DUPLICATE_TABLE_NAME" in response.text:
        print(f"- Table already exists: {table_name}")
        # Get the existing table ID
        tables_url = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"
        tables_response = requests.get(tables_url, headers=HEADERS)
        if tables_response.status_code == 200:
            for table in tables_response.json().get("tables", []):
                if table["name"] == table_name:
                    return table["id"]
        return None
    else:
        print(f"✗ Failed to create table {table_name}: {response.status_code}")
        print(f"  {response.text}")
        return None


def main():
    print("=" * 60)
    print("AIRTABLE SETUP FOR TWO-TIER AI SCORING")
    print("=" * 60)

    # Step 1: Add fields to Intake Tracker
    print(f"\n1. Adding fields to Intake Tracker table ({AIRTABLE_TABLE_ID})...")
    for field in INTAKE_TRACKER_FIELDS:
        add_field_to_table(AIRTABLE_TABLE_ID, field)

    # Step 2: Create Scoring_Log table
    print(f"\n2. Creating Scoring_Log table...")
    scoring_log_id = create_table("Scoring_Log", SCORING_LOG_FIELDS)

    if scoring_log_id:
        # Add remaining fields to Scoring_Log
        print(f"\n3. Adding fields to Scoring_Log table...")
        for field in SCORING_LOG_FIELDS[1:]:  # Skip first field (already created)
            add_field_to_table(scoring_log_id, field)

        # Create linked record field to Intake Tracker
        print(f"\n4. Creating link to Intake Tracker...")
        link_field = {
            "name": "Lead_Record",
            "type": "multipleRecordLinks",
            "options": {
                "linkedTableId": AIRTABLE_TABLE_ID
            }
        }
        add_field_to_table(scoring_log_id, link_field)

        print(f"\n" + "=" * 60)
        print("SETUP COMPLETE!")
        print("=" * 60)
        print(f"\nScoring_Log Table ID: {scoring_log_id}")
        print(f"\nAdd this to your .env file:")
        print(f"AIRTABLE_SCORING_LOG_TABLE_ID={scoring_log_id}")
    else:
        print("\n⚠ Could not create or find Scoring_Log table")
        print("You may need to create it manually in Airtable")


if __name__ == "__main__":
    main()
