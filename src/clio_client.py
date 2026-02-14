"""
Clio API client for Pflug Law Lead Qualifier.
Handles matter creation for auto-accepted leads.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import ClioConfig

logger = logging.getLogger(__name__)


@dataclass
class MatterCreateRequest:
    """Data for creating a new Clio matter."""
    client_name: str
    matter_description: str
    injury_type: str
    accident_location: str
    accident_date: Optional[datetime]
    lead_source: Optional[str]
    phone: Optional[str] = None
    email: Optional[str] = None


@dataclass
class CreatedMatter:
    """Represents a successfully created Clio matter."""
    matter_id: int
    matter_number: str
    display_number: str
    description: str
    client_id: int
    web_url: str


class ClioClient:
    """Client for interacting with Clio API v4."""

    def __init__(self, config: ClioConfig):
        self.config = config

        # Set up session with retry logic
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

        # Cache for lookups
        self._responsible_attorney_id: Optional[int] = None
        self._practice_area_id: Optional[int] = None

    def _headers(self) -> dict:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
        }

    def _api_url(self, endpoint: str) -> str:
        """Build full API URL."""
        return f"{self.config.api_base_url}/{endpoint.lstrip('/')}"

    def test_connection(self) -> bool:
        """Test the Clio API connection."""
        try:
            response = self.session.get(
                self._api_url("/users/who_am_i"),
                headers=self._headers(),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            user = data.get("data", {})
            logger.info(f"Clio connection test successful. User: {user.get('name')}")
            return True
        except requests.RequestException as e:
            logger.error(f"Clio connection test failed: {e}")
            return False

    def _get_responsible_attorney_id(self) -> Optional[int]:
        """Get the ID of the responsible attorney."""
        if self._responsible_attorney_id:
            return self._responsible_attorney_id

        try:
            response = self.session.get(
                self._api_url("/users"),
                headers=self._headers(),
                params={"query": self.config.responsible_attorney_name},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            for user in data.get("data", []):
                if self.config.responsible_attorney_name.lower() in user.get("name", "").lower():
                    self._responsible_attorney_id = user["id"]
                    logger.info(f"Found responsible attorney ID: {self._responsible_attorney_id}")
                    return self._responsible_attorney_id

            logger.warning(f"Could not find attorney: {self.config.responsible_attorney_name}")
            return None

        except requests.RequestException as e:
            logger.error(f"Error fetching attorney: {e}")
            return None

    def _get_practice_area_id(self, practice_area_name: str = "Personal Injury") -> Optional[int]:
        """Get the practice area ID for PI cases."""
        if self._practice_area_id:
            return self._practice_area_id

        try:
            response = self.session.get(
                self._api_url("/practice_areas"),
                headers=self._headers(),
                params={"query": practice_area_name},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            for area in data.get("data", []):
                if practice_area_name.lower() in area.get("name", "").lower():
                    self._practice_area_id = area["id"]
                    logger.info(f"Found practice area ID: {self._practice_area_id}")
                    return self._practice_area_id

            # If not found, try to create it
            logger.info(f"Practice area '{practice_area_name}' not found, will skip")
            return None

        except requests.RequestException as e:
            logger.error(f"Error fetching practice area: {e}")
            return None

    def _find_or_create_contact(self, name: str, phone: Optional[str] = None,
                                 email: Optional[str] = None) -> Optional[int]:
        """Find existing contact or create a new one."""
        # First, try to find existing contact
        try:
            params = {"query": name, "type": "Person"}
            response = self.session.get(
                self._api_url("/contacts"),
                headers=self._headers(),
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            # Check for exact name match
            for contact in data.get("data", []):
                if contact.get("name", "").lower() == name.lower():
                    logger.info(f"Found existing contact: {contact['id']} - {contact['name']}")
                    return contact["id"]

        except requests.RequestException as e:
            logger.warning(f"Error searching for contact: {e}")

        # Create new contact
        try:
            # Parse name into first/last
            name_parts = name.strip().split()
            first_name = name_parts[0] if name_parts else "Unknown"
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

            contact_data = {
                "data": {
                    "type": "Person",
                    "first_name": first_name,
                    "last_name": last_name,
                }
            }

            # Add phone if provided
            if phone:
                contact_data["data"]["phone_numbers"] = [
                    {"name": "Mobile", "number": phone, "default_number": True}
                ]

            # Add email if provided
            if email:
                contact_data["data"]["email_addresses"] = [
                    {"name": "Work", "address": email, "default_email": True}
                ]

            response = self.session.post(
                self._api_url("/contacts"),
                headers=self._headers(),
                json=contact_data,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            contact_id = data["data"]["id"]
            logger.info(f"Created new contact: {contact_id} - {name}")
            return contact_id

        except requests.RequestException as e:
            logger.error(f"Error creating contact: {e}")
            return None

    def create_matter(self, request: MatterCreateRequest) -> Optional[CreatedMatter]:
        """Create a new matter in Clio."""
        # Get or create client contact
        client_id = self._find_or_create_contact(
            request.client_name,
            request.phone,
            request.email
        )
        if not client_id:
            logger.error("Could not create/find client contact")
            return None

        # Get attorney ID
        attorney_id = self._get_responsible_attorney_id()

        # Get practice area ID
        practice_area_id = self._get_practice_area_id()

        # Build matter description
        description = f"{request.injury_type} - {request.accident_location}"

        # Build matter data
        matter_data = {
            "data": {
                "description": description,
                "client": {"id": client_id},
                "status": "Open",
            }
        }

        # Add responsible attorney if found
        if attorney_id:
            matter_data["data"]["responsible_attorney"] = {"id": attorney_id}

        # Add practice area if found
        if practice_area_id:
            matter_data["data"]["practice_area"] = {"id": practice_area_id}

        # Add matter group if configured
        if self.config.default_matter_group_id:
            matter_data["data"]["group"] = {"id": int(self.config.default_matter_group_id)}

        try:
            response = self.session.post(
                self._api_url("/matters"),
                headers=self._headers(),
                json=matter_data,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            matter = data["data"]
            matter_id = matter["id"]

            # Try to add custom fields
            self._add_custom_fields(
                matter_id,
                request.lead_source,
                request.accident_date
            )

            # Build web URL
            web_url = f"https://app.clio.com/nc/#/matters/{matter_id}"

            created_matter = CreatedMatter(
                matter_id=matter_id,
                matter_number=str(matter.get("number", "")),
                display_number=matter.get("display_number", ""),
                description=matter.get("description", description),
                client_id=client_id,
                web_url=web_url,
            )

            logger.info(f"Created Clio matter: {matter_id} - {description}")
            return created_matter

        except requests.RequestException as e:
            logger.error(f"Error creating matter: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def _add_custom_fields(self, matter_id: int, lead_source: Optional[str],
                           accident_date: Optional[datetime]) -> None:
        """Add custom field values to a matter."""
        # Note: Custom fields need to be set up in Clio first
        # This is a best-effort operation - failures are logged but don't fail the matter creation

        custom_fields = []

        if lead_source:
            custom_fields.append({
                "field_name": "Lead Source",
                "value": lead_source
            })

        if accident_date:
            custom_fields.append({
                "field_name": "Accident Date",
                "value": accident_date.strftime("%Y-%m-%d")
            })

        if not custom_fields:
            return

        # First, get custom field definitions
        try:
            response = self.session.get(
                self._api_url("/custom_fields"),
                headers=self._headers(),
                params={"parent_type": "Matter"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            field_map = {}
            for field in data.get("data", []):
                field_map[field["name"].lower()] = field["id"]

            # Set custom field values
            for cf in custom_fields:
                field_name = cf["field_name"].lower()
                if field_name in field_map:
                    self._set_custom_field_value(
                        matter_id,
                        field_map[field_name],
                        cf["value"]
                    )

        except requests.RequestException as e:
            logger.warning(f"Could not set custom fields: {e}")

    def _set_custom_field_value(self, matter_id: int, field_id: int, value: str) -> None:
        """Set a custom field value on a matter."""
        try:
            response = self.session.post(
                self._api_url("/custom_field_values"),
                headers=self._headers(),
                json={
                    "data": {
                        "custom_field": {"id": field_id},
                        "matter": {"id": matter_id},
                        "value": value,
                    }
                },
                timeout=30,
            )
            response.raise_for_status()
            logger.debug(f"Set custom field {field_id} on matter {matter_id}")
        except requests.RequestException as e:
            logger.warning(f"Could not set custom field value: {e}")

    def refresh_access_token(self) -> bool:
        """Refresh the OAuth access token using the refresh token."""
        if not self.config.refresh_token:
            logger.error("No refresh token available")
            return False

        try:
            response = self.session.post(
                "https://app.clio.com/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.config.refresh_token,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            self.config.access_token = data["access_token"]
            if "refresh_token" in data:
                self.config.refresh_token = data["refresh_token"]

            logger.info("Refreshed Clio access token")
            return True

        except requests.RequestException as e:
            logger.error(f"Error refreshing token: {e}")
            return False
