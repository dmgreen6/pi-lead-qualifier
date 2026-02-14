#!/usr/bin/env python3
"""Test Google Drive OAuth2 authentication."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config
from src.google_drive_search import GoogleDriveSearcher

print("Testing Google Drive connection...")
print("A browser window will open for authorization.\n")

config = load_config()
searcher = GoogleDriveSearcher(config.google_drive)

# This will trigger OAuth flow
service = searcher.service

if service:
    print("\n✓ Google Drive connected successfully!")

    # Test search
    print("\nSearching for 'settlement' in your Drive...")
    results = searcher.search(["settlement", "personal injury"], max_results=3)

    if results:
        print(f"\nFound {len(results)} matching files:")
        for r in results:
            print(f"  - {r.file_name}")
            print(f"    Link: {r.web_link}")
    else:
        print("\nNo matching files found (this is OK - Drive search is working)")
else:
    print("\n✗ Failed to connect to Google Drive")
