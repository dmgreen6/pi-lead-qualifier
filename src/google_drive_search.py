"""
Google Drive Search Integration.
Searches firm files for similar prior cases to aid in case valuation.
Supports OAuth2 authentication for personal/workspace accounts.
"""

import io
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .config import GoogleDriveConfig

logger = logging.getLogger(__name__)


# Scopes required for Drive API
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
]


@dataclass
class CaseMatch:
    """A matching case file from Google Drive."""
    file_id: str
    file_name: str
    file_type: str
    web_link: str
    snippet: str  # Relevant text snippet
    relevance_score: float


class GoogleDriveSearcher:
    """Search Google Drive for similar prior cases."""

    def __init__(self, config: GoogleDriveConfig):
        self.config = config
        self._service = None
        # Token file stores the user's access and refresh tokens
        self._token_file = Path(config.credentials_file).parent / "google_drive_token.json"

    @property
    def service(self):
        """Lazy-load Drive API service."""
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def _build_service(self):
        """Build the Google Drive API service using OAuth2."""
        creds_path = Path(self.config.credentials_file)

        if not creds_path.exists():
            logger.warning(f"Google Drive credentials not found at {creds_path}")
            return None

        creds = None

        # Check if we have saved credentials
        if self._token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self._token_file), SCOPES)
            except Exception as e:
                logger.warning(f"Could not load saved credentials: {e}")

        # If no valid credentials, need to authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Could not refresh credentials: {e}")
                    creds = None

            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path), SCOPES
                    )
                    creds = flow.run_local_server(port=8090)

                    # Save credentials for next run
                    with open(self._token_file, 'w') as token:
                        token.write(creds.to_json())
                    logger.info(f"Saved Drive credentials to {self._token_file}")

                except Exception as e:
                    logger.error(f"Failed to authenticate with Google Drive: {e}")
                    return None

        try:
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            logger.error(f"Failed to build Drive service: {e}")
            return None

    def search(self, keywords: list[str], max_results: int = 5) -> list[CaseMatch]:
        """
        Search Google Drive for files matching keywords.

        Args:
            keywords: List of search terms (injury type, carrier, location, etc.)
            max_results: Maximum number of results to return

        Returns:
            List of CaseMatch objects with relevant file information
        """
        if not self.service:
            logger.warning("Drive service not available - skipping search")
            return []

        if not keywords:
            return []

        try:
            # Build the search query
            # Drive API uses fullText contains for content search
            query_parts = []

            for keyword in keywords:
                # Escape single quotes in keywords
                escaped = keyword.replace("'", "\\'")
                query_parts.append(f"fullText contains '{escaped}'")

            # Combine with OR for broader matches
            search_query = " or ".join(query_parts)

            # Exclude folders and trashed files
            search_query = f"({search_query}) and mimeType != 'application/vnd.google-apps.folder' and trashed = false"

            # Add folder restriction if configured
            if self.config.folder_id:
                search_query += f" and '{self.config.folder_id}' in parents"

            logger.debug(f"Drive search query: {search_query}")

            # Execute search
            results = self.service.files().list(
                q=search_query,
                pageSize=max_results,
                fields="files(id, name, mimeType, webViewLink, description)",
                orderBy="modifiedTime desc"
            ).execute()

            files = results.get('files', [])

            if not files:
                logger.info(f"No Drive files found for keywords: {keywords}")
                return []

            # Convert to CaseMatch objects
            matches = []
            for file in files:
                snippet = self._extract_snippet(file, keywords)
                matches.append(CaseMatch(
                    file_id=file['id'],
                    file_name=file['name'],
                    file_type=file.get('mimeType', 'unknown'),
                    web_link=file.get('webViewLink', ''),
                    snippet=snippet,
                    relevance_score=self._calculate_relevance(file, keywords)
                ))

            # Sort by relevance
            matches.sort(key=lambda x: x.relevance_score, reverse=True)

            logger.info(f"Found {len(matches)} matching files in Drive")
            return matches

        except Exception as e:
            logger.error(f"Drive search failed: {e}")
            return []

    def _extract_snippet(self, file: dict, keywords: list[str]) -> str:
        """
        Extract a relevant snippet from the file.
        For now, returns the description or a generic message.
        Full text extraction requires downloading the file.
        """
        # If file has a description, use that
        if file.get('description'):
            return file['description'][:500]

        # Otherwise, create a snippet from the filename
        name = file.get('name', 'Unknown file')

        # Check which keywords match in the filename
        matched = [kw for kw in keywords if kw.lower() in name.lower()]

        if matched:
            return f"File matches: {', '.join(matched)}"
        else:
            return f"Potentially relevant file: {name}"

    def _calculate_relevance(self, file: dict, keywords: list[str]) -> float:
        """Calculate a relevance score for the file."""
        score = 0.0
        name_lower = file.get('name', '').lower()
        desc_lower = (file.get('description') or '').lower()

        for keyword in keywords:
            kw_lower = keyword.lower()
            # Higher score for filename matches
            if kw_lower in name_lower:
                score += 2.0
            # Lower score for description matches
            if kw_lower in desc_lower:
                score += 1.0

        return score

    def get_file_content(self, file_id: str, max_chars: int = 5000) -> Optional[str]:
        """
        Download and extract text content from a file.
        Supports Google Docs, PDFs, and text files.
        """
        if not self.service:
            return None

        try:
            # Get file metadata
            file = self.service.files().get(
                fileId=file_id,
                fields='mimeType, name'
            ).execute()

            mime_type = file.get('mimeType', '')

            # Handle Google Docs - export as plain text
            if mime_type == 'application/vnd.google-apps.document':
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType='text/plain'
                )
            # Handle other files - download directly
            elif mime_type in ['text/plain', 'application/pdf']:
                request = self.service.files().get_media(fileId=file_id)
            else:
                logger.debug(f"Unsupported file type for content extraction: {mime_type}")
                return None

            # Download content
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            content = buffer.getvalue().decode('utf-8', errors='ignore')

            # Truncate if too long
            if len(content) > max_chars:
                content = content[:max_chars] + "..."

            return content

        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            return None

    def test_connection(self) -> bool:
        """Test if Drive API connection is working."""
        if not self.service:
            return False

        try:
            # Try to list a single file
            self.service.files().list(pageSize=1).execute()
            return True
        except Exception as e:
            logger.error(f"Drive connection test failed: {e}")
            return False


def create_drive_searcher(config: GoogleDriveConfig) -> Optional[GoogleDriveSearcher]:
    """
    Factory function to create a GoogleDriveSearcher if credentials are available.
    Returns None if credentials are not configured.
    """
    creds_path = Path(config.credentials_file)

    if not creds_path.exists():
        logger.info("Google Drive credentials not found - case comparison disabled")
        return None

    searcher = GoogleDriveSearcher(config)

    if searcher.test_connection():
        logger.info("Google Drive connection established")
        return searcher
    else:
        logger.warning("Google Drive connection failed - case comparison disabled")
        return None
